"""Run the registered matrix with resumable, non-overwriting per-trial records."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
from gri_bench.runner import ROOT, run_trial, dump
from gri_bench.evaluate import score_trial, export_trial


def main():
    p=argparse.ArgumentParser()
    p.add_argument('phase',choices=['baselines','agents','grade'])
    p.add_argument('--tag',default='pilot-v2'); p.add_argument('--workers',type=int,default=2)
    args=p.parse_args()
    if args.phase=='grade':
        paths=sorted((ROOT/'private/runs'/args.tag).glob('*'))
        for path in paths:
            if not (path/'metadata.json').exists(): continue
            if not (path/'score.json').exists():
                score=score_trial(path)
                print(json.dumps({'trial':path.name,'feasible':score['feasible'],'safe_tir':score['safe_tir'],'status':score['status']}),flush=True)
            destination=ROOT/'results'/args.tag
            if not (destination/path.name).exists(): export_trial(path,destination)
        return
    models=json.loads((ROOT/'contract/pilot-models.json').read_text())['models']
    cases=[f'{split}-{i:02d}' for split in ['dev','sealed'] for i in range(1,7)]
    jobs=[]
    for i,case in enumerate(cases):
        choices=['constant_grid','sobol','differential_evolution'] if args.phase=='baselines' else models
        choices=choices[i%len(choices):]+choices[:i%len(choices)]
        for choice in choices:
            method=choice if args.phase=='baselines' else 'agent'
            model=None if args.phase=='baselines' else choice
            label=choice.replace('/','__')
            trial=ROOT/'private/runs'/args.tag/f'{case}__{label}__seed20261111'
            # Existing attempts are never rerun under the same identifier.
            if trial.exists(): continue
            jobs.append((case,method,model))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(run_trial,case,method,model,tag=args.tag) for case,method,model in jobs]
        for future in as_completed(futures): future.result()


if __name__=='__main__':main()

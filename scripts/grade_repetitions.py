"""Trusted native grading for the three supplemental tags, two host workers."""
from concurrent.futures import ProcessPoolExecutor
import json
import time
from gri_bench.runner import ROOT
from gri_bench.evaluate import score_trial, export_trial


def grade(path,tag):
    if not (path/'score.json').exists():score_trial(path)
    destination=ROOT/'results'/tag
    if not (destination/path.name).exists():export_trial(path,destination)
    score=json.loads((path/'score.json').read_text())
    return {'tag':tag,'trial':path.name,'status':score['status'],
            'feasible':score['feasible'],'safe_tir':score['safe_tir']}


def main():
    plan=json.loads((ROOT/'experiments/repeats-2026-11-11/plan.json').read_text())
    seen=set();futures={};finished=0
    with ProcessPoolExecutor(max_workers=2) as pool:
        while finished<len(plan['jobs']):
            for tag in plan['tags']:
                for path in sorted((ROOT/'private/runs'/tag).glob('*')):
                    if path in seen:continue
                    try:meta=json.loads((path/'metadata.json').read_text())
                    except (FileNotFoundError,json.JSONDecodeError):continue
                    if not meta.get('status'):continue
                    seen.add(path);futures[pool.submit(grade,path,tag)]=path
            for future in list(futures):
                if future.done():
                    print(json.dumps(future.result()),flush=True)
                    finished+=1;del futures[future]
            time.sleep(.5)


if __name__=='__main__':main()

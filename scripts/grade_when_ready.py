"""Score immutable completed submissions while other independent trials run."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import time
from gri_bench.runner import ROOT
from gri_bench.evaluate import score_trial, export_trial


def grade(path, tag):
    if not (path/'score.json').exists(): score_trial(path)
    destination=ROOT/'results'/tag
    if not (destination/path.name).exists():export_trial(path,destination)
    score=json.loads((path/'score.json').read_text())
    return {'trial':path.name,'status':score['status'],'feasible':score['feasible'],'safe_tir':score['safe_tir']}


def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['baselines','agents'])
    p.add_argument('--tag',default='pilot-v1');p.add_argument('--expected',type=int,default=36)
    args=p.parse_args();seen=set();futures={};finished=0
    with ProcessPoolExecutor(max_workers=2) as pool:
        while finished<args.expected:
            for path in sorted((ROOT/'private/runs'/args.tag).glob('*')):
                if path in seen:continue
                try:meta=json.loads((path/'metadata.json').read_text())
                except (FileNotFoundError,json.JSONDecodeError):continue
                if not meta.get('status'):continue
                if (meta['method']=='agent') != (args.phase=='agents'):continue
                seen.add(path);futures[pool.submit(grade,path,args.tag)]=path
            for future in list(futures):
                if future.done():
                    print(json.dumps(future.result()),flush=True)
                    finished+=1;del futures[future]
            time.sleep(.5)


if __name__=='__main__':main()

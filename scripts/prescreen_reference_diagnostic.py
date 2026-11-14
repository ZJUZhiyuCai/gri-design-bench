"""Separate, pre-recorded large-budget historical reference diagnostic."""
import argparse,json
from pathlib import Path
from gri_bench.prescreen_v03.run import (EXP,OUT,read,sha,digest_json,check_plan,screen_job,native_job,pool_run,audit_indices,write_new)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['screen','audit','report']);parser.add_argument('--output',type=Path);args=parser.parse_args()
    p=check_plan();addendum=read(EXP/'diagnostic-reference-plan.json');records=[]
    for r in addendum['designs']:
        d=digest_json({'case':r['case'],'design':r['design']})[:24]
        records.append({**r,'design_id':d})
    if args.stage=='screen':pool_run(screen_job,[(r['case'],r['design_id'],r['design']) for r in records],3)
    elif args.stage=='audit':
        jobs=[]
        for r in records:
            x=read(OUT/'screen'/f"{r['design_id']}.json")
            jobs.extend((r['case'],r['design_id'],r['design'],i,False) for i in audit_indices(x,p) if not(OUT/'native'/r['design_id']/f'{i:03}.json').exists())
        print('DIAGNOSTIC_NATIVE_JOBS',len(jobs),flush=True);pool_run(native_job,jobs,3)
    else:
        if args.output is None:raise ValueError('Need --output')
        result=[]
        for r in records:
            x=read(OUT/'screen'/f"{r['design_id']}.json");audits=[]
            from gri_bench.api import summarize
            for i in audit_indices(x,p):
                a=read(OUT/'native'/r['design_id']/f'{i:03}.json')
                audits.append(summarize([{'metrics':a['metrics']}])['feasible']==summarize([x['rows'][i]])['feasible'])
            result.append({'case':r['case'],'design_id':r['design_id'],'primary':x['primary'],'expanded':x['expanded'],'audit_count':len(audits),'audit_safety_mismatches':sum(not v for v in audits)})
        write_new(args.output,{'scope':addendum['scope'],'addendum_sha256':sha(EXP/'diagnostic-reference-plan.json'),'cases':result})
        print([(r['case'],round(r['primary']['safe_tir'],2),r['primary']['feasible']) for r in result])

if __name__=='__main__':main()

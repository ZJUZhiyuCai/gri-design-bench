"""Bounded, non-benchmark tool roundtrip probes; no model code is executed."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import requests
from gri_bench.runner import ROOT, TOOLS, dump


def probe(model, out):
    assert not any(x in model.lower() for x in ('claude', 'opus'))
    folder=out/model.replace('/', '__')
    folder.mkdir(parents=True, exist_ok=False)
    messages=[{'role':'system','content':'You are checking a MOCK shell tool. This is a protocol diagnostic, not a benchmark. No command will actually be executed.'},
              {'role':'user','content':'Call shell once with command "printf GRI_ROUTE_OK" and timeout_seconds 1. After the mock tool response, reply with only GRI_ROUTE_OK. Do not call another tool.'}]
    report={'requested_model':model,'started_utc':datetime.now(timezone.utc).isoformat(),
            'benchmark_inputs_used':False,'model_code_executed':False,'temperature':0,
            'max_completion_tokens_per_call':6000,'max_calls':2,'calls':[],'passed':False}
    start=time.monotonic()
    try:
        for index in range(2):
            request={'model':model,'messages':messages,'tools':TOOLS,'max_tokens':6000,'temperature':0}
            dump(folder/f'request-{index}.json',request)
            r=requests.post('http://127.0.0.1:3425/v1/chat/completions',json=request,timeout=120)
            raw=r.content;(folder/f'response-{index}.bin').write_bytes(raw)
            entry={'call':index,'http_status':r.status_code,'response_sha256':hashlib.sha256(raw).hexdigest()}
            report['calls'].append(entry)
            r.raise_for_status();data=r.json()
            entry.update({'returned_model':data.get('model'),'usage':data.get('usage'),
                          'finish_reason':data['choices'][0].get('finish_reason')})
            assert not any(x in str(data.get('model','')).lower() for x in ('claude','opus')), 'Excluded returned model'
            message=data['choices'][0]['message'];messages.append(message)
            calls=message.get('tool_calls') or []
            entry['tool_calls']=len(calls)
            if index==0:
                assert len(calls)==1,'Expected one mock shell tool call'
                call=calls[0];assert call['function']['name']=='shell'
                args=json.loads(call['function']['arguments'])
                assert isinstance(args['command'],str) and 'GRI_ROUTE_OK' in args['command']
                assert isinstance(args.get('timeout_seconds',1),(int,float))
                messages.append({'role':'tool','tool_call_id':call['id'],
                                 'content':json.dumps({'mock':True,'stdout':'GRI_ROUTE_OK','exit_code':0})})
            else:
                assert not calls and 'GRI_ROUTE_OK' in (message.get('content') or ''),'Missing mock tool roundtrip acknowledgement'
                report['passed']=True
    except Exception as error:
        report['error_type']=type(error).__name__
        (folder/'private-error.txt').write_text(str(error))
    report['wall_seconds']=time.monotonic()-start
    dump(folder/'report.json',report)
    print(json.dumps(report),flush=True)
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument('--models',nargs='+',required=True);p.add_argument('--tag',required=True)
    args=p.parse_args();out=ROOT/'private/expansion-probes'/args.tag
    out.mkdir(parents=True,exist_ok=False)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=[future.result() for future in as_completed([pool.submit(probe,m,out) for m in args.models])]
    dump(out/'summary.json',{'scope':'Non-benchmark mock tool roundtrip only. Failures retained.','results':results})


if __name__=='__main__':main()

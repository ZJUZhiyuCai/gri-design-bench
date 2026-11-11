"""Real Docker / mock API control; no external inference or scored attempt."""
import json
from unittest.mock import patch
import requests
from gri_bench.repeat_runner import run_trial
from gri_bench.runner import ROOT, dump


def main():
    requested=[]
    steps=[4000,'error',5000,'error']
    class Reply:
        def raise_for_status(self):
            if self.status_code!=200:raise requests.HTTPError(response=self)
        def json(self):return self.data
    def post(*args,**kwargs):
        i=len(requested);requested.append(kwargs['json']['max_tokens'])
        r=Reply();r.status_code=502 if steps[i]=='error' else 200
        r.content=b'{"error":{"message":"empty reply, whole output spent on reasoning"}}'
        command="mkdir -p /work/output; printf '%s\\n' '{\"mode\":\"constant\",\"parameters\":{\"theta_c\":0,\"theta_L\":4}}' > /work/output/design.json; printf 'pass\\n' > /work/output/search.py; printf 'mock accounting control\\n' > /work/output/rationale.md" if i==0 else 'true'
        r.data={'model':'mock-token-control','usage':{'prompt_tokens':100,'completion_tokens':steps[i]},
                'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[
                    {'id':f'call_{i}','type':'function','function':{'name':'shell','arguments':json.dumps({'command':command})}}]}}]}
        return r
    with patch('gri_bench.repeat_runner.requests.post',side_effect=post):
        path=run_trial('dev-01','mock-token-control',tag='control-token-repair')
    meta=json.loads((path/'metadata.json').read_text())
    messages=json.loads((path/'transcript.json').read_text())
    remaining=[json.loads(m['content'])['completion_tokens_remaining'] for m in messages if m['role']=='tool']
    assert requested==[6000,6000,6000,3000]
    assert remaining==[14000,3000]
    assert meta['status']=='submitted' and meta['charged_completion_tokens']==18000
    assert meta['model_calls']==4 and len(meta['api_errors'])==2
    record={'passed':True,'external_model_calls':0,'mock_calls':4,'requested_max_tokens':requested,
            'tool_reported_remaining_tokens':remaining,'charged_completion_tokens':meta['charged_completion_tokens'],
            'submission_files':meta['files'],'cpu_seconds':meta['cpu_seconds'],
            'source':'real isolated Docker task with synthetic API errors; excluded from model scores'}
    dump(ROOT/'results/controls/token-accounting-repair.json',record)
    print(json.dumps(record))


if __name__=='__main__':main()

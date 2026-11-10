"""Mock-model integration check of the 12-call profile; no external API call."""
import json
from unittest.mock import patch
from gri_bench.runner import run_trial, ROOT, dump


class Response:
    def raise_for_status(self): pass
    def json(self):
        return self.data


def main():
    count=0
    def post(*args,**kwargs):
        nonlocal count
        count+=1
        command="mkdir -p /work/output; printf '%s\\n' '{\"mode\":\"constant\",\"parameters\":{\"theta_c\":0,\"theta_L\":4}}' > /work/output/design.json; printf 'pass\\n' > /work/output/search.py; printf 'mock control\\n' > /work/output/rationale.md" if count==1 else 'true'
        r=Response();r.data={'model':'mock-budget-control','usage':{'prompt_tokens':100,'completion_tokens':1},
          'choices':[{'finish_reason':'tool_calls','message':{'role':'assistant','content':None,
          'tool_calls':[{'id':f'call_{count}','type':'function','function':{'name':'shell','arguments':json.dumps({'command':command})}}]}}]}
        return r
    with patch('gri_bench.runner.requests.post',side_effect=post):
        path=run_trial('dev-01','agent','mock-budget-control',tag='control-v2')
    meta=json.loads((path/'metadata.json').read_text())
    messages=json.loads((path/'transcript.json').read_text())
    remaining=[json.loads(m['content'])['model_calls_remaining'] for m in messages if m['role']=='tool']
    assert count==12 and remaining==list(range(11,-1,-1))
    assert meta['status']=='submitted' and all(v=='ok' for v in meta['files'].values())
    dump(ROOT/'results/controls/agent-budget-v2.json',{'passed':True,'external_model_calls':0,'mock_calls':count,
         'reported_remaining_calls':remaining,'submission_files':meta['files'],
         'cpu_seconds':meta['cpu_seconds'],'source':'mock response integration test, excluded from model scores'})
    print(json.dumps({'passed':True,'mock_calls':count,'external_model_calls':0}))


if __name__=='__main__':main()

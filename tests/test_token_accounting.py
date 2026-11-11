import ast
import copy
import json
from pathlib import Path
import requests
import pytest
from gri_bench import runner, repeat_runner
from gri_bench.token_accounting import CompletionBudget, TokenUsageViolation


def test_error_requests_cannot_get_free_retry_tokens():
    budget=CompletionBudget()
    assert budget.reserve(0)==6000
    budget.settle({'completion_tokens':4000},http_status=200)
    assert budget.remaining==14000
    assert budget.reserve(1)==6000
    budget.settle(failed=True,http_status=502)
    assert budget.remaining==8000
    assert budget.reserve(2)==6000
    budget.settle({'completion_tokens':5000},http_status=200)
    assert budget.remaining==3000
    assert budget.reserve(3)==3000
    budget.settle(failed=True,http_status=502)
    assert budget.charged==18000
    with pytest.raises(RuntimeError):budget.reserve(4)


@pytest.mark.parametrize('usage',[None,{}, {'completion_tokens':-1}, {'completion_tokens':False}, {'completion_tokens':'100'}])
def test_missing_or_malformed_usage_consumes_reservation(usage):
    budget=CompletionBudget(total=1700)
    assert budget.reserve(0)==1700
    budget.settle(usage)
    assert budget.charged==1700
    assert budget.entries[0]['basis']=='missing_or_invalid_usage_reserved_max'


def test_provider_overrun_is_detected_and_cannot_refill_budget():
    budget=CompletionBudget()
    budget.reserve(0)
    with pytest.raises(TokenUsageViolation):budget.settle({'completion_tokens':6001})
    assert budget.charged==6000 and budget.pending is None
    assert budget.entries[0]['basis']=='usage_exceeds_request'


def test_system_prompt_is_byte_identical_to_frozen_runner():
    tree=ast.parse(Path(runner.__file__).read_text())
    matches=[node.value for node in ast.walk(tree) if isinstance(node,ast.Constant)
             and isinstance(node.value,str) and node.value.startswith('You are a scientific design agent.')]
    assert matches==[repeat_runner.SYSTEM_PROMPT]


def _mock_run(tmp_path,monkeypatch,module,steps,tag):
    root=tmp_path/tag;root.mkdir()
    (root/'docs').mkdir();(root/'docs/AGENT_TASK.md').write_text('Frozen public task')
    monkeypatch.setattr(module,'ROOT',root)
    monkeypatch.setattr(module,'verify_runtime_lock',lambda:{'pilot_image_id':'image'})
    monkeypatch.setattr(module,'load_case',lambda _:({'split':'development','id':'dev-01'},[]))
    monkeypatch.setattr(module,'digest',lambda _:'digest')
    monkeypatch.setattr(module.subprocess,'check_output',lambda *a,**k:'image\n' if a[0][0]=='docker' else 'commit\n')

    class FakeSandbox:
        exhausted=False;last_cpu=1.;tool_wall=1.
        def __init__(self,*a,**k):pass
        def command(self,*a,**k):return {'output':'ok'}
        def collect(self):return {'design.json':'ok','search.py':'ok','rationale.md':'ok'}
        def close(self):pass
    monkeypatch.setattr(module,'Sandbox',FakeSandbox)
    captured=[]
    class Reply:
        def __init__(self,step,i):
            self.status_code=502 if step=='error' else 200
            self.content=b'{"error":{"message":"empty reply, whole output spent on reasoning"}}'
            self.step=step;self.index=i
        def raise_for_status(self):
            if self.status_code==502:raise requests.HTTPError(response=self)
        def json(self):
            return {'model':'test-model','usage':{'completion_tokens':self.step},'choices':[{'message':{
                'role':'assistant','content':None,'tool_calls':[{'id':f'call-{self.index}','type':'function',
                   'function':{'name':'shell','arguments':'{"command":"true"}'}}]}}]}
    def post(url,headers,json,timeout):
        captured.append(copy.deepcopy(json))
        return Reply(steps[len(captured)-1],len(captured))
    monkeypatch.setattr(module.requests,'post',post)
    if module is runner:path=module.run_trial('dev-01','agent',model='test-model',tag=tag)
    else:path=module.run_trial('dev-01','test-model',tag=tag)
    return captured,json.loads((path/'metadata.json').read_text())


def test_successful_usage_path_preserves_requests_and_prompt(tmp_path,monkeypatch):
    old,old_meta=_mock_run(tmp_path,monkeypatch,runner,[6000]*3,'old-control')
    new,new_meta=_mock_run(tmp_path,monkeypatch,repeat_runner,[6000]*3,'new-control')
    assert old_meta['model_calls']==new_meta['model_calls']==3
    # Wall-clock feedback naturally differs; every other request field matches.
    for requests_list in [old,new]:
        for request in requests_list:
            for message in request['messages']:
                if message['role']=='tool':
                    content=json.loads(message['content']);content.pop('agent_wall_seconds_remaining')
                    message['content']=content
    assert old==new
    assert new_meta['charged_completion_tokens']==18000


def test_runner_charges_error_and_stops_at_original_total_limit(tmp_path,monkeypatch):
    captured,meta=_mock_run(tmp_path,monkeypatch,repeat_runner,[4000,'error',5000,'error'],'error-control')
    assert [r['max_tokens'] for r in captured]==[6000,6000,6000,3000]
    assert meta['charged_completion_tokens']==18000
    assert meta['completion_token_budget_exhausted']
    assert meta['model_calls']==4 and len(meta['api_errors'])==2
    assert meta['status']=='submitted'  # existing checkpoint remains eligible
    assert sum(e['charged_completion_tokens'] for e in meta['completion_token_accounting'])==18000


def test_existing_two_error_stop_is_preserved(tmp_path,monkeypatch):
    captured,meta=_mock_run(tmp_path,monkeypatch,repeat_runner,['error','error'],'two-error-control')
    assert len(captured)==2 and meta['charged_completion_tokens']==12000
    assert len(meta['api_errors'])==2

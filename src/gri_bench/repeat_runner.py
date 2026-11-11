"""Supplemental trials: frozen task/sandbox with corrected error-token accounting.

The original runner remains byte-identical for historical reproduction. This
host-only entry point preserves its prompts, requests, retry/stop policy, tool
execution and scoring artifacts. It additionally charges failed requests against
the existing 18,000-token allowance and records an auditable per-request ledger.
"""
import argparse
import hashlib
import json
import os
import subprocess
import time
import requests
from .runner import ROOT, TOOLS, Sandbox, dump, digest, load_case, verify_runtime_lock
from .token_accounting import CompletionBudget, TokenUsageViolation

SYSTEM_PROMPT='You are a scientific design agent. Work autonomously using the shell tool. You have at most 12 model calls. Save initial versions of all three required files within the first two calls, then improve the design and code. Tool results report remaining budgets. Your final prose is not the submission. Shell runs in an isolated container. API/model waiting does not consume container CPU. Do not assume training safety guarantees heldout safety.'
PROFILE='strict-token-accounting-v1'


def verify_repeat_lock(tag):
    path=ROOT/'experiments/repeats-2026-11-11/lock.json'
    if not path.exists():
        if tag.startswith('repeat-20261111-'):
            raise ValueError('Supplemental execution must be frozen before scored runs')
        return
    lock=json.loads(path.read_text())
    for name,expected in lock['files'].items():
        if digest(ROOT/name)!=expected:
            raise ValueError('Frozen supplemental implementation changed: '+name)


def run_trial(case_id, model, tag, context='colima-etbench', image='gri-bench:0.1.1'):
    lock=verify_runtime_lock()
    verify_repeat_lock(tag)
    label=model.replace('/','__')
    trial_id=f'{case_id}__{label}__seed20261111'
    output=ROOT/'private/runs'/tag/trial_id
    output.mkdir(parents=True,exist_ok=False)
    instance,_=load_case(case_id)
    metadata={'trial_id':trial_id,'instance_id':case_id,'split':instance['split'],'method':'agent','requested_model':model,
              'seed':20261111,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
              'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'contract_sha256':digest(ROOT/'contract/contract.json'),'image':image,
              'image_id':subprocess.check_output(['docker','--context',context,'image','inspect',image,'--format','{{.Id}}'],text=True).strip(),
              'usage':[],'returned_models':[],'api_errors':[],'model_calls':0,
              'execution_profile':PROFILE,'repetition_tag':tag,
              'system_prompt_sha256':hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()}
    if tag.startswith('repeat-20261111-') and metadata['image_id']!=lock['pilot_image_id']:
        raise ValueError('Frozen trial image changed')
    dump(output/'metadata.json',metadata)
    start=time.monotonic();sandbox=None;budget=CompletionBudget()
    try:
        sandbox=Sandbox(output,instance,context,image)
        task=(ROOT/'docs/AGENT_TASK.md').read_text()
        messages=[{'role':'system','content':SYSTEM_PROMPT},
                  {'role':'user','content':task+'\n\nYOUR INSTANCE:\n'+json.dumps(instance)}]
        for call_index in range(12):
            remaining=360-(time.monotonic()-start)
            if remaining<=1 or budget.remaining<=0 or sandbox.exhausted:break
            base_url=os.environ.get('GRI_MODEL_BASE_URL','http://127.0.0.1:3425/v1').rstrip('/')
            headers={}
            if os.environ.get('GRI_MODEL_API_KEY'):
                headers['Authorization']='Bearer '+os.environ['GRI_MODEL_API_KEY']
            metadata['model_calls']+=1
            request={'model':model,'messages':messages,'tools':TOOLS,
                     'max_tokens':budget.reserve(call_index),'temperature':0}
            response=None
            try:
                response=requests.post(base_url+'/chat/completions',headers=headers,json=request,timeout=min(120,remaining))
                response.raise_for_status();data=response.json()
                message=data['choices'][0]['message']
                if not isinstance(message,dict):raise ValueError('Malformed assistant message')
                dump(output/f'response-{call_index:02d}.json',data)
                metadata['returned_models'].append(data.get('model'))
                usage=data.get('usage',{});metadata['usage'].append(usage)
                budget.settle(usage,http_status=response.status_code)
            except TokenUsageViolation:
                metadata['token_usage_violation']=True
                raise
            except (requests.RequestException,ValueError,KeyError,IndexError) as error:
                status=getattr(response,'status_code',None)
                entry=budget.settle(failed=True,http_status=status)
                record={'call':call_index,'type':type(error).__name__,'http_status':status,
                        'charged_completion_tokens':entry['charged_completion_tokens']}
                if response is not None:
                    raw=response.content
                    (output/f'error-response-{call_index:02d}.bin').write_bytes(raw[:2_000_000])
                    record['response_sha256']=hashlib.sha256(raw).hexdigest()
                    # Classification only; raw error text stays private.
                    lower=raw.lower()
                    if b'empty' in lower and b'reasoning' in lower:
                        record['classification']='reasoning_only_at_output_limit'
                metadata['api_errors'].append(record)
                if len(metadata['api_errors'])>=2:break
                continue
            messages.append(message)
            calls=message.get('tool_calls') or []
            if not calls:break
            for tool_call in calls:
                try:
                    if tool_call['function']['name']!='shell':raise ValueError('Unknown tool')
                    args=json.loads(tool_call['function']['arguments'])
                    command=args['command']
                    if not isinstance(command,str):raise ValueError('Invalid command')
                    remaining=max(.1,360-(time.monotonic()-start))
                    result=sandbox.command(command,min(float(args.get('timeout_seconds',85)),remaining))
                except (ValueError,KeyError,TypeError) as error:
                    result={'error':type(error).__name__}
                result['model_calls_remaining']=12-metadata['model_calls']
                result['completion_tokens_remaining']=budget.remaining
                result['agent_wall_seconds_remaining']=max(0.,360-(time.monotonic()-start))
                if result['model_calls_remaining']<=2:
                    result['finalization_reminder']='Finalize design.json, search.py and rationale.md now. No extra calls are granted after the limit.'
                messages.append({'role':'tool','tool_call_id':tool_call['id'],'content':json.dumps(result)})
            dump(output/'transcript.json',messages)
        metadata['files']=sandbox.collect()
        metadata['cpu_seconds']=sandbox.last_cpu
        metadata['tool_wall_seconds']=sandbox.tool_wall
        metadata['budget_exhausted']=sandbox.exhausted
        metadata['status']='submitted' if all(x=='ok' for x in metadata['files'].values()) else 'submission_failure'
        metadata['artifact_sha256']={n:digest(output/n) for n,v in metadata['files'].items() if v=='ok'}
    except Exception as error:
        metadata['status']='infrastructure_error'
        metadata['error_type']=type(error).__name__
        (output/'infrastructure-error.txt').write_text(str(error))
    finally:
        if budget.pending is not None:budget.settle(failed=True)
        metadata['completion_token_accounting']=budget.entries
        metadata['charged_completion_tokens']=budget.charged
        metadata['completion_token_budget_exhausted']=budget.remaining<=0
        if sandbox is not None:sandbox.close()
        metadata['wall_seconds']=time.monotonic()-start
        dump(output/'metadata.json',metadata)
    print(json.dumps({k:metadata.get(k) for k in ['trial_id','repetition_tag','status','cpu_seconds','wall_seconds','model_calls','charged_completion_tokens']}),flush=True)
    return output


def main():
    p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--model',required=True)
    p.add_argument('--tag',required=True);p.add_argument('--context',default='colima-etbench')
    p.add_argument('--image',default='gri-bench:0.1.1');args=p.parse_args()
    run_trial(args.case,args.model,args.tag,args.context,args.image)


if __name__=='__main__':main()

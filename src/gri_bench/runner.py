"""Host-side orchestration; untrusted agent shell runs only in a disposable container.

The host requests the model, pauses the container between tool calls, enforces
aggregate cgroup CPU, and copies only three size-limited regular output files.
No credentials, Docker socket, repository mount, or sealed seed enters the agent.
"""
import argparse
import ast
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time
import uuid
import requests

ROOT = Path(__file__).resolve().parents[2]
TOOLS = [{'type':'function','function':{'name':'shell','description':'Run a shell command in the isolated Linux task workspace. Total CPU budget is shared across all calls. Write/checkpoint output files early.',
    'parameters':{'type':'object','properties':{'command':{'type':'string'},'timeout_seconds':{'type':'number'}},'required':['command'],'additionalProperties':False}}}]


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def verify_runtime_lock():
    lock = json.loads((ROOT/'contract/runtime-lock.json').read_text())
    for name, expected in lock['files'].items():
        if digest(ROOT/name) != expected:
            raise ValueError('Frozen implementation/input changed: '+name)
    return lock


def load_case(case_id):
    if case_id.startswith('dev-'):
        instance = json.loads((ROOT/f'instances/dev/{case_id}.json').read_text())
        evaluation = json.loads((ROOT/f'instances/dev/{case_id}-evaluation.json').read_text())
        return instance, evaluation['evaluation_seeds']
    path = ROOT/f'private/sealed/{case_id}.json'
    manifest = json.loads((ROOT/'contract/sealed-manifest.json').read_text())
    if digest(path) != manifest['files'][case_id]:
        raise ValueError('Sealed case commitment mismatch')
    data = json.loads(path.read_text())
    return data['instance'], data['evaluation_seeds']


class Sandbox:
    def __init__(self, output, instance, context, image):
        self.output = Path(output); self.context = context; self.name = 'gri-'+uuid.uuid4().hex[:12]
        self.paused = False; self.exhausted = False; self.tool_wall = 0.; self.last_cpu = 0.
        self.dc('run','-d','--name',self.name,'--label','gri.trial='+self.output.name,'--network','none','--cpus','1','--memory','2048m','--memory-swap','2048m',
                '--pids-limit','64','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only',
                '--tmpfs','/work:rw,exec,size=268435456,uid=1000,gid=1000',
                '--tmpfs','/tmp:rw,exec,size=134217728,mode=1777',image)
        try:
            dump(self.output/'instance.json',instance)
            self.put_file('/work/instance.json',(self.output/'instance.json').read_bytes())
            self.dc('exec',self.name,'mkdir','-p','/work/output')
            self.dc('exec',self.name,'cp','-R','/opt/numba-cache','/tmp/numba')
            self.dc('exec',self.name,'python','-c','from gri_bench.physiology import *; p,x=patient_parameters("adult#001"); fast_trace(p,x,np.zeros(6),np.array([0.,1.,150.,2.,10.,100.]))')
        except Exception:
            self.close(); raise
        self.start_cpu = self.cpu_raw()
        self.pause()

    def dc(self, *args, check=True, timeout=60):
        return subprocess.run(['docker','--context',self.context,*args],check=check,capture_output=True,timeout=timeout)

    def put_file(self, path, data):
        was_paused = self.paused
        self.unpause()
        try:
            subprocess.run(['docker','--context',self.context,'exec','-i',self.name,'python','-c',
                            'import pathlib,sys; pathlib.Path(sys.argv[1]).write_bytes(sys.stdin.buffer.read())',path],
                           input=data,check=True,capture_output=True,timeout=30)
        finally:
            if was_paused: self.pause()

    def cpu_raw(self):
        out = self.dc('exec',self.name,'cat','/sys/fs/cgroup/cpu.stat').stdout.decode()
        return int(dict(line.split() for line in out.splitlines())['usage_usec'])/1e6

    def pause(self):
        if not self.paused:
            self.dc('pause',self.name); self.paused = True

    def unpause(self):
        if self.paused:
            self.dc('unpause',self.name); self.paused = False

    def command(self, command, timeout=85.):
        if self.exhausted:
            return {'output':'CPU or tool wall budget exhausted.','cpu_seconds':self.last_cpu,'budget_exhausted':True}
        remaining_wall = 90.-self.tool_wall
        if remaining_wall <= 0:
            self.exhausted = True
            return {'output':'Tool wall budget exhausted.','budget_exhausted':True}
        timeout = max(.1,min(float(timeout),remaining_wall,85.))
        self.unpause(); started = time.monotonic()
        log = self.output/f'tool-{len(list(self.output.glob("tool-*.txt"))):02d}.txt'
        reason = None
        with log.open('wb') as stream:
            proc = subprocess.Popen(['docker','--context',self.context,'exec',self.name,'timeout','-k','1',str(timeout),'bash','-lc',command],stdout=stream,stderr=subprocess.STDOUT)
            while proc.poll() is None:
                self.last_cpu = self.cpu_raw()-self.start_cpu
                elapsed = time.monotonic()-started
                if self.last_cpu >= 29.7 or elapsed >= remaining_wall or log.stat().st_size > 2_000_000:
                    reason = 'cpu_budget' if self.last_cpu >= 29.7 else 'tool_wall_or_output_budget'
                    self.exhausted = True; self.pause(); proc.terminate()
                    try: proc.wait(timeout=5)
                    except subprocess.TimeoutExpired: proc.kill(); proc.wait()
                    break
                time.sleep(.15)
            if not self.paused:
                self.last_cpu = self.cpu_raw()-self.start_cpu
                self.pause()
        elapsed = time.monotonic()-started; self.tool_wall += elapsed
        if self.last_cpu >= 29.7: self.exhausted = True
        return {'exit_code':proc.returncode,'output':log.read_text(errors='replace')[:12000],
                'cpu_seconds':self.last_cpu,'cpu_remaining':max(0.,30-self.last_cpu),
                'tool_wall_seconds':self.tool_wall,'budget_exhausted':self.exhausted,'stop_reason':reason}

    def collect(self):
        # Docker archive API does not expose this runtime's tmpfs contents.
        # Stop all other same-UID processes, then use a fixed isolated Python
        # reader from the immutable image. It never imports submitted code.
        # PID 1 and the calling reader are excluded by Linux kill(-1, ...).
        reader = '''import os,signal,stat,json,base64
try: os.kill(-1,signal.SIGKILL)
except ProcessLookupError: pass
result={}
for name,limit in [('design.json',16000),('search.py',262144),('rationale.md',65536)]:
 try:
  fd=os.open('/work/output/'+name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
  try:
   st=os.fstat(fd)
   if not stat.S_ISREG(st.st_mode) or not 0<st.st_size<=limit: raise ValueError('invalid')
   data=os.read(fd,limit+1)
   if len(data)>limit: raise ValueError('invalid')
   result[name]={'status':'ok','data':base64.b64encode(data).decode()}
  finally: os.close(fd)
 except FileNotFoundError: result[name]={'status':'missing'}
 except (OSError,ValueError): result[name]={'status':'invalid'}
print(json.dumps(result))
'''
        self.unpause()
        try:
            response=self.dc('exec',self.name,'/usr/local/bin/python','-I','-c',reader)
            payload=json.loads(response.stdout)
        finally:
            self.pause()
        status={}
        for name, item in payload.items():
            status[name]=item['status']
            if item['status']=='ok':
                data=base64.b64decode(item['data'],validate=True)
                (self.output/name).write_bytes(data)
                if name=='search.py':
                    try: ast.parse(data.decode())
                    except (SyntaxError,UnicodeError): status[name]='invalid'
        return status

    def close(self): self.dc('rm','-f',self.name,check=False)


def run_trial(case_id, method, model=None, context='colima-etbench', image='gri-bench:0.1.1', tag='pilot-v2'):
    lock = verify_runtime_lock()
    label = model.replace('/','__') if model else method
    trial_id = f'{case_id}__{label}__seed20261111'
    output = ROOT/'private/runs'/tag/trial_id
    output.mkdir(parents=True,exist_ok=False)
    instance, _ = load_case(case_id)
    metadata = {'trial_id':trial_id,'instance_id':case_id,'split':instance['split'],'method':method,'requested_model':model,
                'seed':20261111,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                'contract_sha256':digest(ROOT/'contract/contract.json'), 'image':image,
                'image_id':subprocess.check_output(['docker','--context',context,'image','inspect',image,'--format','{{.Id}}'],text=True).strip(),
                'usage':[], 'returned_models':[], 'api_errors':[], 'model_calls':0}
    if tag == 'pilot-v2' and metadata['image_id'] != lock['pilot_image_id']:
        raise ValueError('Pilot image changed after runtime freeze')
    dump(output/'metadata.json',metadata)
    start = time.monotonic(); sandbox = None
    try:
        sandbox = Sandbox(output,instance,context,image)
        if not model:
            sandbox.put_file('/work/baseline.py',(ROOT/'src/gri_bench/baseline.py').read_bytes())
            tool = sandbox.command(f'python /work/baseline.py --method {method} --seed 20261111 --seconds 28',85)
            dump(output/'baseline-tool.json',tool)
        else:
            task = (ROOT/'docs/AGENT_TASK.md').read_text()
            messages = [{'role':'system','content':'You are a scientific design agent. Work autonomously using the shell tool. You have at most 12 model calls. Save initial versions of all three required files within the first two calls, then improve the design and code. Tool results report remaining budgets. Your final prose is not the submission. Shell runs in an isolated container. API/model waiting does not consume container CPU. Do not assume training safety guarantees heldout safety.'},
                        {'role':'user','content':task+'\n\nYOUR INSTANCE:\n'+json.dumps(instance)}]
            completed_tokens = 0
            for call_index in range(12):
                remaining = 360-(time.monotonic()-start)
                if remaining <= 1 or completed_tokens >= 18000 or sandbox.exhausted: break
                base_url = os.environ.get('GRI_MODEL_BASE_URL','http://127.0.0.1:3425/v1').rstrip('/')
                headers = {}
                if os.environ.get('GRI_MODEL_API_KEY'):
                    headers['Authorization'] = 'Bearer '+os.environ['GRI_MODEL_API_KEY']
                metadata['model_calls'] += 1
                request = {'model':model,'messages':messages,'tools':TOOLS,'max_tokens':min(6000,18000-completed_tokens),'temperature':0}
                try:
                    response = requests.post(base_url+'/chat/completions',headers=headers,json=request,timeout=min(120,remaining))
                    response.raise_for_status(); data = response.json()
                    message = data['choices'][0]['message']
                    dump(output/f'response-{call_index:02d}.json',data)
                    metadata['returned_models'].append(data.get('model'))
                    usage = data.get('usage',{}); metadata['usage'].append(usage)
                    completed_tokens += int(usage.get('completion_tokens',6000))
                except (requests.RequestException,ValueError,KeyError,IndexError) as error:
                    metadata['api_errors'].append({'call':call_index,'type':type(error).__name__,
                                                  'http_status':getattr(getattr(error,'response',None),'status_code',None)})
                    # One ordinary retry uses another model call and the same
                    # immutable task/context; every failed attempt is retained.
                    if len(metadata['api_errors']) >= 2: break
                    continue
                messages.append(message)
                calls = message.get('tool_calls') or []
                if not calls: break
                for tool_call in calls:
                    try:
                        if tool_call['function']['name'] != 'shell': raise ValueError('Unknown tool')
                        args = json.loads(tool_call['function']['arguments'])
                        command = args['command']
                        if not isinstance(command,str): raise ValueError('Invalid command')
                        remaining = max(.1,360-(time.monotonic()-start))
                        result = sandbox.command(command,min(float(args.get('timeout_seconds',85)),remaining))
                    except (ValueError,KeyError,TypeError) as error:
                        result = {'error':type(error).__name__}
                    result['model_calls_remaining'] = 12-metadata['model_calls']
                    result['completion_tokens_remaining'] = max(0,18000-completed_tokens)
                    result['agent_wall_seconds_remaining'] = max(0.,360-(time.monotonic()-start))
                    if result['model_calls_remaining'] <= 2:
                        result['finalization_reminder'] = 'Finalize design.json, search.py and rationale.md now. No extra calls are granted after the limit.'
                    messages.append({'role':'tool','tool_call_id':tool_call['id'],'content':json.dumps(result)})
                dump(output/'transcript.json',messages)
        metadata['files'] = sandbox.collect()
        metadata['cpu_seconds'] = sandbox.last_cpu
        metadata['tool_wall_seconds'] = sandbox.tool_wall
        metadata['budget_exhausted'] = sandbox.exhausted
        metadata['status'] = 'submitted' if all(x == 'ok' for x in metadata['files'].values()) else 'submission_failure'
        metadata['artifact_sha256'] = {n:digest(output/n) for n,v in metadata['files'].items() if v == 'ok'}
    except Exception as error:
        metadata['status'] = 'infrastructure_error'
        metadata['error_type'] = type(error).__name__
        (output/'infrastructure-error.txt').write_text(str(error))
    finally:
        if sandbox is not None: sandbox.close()
        metadata['wall_seconds'] = time.monotonic()-start
        dump(output/'metadata.json',metadata)
    print(json.dumps({k:metadata.get(k) for k in ['trial_id','status','cpu_seconds','wall_seconds','model_calls']}),flush=True)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--method',default='agent',choices=['agent','constant_grid','sobol','differential_evolution'])
    parser.add_argument('--model'); parser.add_argument('--context',default='colima-etbench')
    parser.add_argument('--image',default='gri-bench:0.1.1'); parser.add_argument('--tag',default='pilot-v2')
    args = parser.parse_args()
    if args.method == 'agent' and not args.model: parser.error('--model required for agent')
    run_trial(args.case,args.method,args.model,args.context,args.image,args.tag)


if __name__ == '__main__': main()

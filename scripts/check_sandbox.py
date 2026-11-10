"""Executable isolation and budget controls, without model calls or search."""
import json
import tempfile
from pathlib import Path
from gri_bench.runner import ROOT, Sandbox, load_case, dump

instance,_=load_case('dev-01')
with tempfile.TemporaryDirectory(prefix='gri-control-') as temp:
    s=Sandbox(temp,instance,'colima-etbench','gri-bench:0.1')
    try:
        command="""python - <<'PY'
import socket,pathlib,os,json
assert os.getuid()==1000
assert not pathlib.Path('/Users/rosscai/.config/magpie').exists()
assert not pathlib.Path('/private/sealed').exists()
assert not pathlib.Path('/var/run/docker.sock').exists()
try:
    socket.create_connection(('1.1.1.1',443),timeout=1)
    raise AssertionError('Network enabled')
except OSError: pass
try:
    pathlib.Path('/opt/gri_bench/api.py').write_text('corrupt')
    raise AssertionError('Trusted source writable')
except PermissionError: pass
except OSError: pass
p=pathlib.Path('/work/output')
(p/'design.json').symlink_to('/etc/passwd')
(p/'search.py').write_text('pass\\n')
(p/'rationale.md').write_text('sandbox control')
print('nonroot, network isolation, secret isolation, Docker socket isolation, source write protection passed')
PY"""
        isolation=s.command(command)
        assert isolation['exit_code']==0,isolation
        files=s.collect();assert files['design.json']=='invalid',files
        budget=s.command('python -c "while True: pass"',85)
        assert budget['budget_exhausted'] and budget['stop_reason']=='cpu_budget',budget
        assert 29.7 <= budget['cpu_seconds'] <=30.5,budget
        out=ROOT/'results/controls';out.mkdir(parents=True,exist_ok=True)
        dump(out/'sandbox.json',{'passed':True,'isolation':isolation,'symlink_rejected':files,'cpu_budget':budget,
                               'note':'Polling reserves 0.3 CPU seconds; observed cgroup CPU is recorded, not estimated from simulation calls.'})
        print(json.dumps({'passed':True,'cpu_seconds':budget['cpu_seconds']}))
    finally:s.close()

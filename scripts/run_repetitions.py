"""Run only the predeclared supplemental matrix; never overwrite an attempt."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from gri_bench.runner import ROOT, verify_runtime_lock
from gri_bench.repeat_runner import run_trial, verify_repeat_lock


def main():
    plan=json.loads((ROOT/'experiments/repeats-2026-11-11/plan.json').read_text())
    verify_runtime_lock();verify_repeat_lock(plan['tags'][0])
    jobs=[]
    for job in plan['jobs']:
        folder=ROOT/'private/runs'/job['tag']/f"{job['case']}__{job['model'].replace('/','__')}__seed20261111"
        if folder.exists():
            metadata=folder/'metadata.json'
            if metadata.exists() and json.loads(metadata.read_text()).get('status'):
                continue
            raise RuntimeError('Existing unfinished attempt must be accounted for, not silently rerun: '+str(folder))
        jobs.append(job)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(run_trial,j['case'],j['model'],j['tag']) for j in jobs]
        for future in as_completed(futures):future.result()


if __name__=='__main__':main()

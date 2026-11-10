"""Trusted scoring and explicit public export; sealed inputs stay private."""
import argparse
import json
from pathlib import Path
import shutil
from .api import validate_design
from .native import verify_design
from .runner import ROOT, digest, dump, load_case, verify_runtime_lock


def strict_json(path):
    def unique(items):
        d = {}
        for k, v in items:
            if k in d: raise ValueError('Duplicate JSON key')
            d[k] = v
        return d
    def reject(value): raise ValueError('Nonfinite JSON constant')
    return json.loads(Path(path).read_text(),object_pairs_hook=unique,parse_constant=reject)


def score_trial(path):
    verify_runtime_lock()
    path = Path(path)
    if (path/'score.json').exists(): raise FileExistsError('Refusing to overwrite an earlier score')
    meta = strict_json(path/'metadata.json')
    instance, seeds = load_case(meta['instance_id'])
    if meta['status'] == 'infrastructure_error':
        result = {'status':'infrastructure_error','format_valid':False,'feasible':False,'safe_tir':None,
                  'reason':meta.get('error_type')}
    else:
        try:
            if meta['status'] != 'submitted': raise ValueError('Required submission file missing or invalid')
            for name, expected in meta['artifact_sha256'].items():
                if digest(path/name) != expected: raise ValueError('Submission changed after trial ended')
            design = strict_json(path/'design.json'); validate_design(design,instance)
        except (ValueError,KeyError,UnicodeError) as error:
            result = {'status':'submission_failure','format_valid':False,'feasible':False,'safe_tir':0.,'reason':str(error)}
        else:
            try:
                result = verify_design(instance,design,seeds,path/'native-traces.npz')
                result['status'] = 'verified'
                result['reason'] = None if result['feasible'] else 'safety_constraint_failed'
                result['native_traces_sha256'] = digest(path/'native-traces.npz')
            except (ValueError,FloatingPointError,RuntimeError) as error:
                result = {'status':'simulation_failure','format_valid':True,'feasible':False,'safe_tir':0.,'reason':str(error)}
    dump(path/'score.json',result)
    return result


def export_trial(path, destination):
    path = Path(path); destination = Path(destination)
    meta = strict_json(path/'metadata.json'); score = strict_json(path/'score.json')
    out = destination/meta['trial_id']; out.mkdir(parents=True,exist_ok=False)
    public_score = {k:v for k,v in score.items() if k != 'rows'}
    # Store hashes of private evidence, never hidden cases, seeds, per-patient
    # traces, or the sealed agent transcript. Development artifacts are open.
    record = {**meta, 'score':public_score, 'billing_cost':None,
              'billing_note':'Actual provider billing was not available; token usage is API-reported.',
              'private_evidence_sha256':{p.name:digest(p) for p in path.iterdir() if p.is_file()}}
    dump(out/'result.json',record)
    if meta['split'] == 'development':
        for name in ['design.json','search.py','rationale.md','native-traces.npz','score.json','baseline-tool.json']:
            if (path/name).exists(): shutil.copyfile(path/name,out/name)
        if (path/'transcript.json').exists():
            messages = strict_json(path/'transcript.json')
            public = [{k:v for k,v in m.items() if k in {'role','content','tool_calls','tool_call_id'}} for m in messages]
            dump(out/'transcript.json',public)
    return record


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('trial'); parser.add_argument('--export')
    args = parser.parse_args(); result = score_trial(args.trial)
    if args.export: export_trial(args.trial,args.export)
    print(json.dumps({k:v for k,v in result.items() if k != 'rows'}),flush=True)


if __name__ == '__main__': main()

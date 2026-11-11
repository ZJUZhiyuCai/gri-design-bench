import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from gri_bench.publication import public_score


@pytest.mark.parametrize('status,reason',[
    ('submission_failure','relative_leak outside [0.123456789, 0.987654321]'),
    ('submission_failure','Malformed input containing hidden input 0.123456789'),
    ('simulation_failure','Private patient input 0.123456789 failed'),
    ('infrastructure_error','Private runtime input 0.123456789 failed'),
])
def test_sealed_diagnostics_do_not_disclose_inputs_or_change_scores(status,reason):
    raw={'status':status,'reason':reason,'safe_tir':0.,'feasible':False,'format_valid':False}
    before=copy.deepcopy(raw)
    public=public_score(raw,'sealed')
    assert '0.123456789' not in json.dumps(public)
    assert '0.987654321' not in json.dumps(public)
    assert {k:v for k,v in public.items() if k!='reason'}=={k:v for k,v in raw.items() if k!='reason'}
    assert raw==before


def test_open_diagnostics_and_sealed_safety_scores_are_preserved():
    raw={'status':'submission_failure','reason':'relative_leak outside [0.12, 0.98]','safe_tir':0.}
    assert public_score(raw,'development')==raw
    verified={'status':'verified','reason':'safety_constraint_failed','safe_tir':0.,'mean_tir':72.,'rows':['private detail']}
    assert public_score(verified,'sealed')=={k:v for k,v in verified.items() if k!='rows'}


def test_complete_export_archives_originals_and_is_idempotent(tmp_path,monkeypatch):
    source=Path(__file__).resolve().parents[1]/'scripts/sanitize_repetition_exports.py'
    spec=importlib.util.spec_from_file_location('sanitizer',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'ROOT',tmp_path)
    tags=['R1','R2','R3'];models=['A','B','C'];cases=[f'{prefix}-{i}' for prefix in ['dev','sealed'] for i in range(6)]
    jobs=[{'tag':tag,'model':model,'case':case} for tag in tags for model in models for case in cases]
    experiment=tmp_path/'experiments/repeats-2026-11-11';experiment.mkdir(parents=True)
    (experiment/'plan.json').write_text(json.dumps({'tags':tags,'jobs':jobs}))
    changed=None
    for job in jobs:
        split='development' if job['case'].startswith('dev') else 'sealed'
        score={'status':'verified','feasible':True,'safe_tir':75.,'reason':None}
        target=job=={'tag':'R1','model':'A','case':'sealed-0'}
        if target:score={'status':'submission_failure','feasible':False,'safe_tir':0.,'reason':'relative_leak outside [0.123456789, 0.987654321]'}
        trial=job['case']+'__'+job['model']
        private=tmp_path/'private/runs'/job['tag']/trial;private.mkdir(parents=True)
        (private/'score.json').write_text(json.dumps(score))
        destination=tmp_path/'results'/job['tag']/trial;destination.mkdir(parents=True)
        record={'instance_id':job['case'],'requested_model':job['model'],'trial_id':trial,'split':split,'score':score}
        path=destination/'result.json';path.write_text(json.dumps(record))
        if target:changed=(path,path.read_bytes(),private/'score.json',(private/'score.json').read_bytes())
    module.main()
    path,original,private_score,score_bytes=changed
    report_path=tmp_path/'results/repetitions-2026-11-11/publication-redactions.json'
    report=json.loads(report_path.read_text());assert report['redacted_exports']==1
    archived=tmp_path/'private/original-exports/R1'/path.parent.name/'result.json'
    assert archived.read_bytes()==original and private_score.read_bytes()==score_bytes
    published=path.read_bytes();assert b'0.123456789' not in published
    item=report['records'][0]
    assert item['original_export_sha256']==hashlib.sha256(original).hexdigest()
    assert item['published_result_sha256']==hashlib.sha256(published).hexdigest()
    module.main()
    assert path.read_bytes()==published and json.loads(report_path.read_text())==report
    report_path.unlink()
    module.main()
    assert path.read_bytes()==published and json.loads(report_path.read_text())==report
    # A changed numeric score is rejected without overwriting it or the archive.
    tampered=json.loads(published);tampered['score']['safe_tir']=1.
    path.write_text(json.dumps(tampered));tampered_bytes=path.read_bytes()
    with pytest.raises(AssertionError):module.main()
    assert path.read_bytes()==tampered_bytes and archived.read_bytes()==original

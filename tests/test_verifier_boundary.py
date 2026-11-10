import json
from pathlib import Path
import pytest
from gri_bench.runner import digest, dump
from gri_bench.evaluate import score_trial


def submission(path, design):
    path.mkdir()
    dump(path/'design.json',design)
    # Must never run on the verifier host, even when it has valid syntax.
    (path/'search.py').write_text("raise RuntimeError('SUBMITTED CODE MUST NOT RUN')\n")
    (path/'rationale.md').write_text('Claims perfect safety and 100% TIR; verifier must ignore prose.')
    dump(path/'metadata.json',{'instance_id':'dev-01','status':'submitted',
         'artifact_sha256':{n:digest(path/n) for n in ['design.json','search.py','rationale.md']}})


def test_verifier_recomputes_instead_of_executing_or_trusting_prose(tmp_path):
    path=tmp_path/'valid'
    submission(path,{'mode':'constant','parameters':{'theta_c':0.,'theta_L':4.}})
    score=score_trial(path)
    assert score['format_valid'] and score['status']=='verified'
    assert score['trajectories']==18
    assert len(score['rows'])==18
    assert score['native_integrator']=='simglucose-dopri5'
    assert score['mean_tir']<100  # prose claims do not enter the score
    with pytest.raises(FileExistsError):score_trial(path)


def test_tampered_submission_and_extra_score_key_rejected(tmp_path):
    path=tmp_path/'tampered'
    submission(path,{'mode':'constant','parameters':{'theta_c':0.,'theta_L':4.}})
    (path/'design.json').write_text('{}')
    score=score_trial(path)
    assert score['safe_tir']==0 and 'changed' in score['reason']
    path=tmp_path/'claims'
    submission(path,{'mode':'constant','parameters':{'theta_c':0.,'theta_L':4.},'score':100})
    assert score_trial(path)['safe_tir']==0

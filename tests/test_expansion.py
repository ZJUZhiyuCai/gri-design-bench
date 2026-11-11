from collections import Counter
import copy
import hashlib
import json

import pytest

from gri_bench import expansion


def plan_fixture():
    models = [f'provider/model-{i}' for i in range(6)]
    return {'models': models, 'cases': expansion.CASES, 'tags': expansion.TAGS,
            'jobs': expansion.scheduled_jobs(models), 'new_agent_trials': 216,
            'repetitions_per_model_case': 3, 'execution_profile': 'strict-token-accounting-v1',
            'max_concurrent_trials': 2, 'max_concurrent_graders': 2}


def test_full_matrix_has_balanced_coverage_and_rejects_replaced_attempt():
    plan = plan_fixture()
    expansion.validate_plan(plan)
    assert set(Counter(j['model'] for j in plan['jobs']).values()) == {36}
    assert set(Counter(j['tag'] for j in plan['jobs']).values()) == {72}
    assert len({(j['model'], j['tag'], j['case']) for j in plan['jobs']}) == 216
    for model in plan['models']:
        positions = Counter(i % 6 for i, j in enumerate(plan['jobs']) if j['model'] == model)
        assert set(positions.values()) == {6}
    plan['jobs'][0] = plan['jobs'][1]
    with pytest.raises(AssertionError):
        expansion.validate_plan(plan)


@pytest.mark.parametrize('excluded', ['provider/claude-sonnet-5-5', 'opus/anything', 'auto/qwen3.8-27b'])
def test_excluded_or_automatic_routes_cannot_enter_the_matrix(excluded):
    plan = plan_fixture()
    plan['models'][0] = excluded
    plan['jobs'] = expansion.scheduled_jobs(plan['models'])
    with pytest.raises(AssertionError):
        expansion.validate_plan(plan)


def test_resume_preserves_completed_attempts_and_stops_on_unfinished_attempt(tmp_path, monkeypatch):
    monkeypatch.setattr(expansion, 'ROOT', tmp_path)
    plan = plan_fixture()
    first = expansion.trial_path(plan['jobs'][0])
    first.mkdir(parents=True)
    (first / 'metadata.json').write_text(json.dumps({'status': 'submission_failure'}))
    assert len(expansion.pending_jobs(plan)) == 215
    assert plan['jobs'][0] not in expansion.pending_jobs(plan)
    second = expansion.trial_path(plan['jobs'][1])
    second.mkdir(parents=True)
    with pytest.raises(RuntimeError, match='never silently rerun'):
        expansion.pending_jobs(plan)
    assert json.loads((first / 'metadata.json').read_text())['status'] == 'submission_failure'


def test_prior_result_changes_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(expansion, 'ROOT', tmp_path)
    experiment = tmp_path / 'experiment'
    experiment.mkdir()
    monkeypatch.setattr(expansion, 'EXPERIMENT', experiment)
    monkeypatch.setattr(expansion, 'verify_runtime_lock', lambda: None)
    monkeypatch.setattr(expansion, 'verify_repeat_lock', lambda tag: None)
    original = tmp_path / 'previous.json'
    original.write_text('{"score":42}\n')
    snapshot = {'files': {'previous.json': hashlib.sha256(original.read_bytes()).hexdigest()}}
    (experiment / 'prior-result-hashes.json').write_text(json.dumps(snapshot))
    (experiment / 'plan.json').write_text(json.dumps(plan_fixture()))
    (experiment / 'lock.json').write_text(json.dumps({'files': {}}))
    expansion.verify_expansion_freeze()
    original.write_text('{"score":43}\n')
    with pytest.raises(AssertionError, match='Earlier result changed'):
        expansion.verify_expansion_freeze()


def test_sealed_export_is_atomic_recoverable_and_preserves_raw_scores(tmp_path, monkeypatch):
    monkeypatch.setattr(expansion, 'ROOT', tmp_path)
    tag = 'test-round'
    trial = 'sealed-01__provider__model__seed20261111'
    folder = tmp_path / 'private/runs' / tag / trial
    folder.mkdir(parents=True)
    meta = {'trial_id': trial, 'instance_id': 'sealed-01', 'split': 'sealed', 'status': 'submitted'}
    score = {'status': 'submission_failure', 'format_valid': False, 'feasible': False,
             'safe_tir': 0., 'reason': 'relative_leak outside [0.123456789, 0.987654321]'}
    (folder / 'metadata.json').write_text(json.dumps(meta))
    (folder / 'score.json').write_text(json.dumps(score))
    score_bytes = (folder / 'score.json').read_bytes()
    destination = tmp_path / 'results' / tag / trial
    real_dump = expansion.dump

    def fail_before_publication(path, value):
        raise RuntimeError('Simulated export interruption')

    monkeypatch.setattr(expansion, 'dump', fail_before_publication)
    with pytest.raises(RuntimeError, match='Simulated export interruption'):
        expansion.export_safe_trial(folder, tag)
    assert not destination.exists()
    assert (folder / 'score.json').read_bytes() == score_bytes
    monkeypatch.setattr(expansion, 'dump', real_dump)
    record = expansion.export_safe_trial(folder, tag)
    assert record['score']['safe_tir'] == 0. and not record['score']['feasible']
    assert '0.123456789' not in (destination / 'result.json').read_text()
    assert sorted(p.name for p in destination.iterdir()) == ['result.json']
    archive = tmp_path / 'private/original-exports' / tag / trial / 'result.json'
    assert json.loads(archive.read_text())['score'] == score
    published_bytes = (destination / 'result.json').read_bytes()
    receipt = tmp_path / 'private/expansion-publication' / tag / (trial + '.json')
    receipt.unlink()
    expansion.export_safe_trial(folder, tag)
    assert receipt.exists() and (destination / 'result.json').read_bytes() == published_bytes
    altered = copy.deepcopy(record)
    altered['score']['safe_tir'] = 1.
    (destination / 'result.json').write_text(json.dumps(altered))
    with pytest.raises(AssertionError, match='refusing overwrite'):
        expansion.export_safe_trial(folder, tag)
    assert (folder / 'score.json').read_bytes() == score_bytes

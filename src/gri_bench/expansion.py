"""Additional model matrix using the unchanged, frozen repetition runner."""
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from .evaluate import export_trial, score_trial
from .publication import public_score
from .repeat_runner import PROFILE, run_trial, verify_repeat_lock
from .runner import ROOT, digest, dump, verify_runtime_lock

EXPERIMENT = ROOT / 'experiments/expansion-2026-11-11'
REPORT = ROOT / 'results/expansion-2026-11-11'
CASES = [f'{prefix}-{i:02d}' for prefix in ('dev', 'sealed') for i in range(1, 7)]
TAGS = [f'repeat-20261111-expand-r{i}' for i in range(1, 4)]


def scheduled_jobs(models):
    jobs = []
    for ci, case in enumerate(CASES):
        for ri, tag in enumerate(TAGS):
            shift = (ci + ri) % len(models)
            for model in models[shift:] + models[:shift]:
                jobs.append({'tag': tag, 'case': case, 'model': model})
    return jobs


def validate_plan(plan):
    models = plan['models']
    assert len(models) == len(set(models)) == 6, 'Require six distinct new routes'
    for model in models:
        assert '/' in model and not any(s in model.lower() for s in ('claude', 'opus')), 'Excluded model family'
        assert not model.startswith(('auto/', 'group/', 'hub/group/')), 'Require an explicit route'
    assert plan['cases'] == CASES and plan['tags'] == TAGS
    assert plan['jobs'] == scheduled_jobs(models), 'Missing, duplicated or reordered planned jobs'
    assert len(plan['jobs']) == plan['new_agent_trials'] == 216
    assert plan['repetitions_per_model_case'] == 3
    assert plan['execution_profile'] == PROFILE
    assert plan['max_concurrent_trials'] == plan['max_concurrent_graders'] == 2
    return plan


def verify_expansion_freeze(require_revision=False, preserve_results=True):
    plan = validate_plan(json.loads((EXPERIMENT / 'plan.json').read_text()))
    verify_runtime_lock()
    verify_repeat_lock(plan['tags'][0])
    lock = json.loads((EXPERIMENT / 'lock.json').read_text())
    for name, expected in lock['files'].items():
        assert digest(ROOT / name) == expected, 'Frozen expansion file changed: ' + name
    if preserve_results:
        snapshot = json.loads((EXPERIMENT / 'prior-result-hashes.json').read_text())
        for name, expected in snapshot['files'].items():
            assert digest(ROOT / name) == expected, 'Earlier result changed: ' + name
    if require_revision:
        expected = subprocess.check_output(['git', 'rev-parse', plan['plan_tag'] + '^{}'], cwd=ROOT, text=True).strip()
        actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        assert actual == expected, 'Scored runs must use the committed expansion plan revision'
    return plan


def trial_path(job):
    label = job['case'] + '__' + job['model'].replace('/', '__') + '__seed20261111'
    return ROOT / 'private/runs' / job['tag'] / label


def pending_jobs(plan):
    pending = []
    for job in plan['jobs']:
        path = trial_path(job)
        if path.exists():
            meta = path / 'metadata.json'
            if meta.exists() and json.loads(meta.read_text()).get('status'):
                continue
            raise RuntimeError('Existing unfinished attempt must be accounted for, never silently rerun: ' + str(path))
        pending.append(job)
    return pending


def run_one(job, source_commit):
    current = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    assert current == source_commit, 'Source changed during the scored matrix'
    return run_trial(job['case'], job['model'], job['tag'])


def run_matrix():
    plan = verify_expansion_freeze(require_revision=True)
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    image = subprocess.check_output(['docker', '--context', 'colima-etbench', 'image', 'inspect', 'gri-bench:0.1.1', '--format', '{{.Id}}'], text=True).strip()
    assert image == json.loads((ROOT / 'contract/runtime-lock.json').read_text())['pilot_image_id']
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_one, job, source) for job in pending_jobs(plan)]
        for future in as_completed(futures):
            future.result()


def export_safe_trial(path, tag):
    """Retain raw exports privately; publish only a sanitized atomic copy."""
    path = Path(path)
    meta = json.loads((path / 'metadata.json').read_text())
    score = json.loads((path / 'score.json').read_text())
    stage_root = ROOT / 'private/expansion-exports' / tag
    staged = stage_root / path.name
    if not staged.exists():
        export_trial(path, stage_root)
    original = (staged / 'result.json').read_bytes()
    record = json.loads(original)
    assert all(record[k] == v for k, v in meta.items()), 'Raw export metadata changed'
    assert record['score'] == {k: v for k, v in score.items() if k != 'rows'}, 'Raw export score changed'
    safe_score = public_score(score, meta['split'])
    changed = record['score'] != safe_score
    if changed:
        assert meta['split'] == 'sealed'
        assert {k: v for k, v in record['score'].items() if k != 'reason'} == {k: v for k, v in safe_score.items() if k != 'reason'}
        archive = ROOT / 'private/original-exports' / tag / path.name / 'result.json'
        archive.parent.mkdir(parents=True, exist_ok=True)
        if archive.exists():
            assert archive.read_bytes() == original, 'Original export archive changed'
        else:
            archive.write_bytes(original)
    record['score'] = safe_score
    destination = ROOT / 'results' / tag / path.name
    if destination.exists():
        assert json.loads((destination / 'result.json').read_text()) == record, 'Published result changed; refusing overwrite'
    else:
        temp_root = ROOT / 'private/expansion-publication-staging'
        temp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as temporary:
            safe = Path(temporary) / path.name
            shutil.copytree(staged, safe)
            dump(safe / 'result.json', record)
            destination.parent.mkdir(parents=True, exist_ok=True)
            safe.rename(destination)
    if meta['split'] == 'sealed':
        assert sorted(p.name for p in destination.iterdir()) == ['result.json']
    receipt = {'tag': tag, 'trial_id': path.name, 'redacted': changed,
               'changed_fields': ['score.reason'] if changed else [],
               'original_export_sha256': hashlib.sha256(original).hexdigest(),
               'private_score_sha256': digest(path / 'score.json'),
               'published_result_sha256': digest(destination / 'result.json')}
    if changed:
        receipt['published_reason'] = record['score']['reason']
    receipt_path = ROOT / 'private/expansion-publication' / tag / (path.name + '.json')
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    if receipt_path.exists():
        assert json.loads(receipt_path.read_text()) == receipt
    else:
        dump(receipt_path, receipt)
    return record


def grade_one(path, tag):
    if not (path / 'score.json').exists():
        score_trial(path)
    record = export_safe_trial(path, tag)
    return {'tag': tag, 'trial': path.name, 'status': record['score']['status'],
            'feasible': record['score']['feasible'], 'safe_tir': record['score']['safe_tir']}


def grade_matrix():
    plan = verify_expansion_freeze(require_revision=True)
    seen = set()
    futures = {}
    finished = 0
    with ProcessPoolExecutor(max_workers=2) as pool:
        while finished < len(plan['jobs']):
            for job in plan['jobs']:
                path = trial_path(job)
                if path in seen:
                    continue
                try:
                    meta = json.loads((path / 'metadata.json').read_text())
                except (FileNotFoundError, json.JSONDecodeError):
                    continue
                if not meta.get('status'):
                    continue
                seen.add(path)
                futures[pool.submit(grade_one, path, job['tag'])] = path
            for future in list(futures):
                if future.done():
                    print(json.dumps(future.result()), flush=True)
                    finished += 1
                    del futures[future]
            time.sleep(.5)

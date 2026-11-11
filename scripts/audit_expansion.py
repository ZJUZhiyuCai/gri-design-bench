"""Independent expansion audit; never execute submitted search code."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import numpy as np

from gri_bench.expansion import EXPERIMENT, REPORT, trial_path, verify_expansion_freeze
from gri_bench.publication import public_score
from gri_bench.repeat_runner import SYSTEM_PROMPT
from gri_bench.runner import ROOT, digest, dump, load_case

spec = importlib.util.spec_from_file_location('frozen_repeat_audit', ROOT / 'scripts/audit_repetitions.py')
frozen_audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frozen_audit)


def audit_native(folder, score):
    if score['status'] != 'verified':
        assert not score['feasible'] and score['safe_tir'] in (0., None)
        return {'verified': 0, 'failed': 1, 'safety_failed': 0, 'trajectories': 0, 'max_error': 0.}
    archive = folder / 'native-traces.npz'
    assert digest(archive) == score['native_traces_sha256']
    assert len(score['rows']) == 18
    computed = []
    max_error = 0.
    with np.load(archive, allow_pickle=False) as data:
        assert len(data.files) == 36
        for i, row in enumerate(score['rows']):
            trace, minute = data[f'trace_{i:02d}'], data[f'minute_{i:02d}']
            assert trace.shape == (1440, 5) and minute.shape == (4321,)
            assert np.isfinite(trace).all() and np.isfinite(minute).all()
            glucose = trace[480:, 0]
            metrics = {'tir': 100 * np.count_nonzero((glucose >= 70) & (glucose <= 180)) / len(glucose),
                       'tbr70': 100 * np.count_nonzero(glucose < 70) / len(glucose),
                       'tbr54': 100 * np.count_nonzero(glucose < 54) / len(glucose),
                       'minimum': float(minute.min()), 'mean_glucose': float(np.sum(glucose) / len(glucose))}
            for name, value in metrics.items():
                error = abs(value - row['metrics'][name])
                max_error = max(max_error, error)
                assert error < 1e-9, 'Native trajectory metric mismatch'
            computed.append(metrics)
    feasible = all(r['tbr70'] <= 4 and r['tbr54'] <= 1 and r['minimum'] >= 40 for r in computed)
    mean_tir = sum(r['tir'] for r in computed) / 18
    assert score['feasible'] == feasible
    assert abs(score['mean_tir'] - mean_tir) < 1e-9
    assert abs(score['safe_tir'] - (mean_tir if feasible else 0.)) < 1e-9
    return {'verified': 1, 'failed': 0, 'safety_failed': int(not feasible),
            'trajectories': 18, 'max_error': max_error}


def audit_publication(folder, tag, meta, score):
    public_folder = ROOT / 'results' / tag / folder.name
    published = public_folder / 'result.json'
    record = json.loads(published.read_text())
    assert all(record[k] == v for k, v in meta.items()), 'Public metadata differs from raw metadata'
    assert record['score'] == public_score(score, meta['split'])
    staged = ROOT / 'private/expansion-exports' / tag / folder.name
    raw_bytes = (staged / 'result.json').read_bytes()
    raw = json.loads(raw_bytes)
    assert raw['score'] == {k: v for k, v in score.items() if k != 'rows'}
    expected = {**raw, 'score': public_score(score, meta['split'])}
    assert record == expected, 'Publication changed more than the score diagnostic'
    receipt = json.loads((ROOT / 'private/expansion-publication' / tag / (folder.name + '.json')).read_text())
    changed = raw['score'] != record['score']
    assert receipt['redacted'] == changed
    assert receipt['tag'] == tag and receipt['trial_id'] == folder.name
    assert receipt['changed_fields'] == (['score.reason'] if changed else [])
    assert receipt['original_export_sha256'] == hashlib.sha256(raw_bytes).hexdigest()
    assert receipt['private_score_sha256'] == digest(folder / 'score.json')
    assert receipt['published_result_sha256'] == digest(published)
    if changed:
        assert meta['split'] == 'sealed'
        original = ROOT / 'private/original-exports' / tag / folder.name / 'result.json'
        assert original.read_bytes() == raw_bytes
        assert receipt['published_reason'] == record['score']['reason']
        before = dict(raw['score'])
        before['reason'] = record['score']['reason']
        assert before == record['score'], 'Numeric score changed during publication'
    assert {p.name for p in public_folder.iterdir()} == {p.name for p in staged.iterdir()}
    if meta['split'] == 'sealed':
        assert {p.name for p in public_folder.iterdir()} == {'result.json'}
    else:
        for p in public_folder.iterdir():
            if p.name != 'result.json':
                assert digest(p) == digest(staged / p.name), 'Public development artifact changed'
        if (folder / 'transcript.json').exists():
            private_messages = json.loads((folder / 'transcript.json').read_text())
            expected_messages = [{k: v for k, v in m.items() if k in {'role', 'content', 'tool_calls', 'tool_call_id'}} for m in private_messages]
            assert json.loads((public_folder / 'transcript.json').read_text()) == expected_messages
    evidence = record['private_evidence_sha256']
    assert set(evidence) == {p.name for p in folder.iterdir() if p.is_file()}
    for name, expected_hash in evidence.items():
        assert Path(name).name == name and digest(folder / name) == expected_hash, 'Private evidence hash mismatch'
    return record, receipt, len(evidence)


def audit_response_metadata(folder, meta):
    responses = [json.loads(path.read_text()) for path in sorted(folder.glob('response-*.json'))]
    assert [r.get('model') for r in responses] == meta['returned_models'], 'Response model labels differ from metadata'
    assert [r.get('usage', {}) for r in responses] == meta['usage'], 'Response usage differs from metadata'
    assert not any(token in str(r.get('model')).lower() for r in responses for token in ('claude', 'opus'))
    return len(responses)


def main():
    plan = verify_expansion_freeze()
    source = subprocess.check_output(['git', 'rev-parse', plan['plan_tag'] + '^{}'], cwd=ROOT, text=True).strip()
    image = json.loads((ROOT / 'contract/runtime-lock.json').read_text())['pilot_image_id']
    expected = {(j['tag'], j['case'], j['model']) for j in plan['jobs']}
    actual = set()
    metadata, ledgers, native, receipts = [], [], [], []
    prompts = evidence_count = response_count = 0
    by_tag = {tag: [] for tag in plan['tags']}
    for tag in plan['tags']:
        paths = sorted((ROOT / 'private/runs' / tag).glob('*/metadata.json'))
        public_paths = sorted((ROOT / 'results' / tag).glob('*/result.json'))
        assert len(paths) == len(public_paths) == 72
        for p in paths:
            folder = p.parent
            meta = json.loads(p.read_text())
            key = (tag, meta['instance_id'], meta['requested_model'])
            assert key in expected and key not in actual
            actual.add(key)
            assert folder == trial_path({'tag': tag, 'case': meta['instance_id'], 'model': meta['requested_model']})
            assert meta['source_commit'] == source and meta['image_id'] == image
            assert meta['execution_profile'] == 'strict-token-accounting-v1' and meta['repetition_tag'] == tag
            assert meta['contract_sha256'] == digest(ROOT / 'contract/contract.json')
            assert meta['system_prompt_sha256'] == hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()
            assert meta.get('status')
            assert not any(token in str(label).lower() for label in meta['returned_models'] for token in ('claude', 'opus'))
            response_count += audit_response_metadata(folder, meta)
            for name, expected_hash in meta.get('artifact_sha256', {}).items():
                assert digest(folder / name) == expected_hash
            score = json.loads((folder / 'score.json').read_text())
            _, receipt, count = audit_publication(folder, tag, meta, score)
            receipts.append(receipt)
            evidence_count += count
            transcript = folder / 'transcript.json'
            if transcript.exists():
                messages = json.loads(transcript.read_text())
                instance, _ = load_case(meta['instance_id'])
                assert messages[0] == {'role': 'system', 'content': SYSTEM_PROMPT}
                assert messages[1] == {'role': 'user', 'content': (ROOT / 'docs/AGENT_TASK.md').read_text() + '\n\nYOUR INSTANCE:\n' + json.dumps(instance)}
                prompts += 1
            else:
                assert meta['status'] != 'submitted'
            ledgers.append(frozen_audit.check_ledger(meta, folder))
            check = audit_native(folder, score)
            native.append(check)
            by_tag[tag].append(check)
            metadata.append(meta)
    assert actual == expected and len(actual) == 216
    for tag, rows in by_tag.items():
        dump(ROOT / 'results' / tag / 'audit.json', {'passed': True, 'attempts': len(rows),
             'verified_designs': sum(r['verified'] for r in rows), 'failed_attempts_retained': sum(r['failed'] for r in rows),
             'safety_failures_retained': sum(r['safety_failed'] for r in rows),
             'native_trajectories_recomputed': sum(r['trajectories'] for r in rows),
             'maximum_metric_error': max(r['max_error'] for r in rows)})
    changed = [{k: v for k, v in r.items() if k != 'redacted'} for r in receipts if r['redacted']]
    REPORT.mkdir(parents=True, exist_ok=True)
    dump(REPORT / 'publication-redactions.json', {'scope': 'Expansion exports only; raw exports were staged privately before publication.',
         'modified_score_values': 0, 'redacted_exports': len(changed), 'all_export_receipts_verified': len(receipts), 'records': changed})
    report = {'passed': True, 'planned_and_audited_attempts': len(actual), 'source_commit': source,
              'prior_result_files_unchanged': len(json.loads((EXPERIMENT / 'prior-result-hashes.json').read_text())['files']),
              'original_runtime_files_unchanged': 32, 'earlier_repetition_files_unchanged': 11,
              'expansion_files_unchanged': len(json.loads((EXPERIMENT / 'lock.json').read_text())['files']),
              'saved_initial_prompts_verified': prompts, 'private_evidence_hashes_verified': evidence_count,
              'saved_response_model_and_usage_records_verified': response_count,
              'publication_receipts_verified': len(receipts), 'sealed_diagnostic_redactions_verified': len(changed),
              'api_requests_accounted': sum(x['attempts'] for x in ledgers),
              'maximum_charged_completion_tokens': max(x['charged'] for x in ledgers),
              'provider_usage_overrun_requests': sum(x['provider_usage_violations'] for x in ledgers),
              'unexpected_infrastructure_failure_reservations': sum(x['unexpected_infrastructure_failure_reservations'] for x in ledgers),
              'verified_designs': sum(x['verified'] for x in native),
              'submission_or_technical_failures_retained': sum(x['failed'] for x in native),
              'safety_failures_retained': sum(x['safety_failed'] for x in native),
              'native_trajectories_recomputed': sum(x['trajectories'] for x in native),
              'maximum_metric_error': max(x['max_error'] for x in native),
              'excluded_model_labels_observed': 0,
              'note': 'Every planned attempt retained. Native arrays recomputed independently; no submitted code executed. Raw private scores and prior releases preserved.'}
    for field, limit in [('cpu_seconds', 30), ('wall_seconds', 360), ('tool_wall_seconds', 90)]:
        report['maximum_recorded_' + field] = max(float(m.get(field) or 0.) for m in metadata)
        report[field + '_limit_excess_count'] = sum(float(m.get(field) or 0.) > limit for m in metadata)
    dump(REPORT / 'audit.json', report)
    print(json.dumps(report))


if __name__ == '__main__':
    main()

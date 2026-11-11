import copy
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from gri_bench.expansion_analysis import build_analysis, load_cohort
from gri_bench.runner import digest


def records_fixture():
    cohorts = {'earlier_strict_batch': [f'old/m{i}' for i in range(3)],
               'six_route_expansion': [f'new/m{i}' for i in range(6)]}
    # Multiples of five lie on the native evaluator's integer-sample TIR grid.
    values = [80., 75., 40., 70., 70., 65., 60., 55., 50.]
    records = []
    offset = 0
    for cohort, models in cohorts.items():
        for mi, model in enumerate(models):
            for repeat in (1, 2, 3):
                for split, prefix in [('development', 'dev'), ('sealed', 'sealed')]:
                    for i in range(1, 7):
                        records.append({'requested_model': model, 'instance_id': f'{prefix}-{i:02d}',
                            'split': split, '_cohort': cohort, '_repeat': repeat, '_tag': f'{cohort}-r{repeat}',
                            'execution_profile': 'strict-token-accounting-v1', 'source_commit': cohort,
                            'score': {'status': 'verified', 'feasible': True, 'format_valid': True, 'safe_tir': values[offset + mi]},
                            'usage': [{'completion_tokens': 100}], 'charged_completion_tokens': 100,
                            'model_calls': 1, 'cpu_seconds': 10., 'tool_wall_seconds': 12., 'wall_seconds': 20., 'api_errors': []})
        offset += len(models)
    failed = next(r for r in records if (r['requested_model'], r['_repeat'], r['instance_id']) == ('new/m5', 1, 'sealed-01'))
    failed['score'] = {'status': 'infrastructure_error', 'feasible': False, 'format_valid': False, 'safe_tir': None}
    excess = next(r for r in records if (r['requested_model'], r['_repeat'], r['instance_id']) == ('new/m0', 2, 'sealed-02'))
    excess['cpu_seconds'] = 30.2
    return records, cohorts


def test_complete_analysis_keeps_failures_ties_and_separate_batch_ranks():
    records, cohorts = records_fixture()
    untouched = copy.deepcopy(records)
    result = build_analysis(records, cohorts)
    assert records == untouched
    assert result['new_attempts'] == 216 and result['combined_strict_profile_attempts'] == 324
    rows = {r['model']: r for r in result['rows'] if r['split'] == 'sealed'}
    assert rows['new/m0']['rank'] == rows['new/m1']['rank'] == 3.5
    assert rows['new/m0']['within_cohort_round_ranks'] == [1.5, 1.5, 1.5]
    assert rows['new/m0']['within_cohort_rank_denominator'] == 6
    assert rows['old/m0']['within_cohort_rank_denominator'] == 3
    assert rows['new/m5']['attempts'] == 18 and rows['new/m5']['feasible_attempts'] == 17
    assert rows['new/m5']['mean_safe_tir'] == pytest.approx(17 * 50 / 18)
    assert rows['new/m5']['infrastructure_failures'] == 1
    assert rows['new/m5']['cases_feasible_all_three'] == 5
    assert rows['new/m5']['cases_feasible_some_repetitions'] == 1
    strict = {r['model']: r for r in result['resource_sensitivity']['rows'] if r['split'] == 'sealed'}
    assert strict['new/m0']['attempts'] == 18 and strict['new/m0']['feasible_attempts'] == 17
    assert strict['new/m0']['mean_safe_tir'] == pytest.approx(17 * 70 / 18)
    assert strict['old/m2']['rank'] < strict['new/m0']['rank'], 'Feasibility must outrank a higher TIR mean'
    assert strict['new/m0']['within_cohort_round_ranks'] == [1.5, 6, 1.5]
    assert result['resource_sensitivity']['ordering_matches_primary_by_round']['six_route_expansion']['sealed'] == [True, False, True]
    assert result['resource_sensitivity']['ordering_matches_primary_by_round']['earlier_strict_batch']['sealed'] == [True, True, True]
    assert len(result['paired_comparisons_new_cohort_only']) == 30
    for row in result['paired_comparisons_new_cohort_only']:
        assert row['model_a'].startswith('new/') and row['model_b'].startswith('new/')
        assert row['a_wins'] + row['b_wins'] + row['ties'] == 18
    for invalid in (records[:-1], records[:-1] + [records[0]]):
        with pytest.raises(AssertionError):
            build_analysis(invalid, cohorts)


def test_public_loader_refuses_partial_or_duplicate_attempts(tmp_path):
    records, cohorts = records_fixture()
    rows = [r for r in records if r['_cohort'] == 'six_route_expansion']
    tags = sorted({r['_tag'] for r in rows})
    plan = {'tags': tags, 'jobs': [{'tag': r['_tag'], 'case': r['instance_id'], 'model': r['requested_model']} for r in rows]}
    for r in rows[:-1]:
        path = tmp_path / 'results' / r['_tag'] / (r['instance_id'] + '__' + r['requested_model'].replace('/', '__')) / 'result.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({k: v for k, v in r.items() if not k.startswith('_')}))
    with pytest.raises(AssertionError, match='Incomplete'):
        load_cohort(plan, 'six_route_expansion', tmp_path)
    last = rows[-1]
    path = tmp_path / 'results' / last['_tag'] / 'last' / 'result.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({k: v for k, v in last.items() if not k.startswith('_')}))
    assert len(load_cohort(plan, 'six_route_expansion', tmp_path)) == 216
    duplicate = tmp_path / 'results' / last['_tag'] / 'duplicate' / 'result.json'
    duplicate.parent.mkdir()
    duplicate.write_bytes(path.read_bytes())
    with pytest.raises(AssertionError, match='Duplicate'):
        load_cohort(plan, 'six_route_expansion', tmp_path)


def test_native_recomputation_detects_a_metric_disagreement(tmp_path):
    source = Path(__file__).resolve().parents[1] / 'scripts/audit_expansion.py'
    spec = importlib.util.spec_from_file_location('audit_expansion_test', source)
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    arrays = {}
    for i in range(18):
        trace = np.zeros((1440, 5));trace[:, 0] = 100.
        arrays[f'trace_{i:02d}'] = trace
        arrays[f'minute_{i:02d}'] = np.full((4321,), 100.)
    path = tmp_path / 'native-traces.npz'
    np.savez_compressed(path, **arrays)
    metrics = {'tir': 100., 'tbr70': 0., 'tbr54': 0., 'minimum': 100., 'mean_glucose': 100.}
    score = {'status': 'verified', 'feasible': True, 'safe_tir': 100., 'mean_tir': 100.,
             'native_traces_sha256': digest(path), 'rows': [{'metrics': dict(metrics)} for _ in range(18)]}
    assert audit.audit_native(tmp_path, score)['trajectories'] == 18
    score['rows'][0]['metrics']['tir'] = 99.
    with pytest.raises(AssertionError, match='metric mismatch'):
        audit.audit_native(tmp_path, score)

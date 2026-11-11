"""Descriptive comparison across fixed-case chronological model batches."""
import collections
import importlib.util
import itertools
import json
from statistics import mean, stdev

from .runner import ROOT

spec = importlib.util.spec_from_file_location('frozen_repeat_analysis', ROOT / 'scripts/analyze_repetitions.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def load_cohort(plan, cohort, root=ROOT):
    expected = {(j['tag'], j['case'], j['model']) for j in plan['jobs']}
    lookup = {}
    for repeat, tag in enumerate(plan['tags'], 1):
        for path in (root / 'results' / tag).glob('*/result.json'):
            record = json.loads(path.read_text())
            key = (tag, record['instance_id'], record['requested_model'])
            assert key not in lookup, 'Duplicate trial in public results'
            assert record['execution_profile'] == 'strict-token-accounting-v1'
            assert record['split'] == ('development' if record['instance_id'].startswith('dev-') else 'sealed')
            lookup[key] = {**record, '_tag': tag, '_repeat': repeat, '_cohort': cohort}
    assert set(lookup) == expected, 'Incomplete or unexpected public matrix'
    assert len(lookup) == len(plan['jobs'])
    return list(lookup.values())


def rank(rows):
    """Feasibility first, exact integer TIR second; average ranks for ties."""
    ordered = sorted(rows, key=lambda r: (-r['feasible_attempts'], -r['_ticks'], r['model']))
    position = 1
    groups = []
    for _, members in itertools.groupby(ordered, key=lambda r: (r['feasible_attempts'], r['_ticks'])):
        members = list(members)
        groups.append(sorted(r['model'] for r in members))
        for row in members:
            row['rank'] = position + (len(members) - 1) / 2
            row['tied'] = len(members) > 1
        position += len(members)
    return ordered, groups


def effective(record, strict):
    if strict and base.resource_excess(record):
        return 0, 0
    return int(record['score']['feasible']), base.ticks(record)


def summarize_model(records, strict=False):
    assert len(records) == 18
    model = records[0]['requested_model']
    split = records[0]['split']
    cohort = records[0]['_cohort']
    assert all(r['requested_model'] == model and r['split'] == split and r['_cohort'] == cohort for r in records)
    rounds = [[r for r in records if r['_repeat'] == i] for i in (1, 2, 3)]
    assert all(len(group) == 6 and len({r['instance_id'] for r in group}) == 6 for group in rounds)
    case_sets = [{r['instance_id'] for r in group} for group in rounds]
    assert case_sets[0] == case_sets[1] == case_sets[2]
    outcomes = [[effective(r, strict) for r in group] for group in rounds]
    scores = [sum(t for _, t in group) / 172.8 / 6 for group in outcomes]
    feasible = [sum(f for f, _ in group) for group in outcomes]
    counts = sum(t for group in outcomes for _, t in group)
    case_rows = [[r for r in records if r['instance_id'] == case] for case in sorted(case_sets[0])]
    case_values = [[effective(r, strict)[1] / 172.8 for r in group] for group in case_rows]
    case_counts = [sum(effective(r, strict)[0] for r in group) for group in case_rows]
    errors = collections.Counter(e.get('classification') or ('HTTP_' + str(e['http_status']) if e.get('http_status') else e['type']) for r in records for e in r['api_errors'])
    row = {'split': split, 'cohort': cohort, 'model': model, 'attempts': 18, 'repetitions': 3,
           'feasible_attempts': sum(feasible), 'feasible_per_round': feasible,
           'mean_safe_tir': counts / 172.8 / 18, 'sample_sd_of_round_means': stdev(scores),
           'round_means': scores, 'minimum_round_mean': min(scores), 'maximum_round_mean': max(scores),
           'cases_feasible_all_three': sum(n == 3 for n in case_counts),
           'cases_feasible_some_repetitions': sum(0 < n < 3 for n in case_counts),
           'cases_feasible_no_repetition': sum(n == 0 for n in case_counts),
           'mean_within_case_sample_sd': mean(stdev(v) for v in case_values),
           'maximum_within_case_range': max(max(v) - min(v) for v in case_values),
           'native_verified': sum(r['score']['status'] == 'verified' for r in records),
           'valid_submissions': sum(r['score'].get('format_valid', False) for r in records),
           'api_error_requests': sum(len(r['api_errors']) for r in records), 'api_error_classes': dict(errors),
           'charged_completion_tokens': sum(r['charged_completion_tokens'] for r in records),
           'reported_success_completion_tokens': sum(base.reported_tokens(r) for r in records),
           'mean_cpu_seconds': mean(r.get('cpu_seconds', 0.) for r in records),
           'mean_wall_seconds': mean(r['wall_seconds'] for r in records),
           'resource_exceptions': sum(bool(base.resource_excess(r)) for r in records),
           'source_commits': sorted({r['source_commit'] for r in records}), '_ticks': counts}
    row.update(base.failure_counts(records))
    assert abs(mean(scores) - row['mean_safe_tir']) < 1e-9
    return row


def round_rows(records, cohorts, strict=False):
    rows, orders = [], {}
    for cohort, models in cohorts.items():
        orders[cohort] = {}
        for split in ('development', 'sealed'):
            orders[cohort][split] = []
            for repeat in (1, 2, 3):
                current = []
                for model in models:
                    group = [r for r in records if r['_cohort'] == cohort and r['split'] == split and r['_repeat'] == repeat and r['requested_model'] == model]
                    assert len(group) == 6
                    outcome = [effective(r, strict) for r in group]
                    count = sum(t for _, t in outcome)
                    row = {'cohort': cohort, 'cohort_model_count': len(models), 'split': split, 'repeat': repeat,
                           'tag': group[0]['_tag'], 'model': model, 'attempts': 6,
                           'feasible_attempts': sum(f for f, _ in outcome), 'mean_safe_tir': count / 172.8 / 6,
                           'api_error_requests': sum(len(r['api_errors']) for r in group),
                           'charged_completion_tokens': sum(r['charged_completion_tokens'] for r in group),
                           'resource_exceptions': sum(bool(base.resource_excess(r)) for r in group), '_ticks': count}
                    row.update(base.failure_counts(group))
                    current.append(row)
                ranked, groups = rank(current)
                rows.extend(ranked)
                orders[cohort][split].append({'repeat': repeat, 'rank_groups': groups})
    return rows, orders


def clean(row):
    return {k: v for k, v in row.items() if not k.startswith('_')}


def build_analysis(records, cohorts):
    assert set(cohorts) == {'earlier_strict_batch', 'six_route_expansion'}
    assert len(cohorts['earlier_strict_batch']) == 3 and len(cohorts['six_route_expansion']) == 6
    models = [model for group in cohorts.values() for model in group]
    assert len(models) == len(set(models)) == 9
    keys = {(r['_cohort'], r['_repeat'], r['instance_id'], r['requested_model']) for r in records}
    assert len(keys) == len(records) == 324
    for r in records:
        assert r['requested_model'] in cohorts[r['_cohort']]
    rounds, orders = round_rows(records, cohorts)
    strict_rounds, strict_orders = round_rows(records, cohorts, strict=True)
    rank_lookup = {(r['cohort'], r['split'], r['repeat'], r['model']): r['rank'] for r in rounds}
    strict_rank_lookup = {(r['cohort'], r['split'], r['repeat'], r['model']): r['rank'] for r in strict_rounds}
    rows, strict_rows, aggregate_orders, strict_aggregate_orders = [], [], {}, {}
    for split in ('development', 'sealed'):
        primary, sensitive = [], []
        for model in models:
            group = [r for r in records if r['split'] == split and r['requested_model'] == model]
            item = summarize_model(group)
            item['within_cohort_round_ranks'] = [rank_lookup[(item['cohort'], split, i, model)] for i in (1, 2, 3)]
            item['within_cohort_rank_denominator'] = len(cohorts[item['cohort']])
            primary.append(item)
            strict_item = summarize_model(group, strict=True)
            strict_item['within_cohort_round_ranks'] = [strict_rank_lookup[(strict_item['cohort'], split, i, model)] for i in (1, 2, 3)]
            strict_item['within_cohort_rank_denominator'] = len(cohorts[strict_item['cohort']])
            sensitive.append(strict_item)
        ranked, groups = rank(primary)
        strict_ranked, strict_groups = rank(sensitive)
        rows.extend(ranked);strict_rows.extend(strict_ranked)
        aggregate_orders[split] = groups;strict_aggregate_orders[split] = strict_groups
    variation, exceptions = [], []
    for model in models:
        cohort = next(c for c, group in cohorts.items() if model in group)
        for case in sorted({r['instance_id'] for r in records if r['requested_model'] == model}):
            group = sorted([r for r in records if r['requested_model'] == model and r['instance_id'] == case], key=lambda r: r['_repeat'])
            assert len(group) == 3
            scores = [base.value(r) for r in group]
            variation.append({'cohort': cohort, 'model': model, 'case': case, 'split': group[0]['split'],
                              'feasible_repetitions': sum(r['score']['feasible'] for r in group),
                              'r1': scores[0], 'r2': scores[1], 'r3': scores[2], 'mean_safe_tir': mean(scores),
                              'sample_sd': stdev(scores), 'range': max(scores) - min(scores)})
    for r in records:
        excess = base.resource_excess(r)
        if excess:
            exceptions.append({'cohort': r['_cohort'], 'tag': r['_tag'], 'case': r['instance_id'],
                               'model': r['requested_model'], 'split': r['split'], 'excess': excess,
                               'original_feasible': r['score']['feasible'], 'original_safe_tir': base.value(r)})
    paired = []
    new_records = [r for r in records if r['_cohort'] == 'six_route_expansion']
    lookup = {(r['requested_model'], r['_repeat'], r['instance_id']): r for r in new_records}
    for split in ('development', 'sealed'):
        cases = sorted({r['instance_id'] for r in new_records if r['split'] == split})
        for a, b in itertools.combinations(cohorts['six_route_expansion'], 2):
            aw = bw = ties = 0
            for repeat, case in itertools.product((1, 2, 3), cases):
                ra, rb = lookup[(a, repeat, case)], lookup[(b, repeat, case)]
                ka, kb = (ra['score']['feasible'], base.ticks(ra)), (rb['score']['feasible'], base.ticks(rb))
                aw += ka > kb;bw += kb > ka;ties += ka == kb
            paired.append({'split': split, 'model_a': a, 'model_b': b, 'paired_case_repetitions': 18,
                           'a_wins': aw, 'b_wins': bw, 'ties': ties})
    stable = {cohort: {split: all(x['rank_groups'] == values[0]['rank_groups'] for x in values)
                      for split, values in splits.items()} for cohort, splits in orders.items()}
    return {'primary_split': 'sealed', 'new_attempts': len(new_records), 'combined_strict_profile_attempts': len(records),
            'cohorts': cohorts, 'rows': [clean(r) for r in rows], 'rounds': [clean(r) for r in rounds],
            'round_orderings_within_cohort': orders, 'identical_ordering_in_all_three_rounds': stable,
            'combined_aggregate_orderings': aggregate_orders, 'case_variation': variation,
            'paired_comparisons_new_cohort_only': paired,
            'resource_sensitivity': {'registration': {'six_route_expansion': 'preregistered', 'earlier_strict_batch': 'posthoc, retained as previously disclosed'},
                'rows': [clean(r) for r in strict_rows], 'rounds': [clean(r) for r in strict_rounds],
                'round_orderings_within_cohort': strict_orders, 'aggregate_orderings': strict_aggregate_orders,
                'ordering_matches_primary_by_round': {
                    cohort: {split: [a['rank_groups'] == b['rank_groups'] for a, b in zip(strict_orders[cohort][split], orders[cohort][split])]
                             for split in ('development', 'sealed')} for cohort in cohorts},
                'aggregate_ordering_matches_primary': {s: aggregate_orders[s] == strict_aggregate_orders[s] for s in aggregate_orders},
                'exceptions': exceptions},
            'limits': ['Nine-route aggregates combine two chronological batches; no contemporaneous nine-route randomization or cross-batch paired tests.',
                       'Mean and sample SD describe three observed round means on six fixed sealed cases, not confidence intervals or a population ranking.',
                       'Failed attempts remain in every denominator. The old pilot is not pooled with strict-profile attempts.',
                       'Public weight repositories do not authenticate the checkpoint or inference settings served by a routed API. Billing is unavailable.']}

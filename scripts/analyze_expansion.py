"""Require the complete public matrices; write only the new expansion report."""
import csv
import json

from gri_bench.expansion import EXPERIMENT, REPORT, verify_expansion_freeze
from gri_bench.expansion_analysis import build_analysis, load_cohort
from gri_bench.runner import ROOT, dump


def write_csv(name, rows):
    flattened = []
    for row in rows:
        flattened.append({k: json.dumps(v, separators=(',', ':')) if isinstance(v, (dict, list)) else v for k, v in row.items()})
    with (REPORT / name).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flattened[0]) if flattened else [], lineterminator='\n')
        writer.writeheader()
        writer.writerows(flattened)


def render_report(summary, names):
    sealed = [r for r in summary['rows'] if r['split'] == 'sealed']
    new = [r for r in sealed if r['cohort'] == 'six_route_expansion']
    sensitivity = summary['resource_sensitivity']
    exceptions = sensitivity['exceptions']
    new_exceptions = [r for r in exceptions if r['cohort'] == 'six_route_expansion']
    lines = ['# Six additional model routes', '',
             '**216 new attempts are complete:** six routes × twelve fixed cases × three fresh contexts. The nine-route aggregate contains 324 attempts under strict token accounting, combining this expansion with the earlier 108 attempts. Every planned failure remains in the denominator.', '',
             'The [preregistered protocol](../../docs/MODEL_EXPANSION_2026_11_11.md) preserves the task, prompts, image, scoring and per-trial budgets. The [model registry](../../experiments/expansion-2026-11-11/models.json) links official open weights; API-served checkpoint identities are not independently authenticated. Claude-family routes are excluded.', '',
             '## Nine-route sealed-case aggregate', '',
             'Rank by feasible-case rate, then mean safety-gated TIR; ties share average rank. Each route has 18 sealed attempts. **SD is the sample SD of three round means, not a confidence interval.** The earlier three routes and the new six routes are different chronological batches.', '',
             '| Rank | Model / requested route | Batch | Feasible /18 | Mean safe TIR (%) ± SD | R1 / R2 / R3 means |',
             '|---:|---|---|---:|---:|---|']
    for r in sealed:
        batch = 'New six' if r['cohort'] == 'six_route_expansion' else 'Earlier three'
        lines.append(f"| {r['rank']:g} | {names[r['model']]} · `{r['model']}` | {batch} | {r['feasible_attempts']}/18 | {r['mean_safe_tir']:.2f} ± {r['sample_sd_of_round_means']:.2f} | " + ' / '.join(f'{v:.2f}' for v in r['round_means']) + ' |')
    lines += ['', '![Nine-route descriptive comparison on fixed sealed cases](comparison.png)', '',
              '## Repeatability within the six new routes', '',
              'The ranks below compare only the six new routes in each new round. They do not treat separately collected earlier rounds as an interleaved nine-route trial.', '',
              '| Model | Feasible R1 / R2 / R3 | Ranks among six | Cases feasible all 3 / some / none | Mean within-case SD (pp) | Largest within-case range (pp) |',
              '|---|---|---|---|---:|---:|']
    for r in new:
        lines.append(f"| {names[r['model']]} | " + ' / '.join(map(str, r['feasible_per_round'])) + ' | ' + ' / '.join(f'{x:g}' for x in r['within_cohort_round_ranks']) +
                     f" | {r['cases_feasible_all_three']} / {r['cases_feasible_some_repetitions']} / {r['cases_feasible_no_repetition']} | {r['mean_within_case_sample_sd']:.2f} | {r['maximum_within_case_range']:.2f} |")
    stable = summary['identical_ordering_in_all_three_rounds']['six_route_expansion']['sealed']
    lines += ['', f'Identical sealed-case ordering among the new six in all three rounds: **{str(stable).lower()}**. Variability includes zeros from invalid submissions and safety failures.', '',
              '## Sealed-case failures and request accounting', '',
              '| Model | API-error requests | Submission failures /18 | Simulation failures /18 | Infrastructure failures /18 | Safety failures /18 |',
              '|---|---:|---:|---:|---:|---:|']
    for r in sealed:
        lines.append(f"| {names[r['model']]} | {r['api_error_requests']} | {r['submission_failures']} | {r['simulation_failures']} | {r['infrastructure_failures']} | {r['safety_failures']} |")
    lines += ['', 'API errors count requests and may coexist with a completed design. Trial failure categories are mutually exclusive. Failed-request output allowances remain charged; model waiting consumes the unchanged wall-clock allowance. These observations do not isolate a causal effect of a model family or provider.', '',
              '## Resource-limit sensitivity', '',
              f'The new cohort contains **{len(new_exceptions)}/216** attempts with a recorded resource-limit excess; the complete [exception list](resource-exceptions.json) also retains earlier-cohort exceptions. The monitor and configured limits were unchanged.', '',
              'The secondary view sets any over-limit attempt to infeasible/zero, retains all attempts and leaves primary scores unchanged. This view was preregistered for the new cohort; the earlier cohort’s sensitivity was introduced after its development CPU overrun.', '',
              '| Model | Sealed resource exceptions | Feasible /18 after zeroing | Mean safe TIR (%) | Aggregate rank after zeroing | R1 / R2 / R3 ranks within batch |',
              '|---|---:|---:|---:|---:|---|']
    for r in sensitivity['rows']:
        if r['split'] == 'sealed':
            lines.append(f"| {names[r['model']]} | {r['resource_exceptions']} | {r['feasible_attempts']}/18 | {r['mean_safe_tir']:.2f} | {r['rank']:g} | " + ' / '.join(f'{x:g}' for x in r['within_cohort_round_ranks']) + ' |')
    comparisons = sensitivity['ordering_matches_primary_by_round']
    lines += ['', 'Within-batch ranks compare six new routes or three earlier routes. Sealed round orderings unchanged after zeroing (R1 / R2 / R3): new six **' + ' / '.join('yes' if x else 'no' for x in comparisons['six_route_expansion']['sealed']) + '**; earlier three **' + ' / '.join('yes' if x else 'no' for x in comparisons['earlier_strict_batch']['sealed']) + '**.', '',
              'After zeroing, the combined sealed-case aggregate ordering is ' + ('unchanged' if sensitivity['aggregate_ordering_matches_primary']['sealed'] else 'changed') + '; the development aggregate ordering is ' + ('unchanged' if sensitivity['aggregate_ordering_matches_primary']['development'] else 'changed') + '.', '',
              '## Fixed baseline reference', '',
              '| Method | Feasible /6 | Mean safe TIR (%) |', '|---|---:|---:|']
    for r in summary['baseline_single_run_reference']:
        if r['split'] == 'sealed':
            lines.append(f"| {r['method']} | {r['feasible_cases']}/6 | {r['mean_safe_tir']:.2f} |")
    lines += ['', 'Baselines have one original run per case; these rows do not estimate baseline variance. The original model pilot is preserved in the earlier release and is not pooled with the strict-profile trials.', '',
              '## Evidence and interpretation', '',
              '- [Independent audit](audit.json): exact planned coverage, source/image/lock preservation, native trajectory arithmetic, request ledgers, prompts, evidence hashes and publication receipts.',
              '- [Publication redactions](publication-redactions.json): only private sealed diagnostic text changes; raw exports and numeric scores remain intact.',
              '- [Publication audit](publication-audit.json): credentials, private evaluation seeds/salts, public Git contents and the original research files.',
              '- [All nine routes](leaderboard.csv), [rounds](rounds.csv), [case variability](case-variation.csv), [new-cohort paired comparisons](paired-comparisons-new-cohort.csv), [resource sensitivity](resource-sensitivity.csv), [resource-sensitive round ranks](resource-rounds.csv), and [complete JSON](summary.json).',
              '- [Earlier three-route report](../repetitions-2026-11-11/README.md) and all earlier result bytes remain unchanged.',
              '- The fixed sealed cases have already been scored by the maintainer. This measures repetition on existing cases, not new unseen-case generalization, clinical efficacy, statistical significance, or a population-level foundation-model ranking.',
              '- No cross-batch paired test is reported. Provider-default inference, API routing and observation time are part of the measured workflow; actual provider billing is unavailable.', '']
    return '\n'.join(lines)


def main():
    plan = verify_expansion_freeze()
    old = json.loads((ROOT / 'experiments/repeats-2026-11-11/plan.json').read_text())
    earlier = load_cohort(old, 'earlier_strict_batch')
    new = load_cohort(plan, 'six_route_expansion')
    summary = build_analysis(earlier + new, {'earlier_strict_batch': old['models'], 'six_route_expansion': plan['models']})
    prior_summary = json.loads((ROOT / 'results/repetitions-2026-11-11/summary.json').read_text())
    summary['baseline_single_run_reference'] = prior_summary['baseline_single_run_reference']
    old_lookup = {(r['split'], r['model']): r for r in prior_summary['rows']}
    for row in summary['rows']:
        if row['cohort'] == 'earlier_strict_batch':
            previous = old_lookup[(row['split'], row['model'])]
            for field in ('mean_safe_tir', 'sample_sd_of_round_means', 'mean_within_case_sample_sd', 'maximum_within_case_range'):
                assert abs(row[field] - previous[field]) < 1e-9
            assert row['feasible_attempts'] == previous['feasible_attempts']
            assert row['within_cohort_round_ranks'] == previous['round_ranks']
    names = {'codex/gpt-6.1-sol': 'GPT-6.1 Sol', 'wanjie/deepseek-v4.1-flash-1017': 'DeepSeek V4.1 Flash 1017', 'tokendance/glm-5.3': 'GLM-5.3'}
    registry = json.loads((EXPERIMENT / 'models.json').read_text())
    names.update({r['requested_route']: r['display_name'] for r in registry['selected']})
    summary['display_names'] = names
    REPORT.mkdir(parents=True, exist_ok=True)
    dump(REPORT / 'summary.json', summary)
    write_csv('leaderboard.csv', summary['rows'])
    write_csv('rounds.csv', summary['rounds'])
    write_csv('case-variation.csv', summary['case_variation'])
    write_csv('paired-comparisons-new-cohort.csv', summary['paired_comparisons_new_cohort_only'])
    write_csv('resource-sensitivity.csv', summary['resource_sensitivity']['rows'])
    write_csv('resource-rounds.csv', summary['resource_sensitivity']['rounds'])
    dump(REPORT / 'resource-exceptions.json', summary['resource_sensitivity']['exceptions'])
    (REPORT / 'README.md').write_text(render_report(summary, names))
    print(json.dumps({'new_attempts': len(new), 'combined_attempts': len(earlier) + len(new),
                      'new_sealed_order_stable': summary['identical_ordering_in_all_three_rounds']['six_route_expansion']['sealed']}))


if __name__ == '__main__':
    main()

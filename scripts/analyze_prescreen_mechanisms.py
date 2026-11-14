"""Post-screen descriptive diagnostics; no new design selection or simulation."""
import argparse
import statistics
from gri_bench.prescreen_v03.run import OUT, check_plan, read, design_records, write_new


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    plan = check_plan()
    records = design_records(plan)
    lookup = {(r['case'], r['repetition'], r['method']): r for r in records}
    scores = {r['design_id']: read(OUT / 'screen' / f"{r['design_id']}.json") for r in records}
    agreements = []
    for a, b in [('de_fixed', 'de_racing'), ('de_fixed', 'de_no_margin'),
                 ('de_fixed', 'de_early'), ('de_fixed', 'de_search')]:
        changed = []
        for case in plan['cases']:
            for repetition in range(1, 6):
                ra, rb = (lookup[case, repetition, m] for m in (a, b))
                if ra['design_id'] != rb['design_id']:
                    changed.append({'case': case, 'repetition': repetition,
                                    'a_primary': scores[ra['design_id']]['primary'],
                                    'b_primary': scores[rb['design_id']]['primary']})
        agreements.append({'a': a, 'b': b, 'identical_designs': 30-len(changed),
                           'total_pairs': 30, 'changed_pairs': changed})
    cases = []
    for case in plan['cases']:
        for method in plan['methods']:
            selected = [r for r in records if r['case'] == case and r['method'] == method]
            observed = [scores[r['design_id']] for r in selected]
            cases.append({'case': case, 'method': method, 'attempts': len(selected),
                          'score16': statistics.mean(x['primary']['safe_tir'] for x in observed),
                          'safe16': sum(x['primary']['feasible'] for x in observed),
                          'score32': statistics.mean(x['expanded']['safe_tir'] for x in observed),
                          'safe32': sum(x['expanded']['feasible'] for x in observed)})
    validation = []
    for case in plan['cases']:
        for repetition in range(1, 6):
            job = read(OUT / 'search' / f'{case}-r{repetition}.json')
            candidates = job['details']['de']['fixed_validation']['candidates']
            validation.append({'case': case, 'repetition': repetition,
                               'selected_candidate_index': candidates[0]['candidate_index'],
                               'top_two_loss_gap': candidates[1]['loss']-candidates[0]['loss'],
                               'validation_feasible_candidates': sum(x['validation']['feasible'] for x in candidates)})
    result = {'scope': 'Post-screen descriptive diagnostics; not preregistered hypotheses or new optimization.',
              'agreements': agreements, 'case_methods': cases, 'validation_shortlists': validation,
              'zero_release_selections': {m: sum(all(v == 0 for k, v in r['design']['parameters'].items()
                                                   if k in ('theta_a', 'theta_c'))
                                                 for r in records if r['method'] == m)
                                          for m in plan['methods']}}
    write_new(args.output, result)
    print({'agreements': [(x['a'], x['b'], x['identical_designs']) for x in agreements],
           'output': args.output})


if __name__ == '__main__':
    main()

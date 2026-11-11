"""Predeclared stability analysis plus disclosed resource sensitivity; require 108 attempts."""
import collections
import csv
import itertools
import json
from statistics import mean, stdev
from gri_bench.runner import ROOT, dump

EXP=ROOT/'experiments/repeats-2026-11-11'
OUT=ROOT/'results/repetitions-2026-11-11'


def ticks(record):
    # Each verified design has 18 trajectories x 960 post-warmup samples.
    # Integer TIR counts preserve mathematical ties despite float summation noise.
    value=record['score'].get('safe_tir') or 0.
    count=round(value*172.8)
    assert abs(value-count/172.8)<1e-9
    return count


def value(record):return ticks(record)/172.8


def reported_tokens(record):
    values=[u.get('completion_tokens') for u in record['usage'] if isinstance(u,dict)]
    return sum(v for v in values if isinstance(v,int) and not isinstance(v,bool) and v>=0)


def failure_counts(records):
    statuses=collections.Counter(r['score']['status'] for r in records)
    assert set(statuses)<={'verified','submission_failure','simulation_failure','infrastructure_error'}
    return {'submission_failures':statuses['submission_failure'],
            'simulation_failures':statuses['simulation_failure'],
            'infrastructure_failures':statuses['infrastructure_error'],
            'safety_failures':sum(r['score']['status']=='verified' and not r['score']['feasible'] for r in records)}


def resource_excess(record):
    limits={'cpu_seconds':30,'tool_wall_seconds':90,'wall_seconds':360,
            'charged_completion_tokens':18000,'model_calls':12}
    return {name:record[name]-limit for name,limit in limits.items()
            if record.get(name,0)>limit}


def resource_sensitivity(records,models,tags,primary_orderings):
    """Secondary analysis introduced after a development CPU overrun was observed.

    Keep saved native scores untouched. Zero over-limit attempts only in this
    explicitly separate view, retaining every attempt in its original denominator.
    """
    exceptions=[];rounds=[];orderings={};summary=[]
    for r in records:
        excess=resource_excess(r)
        if excess:
            exceptions.append({'tag':r['_tag'],'case':r['instance_id'],'split':r['split'],
                               'model':r['requested_model'],'excess':excess,
                               'original_feasible':r['score']['feasible'],
                               'original_safe_tir':value(r)})
    for split in ['development','sealed']:
        orderings[split]=[]
        for tag in tags:
            rows=[]
            for model in models:
                group=[r for r in records if r['_tag']==tag and r['split']==split and r['requested_model']==model]
                assert len(group)==6
                retained=[r for r in group if not resource_excess(r)]
                count=sum(r['score']['feasible'] for r in retained)
                score_sum=sum(ticks(r) for r in retained)
                rows.append({'split':split,'tag':tag,'model':model,'attempts':6,
                             'resource_exceptions':6-len(retained),'feasible_cases':count,
                             'mean_safe_tir':score_sum/172.8/6,'_key':(count,score_sum)})
            groups=[];position=1
            for key,items in itertools.groupby(sorted(rows,key=lambda r:r['_key'],reverse=True),key=lambda r:r['_key']):
                items=list(items);groups.append(sorted(r['model'] for r in items))
                for row in items:row['rank']=(2*position+len(items)-1)/2
                position+=len(items)
            orderings[split].append({'tag':tag,'rank_groups':groups})
            for row in rows:row.pop('_key');rounds.append(row)
        for model in models:
            group=[r for r in rounds if r['split']==split and r['model']==model]
            summary.append({'split':split,'model':model,'attempts':18,
                            'resource_exceptions':sum(r['resource_exceptions'] for r in group),
                            'feasible_attempts':sum(r['feasible_cases'] for r in group),
                            'mean_safe_tir':mean(r['mean_safe_tir'] for r in group),
                            'round_means':[r['mean_safe_tir'] for r in group],
                            'round_ranks':[r['rank'] for r in group]})
    return {'status':'Secondary sensitivity, added after observing a development CPU overrun; not preregistered.',
            'rule':'Assign infeasible/zero in this view whenever any recorded CPU, wall, tool-wall, call or charged-token limit is exceeded. No tolerance and no dropped trials. Original native scores remain unchanged.',
            'exceptions':exceptions,'rows':summary,'rounds':rounds,'round_orderings':orderings,
            'ordering_matches_primary_by_round':{s:[a['rank_groups']==b['rank_groups'] for a,b in zip(orderings[s],primary_orderings[s])] for s in orderings}}


def write_csv(name,rows):
    with (OUT/name).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(rows)


def main():
    plan=json.loads((EXP/'plan.json').read_text());models=plan['models'];tags=plan['tags']
    records=[];lookup={}
    for tag in tags:
        for p in sorted((ROOT/'results'/tag).glob('*/result.json')):
            r=json.loads(p.read_text());r['_tag']=tag
            key=(tag,r['instance_id'],r['requested_model'])
            assert key not in lookup;lookup[key]=r;records.append(r)
    expected={(j['tag'],j['case'],j['model']) for j in plan['jobs']}
    assert set(lookup)==expected and len(records)==108,'Incomplete or unexpected matrix'
    OUT.mkdir(parents=True,exist_ok=True)
    rounds=[];orderings={};rankings={}
    for split in ['development','sealed']:
        orderings[split]=[]
        for tag in tags:
            rows=[]
            for model in models:
                group=[r for r in records if r['_tag']==tag and r['split']==split and r['requested_model']==model]
                assert len(group)==6
                row={'split':split,'tag':tag,'model':model,'attempts':6,
                     'feasible_cases':sum(r['score']['feasible'] for r in group),
                     'mean_safe_tir':sum(ticks(r) for r in group)/172.8/6,
                     'valid_submissions':sum(r['score'].get('format_valid',False) for r in group),
                     'native_verified':sum(r['score']['status']=='verified' for r in group),
                     'api_error_requests':sum(len(r['api_errors']) for r in group),
                     'charged_completion_tokens':sum(r['charged_completion_tokens'] for r in group),
                     'reported_success_completion_tokens':sum(reported_tokens(r) for r in group),
                     'mean_cpu_seconds':mean(r.get('cpu_seconds',0.) for r in group),
                     'mean_wall_seconds':mean(r['wall_seconds'] for r in group)}
                row.update(failure_counts(group))
                row['_key']=(row['feasible_cases'],sum(ticks(r) for r in group));rows.append(row)
            groups=[];position=1
            for key,items in itertools.groupby(sorted(rows,key=lambda r:r['_key'],reverse=True),key=lambda r:r['_key']):
                items=list(items);groups.append(sorted(r['model'] for r in items))
                for r in items:
                    r['rank']=(position+position+len(items)-1)/2
                    r['tied']=len(items)>1;rankings[(split,tag,r['model'])]=r['rank']
                position+=len(items)
            orderings[split].append({'tag':tag,'rank_groups':groups})
            for row in rows:row.pop('_key');rounds.append(row)
    summary=[]
    for split in ['development','sealed']:
        for model in models:
            rs=[r for r in rounds if r['split']==split and r['model']==model]
            group=[r for r in records if r['split']==split and r['requested_model']==model]
            scores=[r['mean_safe_tir'] for r in rs]
            cases=sorted({r['instance_id'] for r in group})
            case_scores=[[value(r) for r in group if r['instance_id']==case] for case in cases]
            case_feasible=[sum(r['score']['feasible'] for r in group if r['instance_id']==case) for case in cases]
            assert len(cases)==6 and all(len(v)==3 for v in case_scores)
            classes=collections.Counter(e.get('classification') or ('HTTP_'+str(e['http_status']) if e.get('http_status') else e['type']) for r in group for e in r['api_errors'])
            row={'split':split,'model':model,'attempts':18,'repetitions':3,
                 'feasible_attempts':sum(r['score']['feasible'] for r in group),
                 'feasible_per_round':[r['feasible_cases'] for r in rs],
                 'mean_safe_tir':mean(scores),'sample_sd_of_round_means':stdev(scores),
                 'minimum_round_mean':min(scores),'maximum_round_mean':max(scores),
                 'round_means':scores,'round_ranks':[r['rank'] for r in rs],
                 'cases_feasible_all_three':sum(n==3 for n in case_feasible),
                 'cases_feasible_some_repetitions':sum(0<n<3 for n in case_feasible),
                 'cases_feasible_no_repetition':sum(n==0 for n in case_feasible),
                 'mean_within_case_sample_sd':mean(stdev(v) for v in case_scores),
                 'maximum_within_case_range':max(max(v)-min(v) for v in case_scores),
                 'valid_submissions':sum(r['score'].get('format_valid',False) for r in group),
                 'native_verified':sum(r['score']['status']=='verified' for r in group),
                 'api_error_requests':sum(len(r['api_errors']) for r in group),
                 'api_error_classes':dict(classes),
                 'charged_completion_tokens':sum(r['charged_completion_tokens'] for r in group),
                 'reported_success_completion_tokens':sum(reported_tokens(r) for r in group),
                 'mean_cpu_seconds':mean(r.get('cpu_seconds',0.) for r in group),
                 'mean_wall_seconds':mean(r['wall_seconds'] for r in group)}
            row.update(failure_counts(group));summary.append(row)
    summary.sort(key=lambda r:(r['split'],-r['feasible_attempts'],-r['mean_safe_tir']))
    variation=[]
    for case in plan['cases']:
        for model in models:
            group=[lookup[(tag,case,model)] for tag in tags]
            scores=[value(r) for r in group]
            variation.append({'case':case,'split':group[0]['split'],'model':model,
                'feasible_repetitions':sum(r['score']['feasible'] for r in group),
                'r1':scores[0],'r2':scores[1],'r3':scores[2],'mean_safe_tir':mean(scores),
                'sample_sd':stdev(scores),'range':max(scores)-min(scores)})
    paired=[]
    for split in ['development','sealed']:
        cases=[c for c in plan['cases'] if c.startswith('dev' if split=='development' else 'sealed')]
        for a,b in itertools.combinations(models,2):
            aw=bw=ties=0
            for tag,case in itertools.product(tags,cases):
                ra,rb=lookup[(tag,case,a)],lookup[(tag,case,b)]
                ka=(ra['score']['feasible'],ticks(ra));kb=(rb['score']['feasible'],ticks(rb))
                aw+=ka>kb;bw+=kb>ka;ties+=ka==kb
            paired.append({'split':split,'model_a':a,'model_b':b,'paired_case_repetitions':18,
                           'a_wins':aw,'b_wins':bw,'ties':ties})
    baseline=[];historical=[]
    for folder,kind in [('pilot-v1','baseline'),('pilot-v2','historical')]:
        rows=[json.loads(p.read_text()) for p in (ROOT/'results'/folder).glob('*/result.json')]
        if kind=='baseline':rows=[r for r in rows if r['method']!='agent']
        for split in ['development','sealed']:
            for method in sorted({r['requested_model'] or r['method'] for r in rows}):
                group=[r for r in rows if r['split']==split and (r['requested_model'] or r['method'])==method]
                assert len(group)==6
                item={'split':split,'method':method,'attempts':6,'feasible_cases':sum(r['score']['feasible'] for r in group),
                      'mean_safe_tir':mean(value(r) for r in group)}
                (baseline if kind=='baseline' else historical).append(item)
    sensitivity=resource_sensitivity(records,models,tags,orderings)
    report={'analysis':'Three additional repetitions, strict-token-accounting-v1; all planned attempts included.',
            'primary_split':'sealed','rows':summary,'rounds':rounds,'round_orderings':orderings,
            'identical_ordering_in_all_three_rounds':{s:all(x['rank_groups']==orderings[s][0]['rank_groups'] for x in orderings[s]) for s in orderings},
            'paired_comparisons':paired,'baseline_single_run_reference':baseline,'original_pilot_separate_reference':historical,
            'resource_sensitivity':sensitivity,
            'limits':['Within six fixed cases per split, three new model contexts per case. Existing sealed-case scores were known to the maintainer.',
                      'Sample SD is across three round means, not a confidence interval or population-level model-ranking claim.',
                      'Original GLM trials used defective failed-request accounting; no homogeneous four-repeat pooling.',
                      'Ranking uses feasibility first, then mean safe TIR. Integer TIR sample counts preserve mathematical ties.',
                      'Configured resource limits are unchanged. Observed monitor overshoot is disclosed; a secondary, non-preregistered analysis zeroes any over-limit attempt.',
                      'Failure reservations are conservative upper bounds; actual billing and authenticated upstream identities are unavailable.']}
    dump(OUT/'summary.json',report)
    write_csv('leaderboard.csv',[{k:(json.dumps(v) if isinstance(v,(list,dict)) else v) for k,v in r.items()} for r in summary])
    write_csv('rounds.csv',rounds);write_csv('case-variation.csv',variation);write_csv('paired-comparisons.csv',paired)
    write_csv('resource-sensitivity.csv',[{k:(json.dumps(v) if isinstance(v,(list,dict)) else v) for k,v in r.items()} for r in sensitivity['rows']])
    dump(OUT/'resource-exceptions.json',sensitivity['exceptions'])
    lines=['# Three additional repetitions','',
      '**108 planned attempts:** three routes × twelve fixed cases × three new contexts. All attempts, including failures, remain in the denominator. Original results are preserved separately.','',
      'The scientific contract and numeric budgets are unchanged. Failed requests now consume their reserved completion allowance. See the [pre-run plan](../../experiments/repeats-2026-11-11/plan.json) and [GLM diagnosis](../../docs/GLM_502_DIAGNOSIS.md).','',
      '![Three-round quality and feasibility on the fixed sealed cases](stability.png)','',
      '## Sealed cases','',
      '| Requested route | Feasible /18 | R1 / R2 / R3 mean safe TIR (%) | Mean ± sample SD | R1 / R2 / R3 rank | API errors |',
      '|---|---:|---|---:|---|---:|']
    for r in summary:
        if r['split']!='sealed':continue
        means=' / '.join(f'{v:.2f}' for v in r['round_means']);ranks=' / '.join(f'{v:g}' for v in r['round_ranks'])
        lines.append(f"| {r['model']} | {r['feasible_attempts']}/18 | {means} | {r['mean_safe_tir']:.2f} ± {r['sample_sd_of_round_means']:.2f} | {ranks} | {r['api_error_requests']} |")
    stable=report['identical_ordering_in_all_three_rounds']['sealed']
    lines+=['',f'Identical sealed-case ordering in all three rounds: **{str(stable).lower()}**. Ranking is by feasible-case count first and mean safety-gated TIR second; ties share rank.','',
      '## Per-round orders','']
    for o in orderings['sealed']:
        lines.append('- '+o['tag']+': '+' > '.join(' = '.join(group) for group in o['rank_groups']))
    lines+=['','## Failure accounting on sealed cases','',
      '| Requested route | API error requests | Submission failures /18 | Simulation or infrastructure failures /18 | Safety failures /18 |',
      '|---|---:|---:|---:|---:|']
    for r in summary:
        if r['split']!='sealed':continue
        lines.append(f"| {r['model']} | {r['api_error_requests']} | {r['submission_failures']} | {r['simulation_failures']+r['infrastructure_failures']} | {r['safety_failures']} |")
    lines+=['','API errors count requests and may coexist with a valid or failed design. The other columns count mutually exclusive trial outcomes. An association between API errors and low scores does not isolate a causal effect of the route.']
    lines+=['','## Within-case consistency','',
      '| Requested route | Cases feasible in all 3 / some / none | Mean within-case SD (percentage points) | Largest within-case range (percentage points) |',
      '|---|---|---:|---:|']
    for r in summary:
        if r['split']!='sealed':continue
        counts=f"{r['cases_feasible_all_three']} / {r['cases_feasible_some_repetitions']} / {r['cases_feasible_no_repetition']}"
        lines.append(f"| {r['model']} | {counts} | {r['mean_within_case_sample_sd']:.2f} | {r['maximum_within_case_range']:.2f} |")
    lines+=['','These variability measures include zero scores from safety or submission failures. They describe repeated runs on the same six cases.']
    lines+=['','## Observed resource limits and sensitivity','',
      f"{len(sensitivity['exceptions'])}/108 attempts exceeded at least one recorded resource limit; [exact exceptions](resource-exceptions.json) are retained. Configured limits and the frozen monitor were unchanged.",
      '',sensitivity['status'],sensitivity['rule'],'',
      '| Requested route | Resource exceptions (sealed /18) | Feasible /18 after zeroing | Mean safe TIR (%) | R1 / R2 / R3 rank |',
      '|---|---:|---:|---:|---|']
    for r in sensitivity['rows']:
        if r['split']!='sealed':continue
        ranks=' / '.join(f'{v:g}' for v in r['round_ranks'])
        lines.append(f"| {r['model']} | {r['resource_exceptions']} | {r['feasible_attempts']}/18 | {r['mean_safe_tir']:.2f} | {ranks} |")
    lines+=['',f"Sealed ordering matches the primary analysis in rounds 1 / 2 / 3: {sensitivity['ordering_matches_primary_by_round']['sealed']}. Both splits are in [resource-sensitivity.csv](resource-sensitivity.csv)."]
    lines+=['','## Fixed baseline reference','',
      '| Method | Feasible /6 | Mean safe TIR (%) |','|---|---:|---:|']
    for r in sorted([r for r in baseline if r['split']=='sealed'],key=lambda r:(-r['feasible_cases'],-r['mean_safe_tir'])):
        lines.append(f"| {r['method']} | {r['feasible_cases']}/6 | {r['mean_safe_tir']:.2f} |")
    lines+=['','Baselines have one original run per case; these reference rows do not estimate baseline variance. The original pilot is kept in `summary.json` as a separate reference, not pooled as a fourth same-condition repetition.','',
      '## Evidence and limits','',
      '- [Independent audit](audit.json) checks native trajectories, every request ledger, exact planned coverage and preservation of the original result files.',
      '- [Publication redactions](publication-redactions.json) remove private sealed bounds from exception text only. Numeric scores are unchanged; raw diagnostics and original exports remain private with hashes.',
      '- [Round-level results](rounds.csv), [case variation](case-variation.csv), [paired comparisons](paired-comparisons.csv), and [full JSON](summary.json) include both development and sealed splits.',
      '- Sample SD describes three observed round means. Six fixed cases and three repetitions do not establish a population ranking, statistical significance, unseen-patient generalization or clinical efficacy.',
      '- Routes and provider-default inference settings are not independently authenticated model checkpoints. Token reservations include failed requests; billing is unavailable.','']
    (OUT/'README.md').write_text('\n'.join(lines))
    print('\n'.join(lines))


if __name__=='__main__':main()

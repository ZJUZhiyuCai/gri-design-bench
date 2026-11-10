"""Descriptive failure/resource accounting; never changes primary scores."""
import collections
import json
from pathlib import Path
from statistics import mean
from gri_bench.runner import ROOT, dump


def main():
    folder=ROOT/'results/pilot-v2'
    records=[json.loads(p.read_text()) for p in folder.glob('*/result.json')]
    if len(records)!=36:raise RuntimeError('Wait for all 36 formal agent records')
    groups=collections.defaultdict(list)
    for r in records:groups[(r['requested_model'],r['split'])].append(r)
    analysis=[]
    for (model,split),rows in sorted(groups.items()):
        counts=collections.Counter(r['score']['status'] for r in rows)
        safety=collections.Counter()
        for r in rows:
            s=r['score']
            if s['status']=='verified' and not s['feasible']:
                if s['max_trajectory_tbr70']>4:safety['TBR70']+=1
                if s['max_trajectory_tbr54']>1:safety['TBR54']+=1
                if s['minimum_glucose']<40:safety['minimum_glucose']+=1
        usage=[u for r in rows for u in r['usage']]
        api_statuses=collections.Counter(str(e.get('http_status',e.get('type','unknown')))
                                        for r in rows for e in r['api_errors'])
        reasoning=[u.get('completion_tokens_details',{}).get('reasoning_tokens') for u in usage]
        reported=[x for x in reasoning if x is not None]
        analysis.append({'model':model,'split':split,'trials':len(rows),'statuses':dict(counts),
             'safety_failure_types_nonexclusive':dict(safety),'feasible':sum(r['score']['feasible'] for r in rows),
             'missing_artifact_trials':sum(any(v!='ok' for v in r.get('files',{}).values()) for r in rows),
             'tool_budget_exhausted':sum(r.get('budget_exhausted',False) for r in rows),
             'mean_cpu_seconds':mean(r.get('cpu_seconds',0.) for r in rows),
             'mean_model_calls':mean(r['model_calls'] for r in rows),
             'reported_prompt_tokens':sum(u.get('prompt_tokens',0) for u in usage),
             'reported_completion_tokens':sum(u.get('completion_tokens',0) for u in usage),
             'reported_reasoning_tokens':sum(reported) if reported else None,
             'requests_with_reasoning_usage':len(reported),'requests_with_usage':len(usage),
             'api_error_status_counts':dict(api_statuses),
             'api_error_requests':sum(len(r['api_errors']) for r in rows)})
    dump(folder/'failure-and-resource-analysis.json',{'rows':analysis,
        'caveats':['Post-run descriptive analysis, not a new ranking criterion.',
                   'Reasoning tokens are provider-reported; missing usage is not zero inference.',
                   'Failed API requests consume calls and wall time, but their unreported inference tokens cannot be included in the nominal 18000-token allowance.',
                   'seed20261111 identifies the trial/baseline seed; no LLM sampling seed was requested.',
                   'Costs are unknown. Local CPU is equal-capped; upstream inference hardware is not equalized.']})
    lines=['# Failure and resource accounting','',
           'All 36 formal model trials are included. Original development calibration is archived separately and is not pooled into these rows. Safety failure types can overlap within a trial.','',
           '| Route | Split | Complete native evaluations | Feasible | Submission failures | API error requests | Mean CPU (s) |',
           '|---|---|---:|---:|---:|---:|---:|']
    for r in analysis:
        lines.append(f"| {r['model']} | {r['split']} | {r['statuses'].get('verified',0)}/{r['trials']} | {r['feasible']}/{r['trials']} | {r['statuses'].get('submission_failure',0)} | {r['api_error_requests']} | {r['mean_cpu_seconds']:.2f} |")
    lines += ['', 'See the JSON for token totals, reported reasoning-token counts, call counts and safety-failure categories. Failed API requests consume calls and wall time; their token usage and cost are unavailable. Reported token totals therefore do not establish a strict cap on all upstream inference. These observations describe the configured routes and harness. They do not isolate upstream model reasoning ability or establish statistically significant differences.','']
    (folder/'FAILURES.md').write_text('\n'.join(lines))
    print('\n'.join(lines))


if __name__=='__main__':main()

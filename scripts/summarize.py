"""Build a transparent descriptive leaderboard from exported trial records."""
import argparse
import csv
import json
from pathlib import Path
from statistics import mean
from gri_bench.runner import ROOT, dump


def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',default='pilot-v2');p.add_argument('--baseline-tag');args=p.parse_args()
    folder=ROOT/'results'/args.tag
    records=[json.loads(p.read_text()) for p in sorted(folder.glob('*/result.json'))]
    if args.baseline_tag:
        records += [r for p in sorted((ROOT/'results'/args.baseline_tag).glob('*/result.json'))
                    if (r:=json.loads(p.read_text()))['method']!='agent']
    if not records:raise RuntimeError('No verified trial records')
    groups={}
    for record in records:
        method=record['requested_model'] or record['method']
        groups.setdefault((method,record['split']),[]).append(record)
    rows=[]
    for (method,split),group in groups.items():
        scores=[r['score'] for r in group]
        rows.append({'method':method,'split':split,'attempts':len(group),
                     'valid_submissions':sum(s.get('format_valid',False) for s in scores),
                     'feasible_cases':sum(s['feasible'] for s in scores),
                     'feasible_rate':mean(float(s['feasible']) for s in scores),
                     'mean_safe_tir':mean(s['safe_tir'] or 0. for s in scores),
                     'mean_raw_tir_valid_only':mean(s['mean_tir'] for s in scores if s.get('mean_tir') is not None) if any(s.get('mean_tir') is not None for s in scores) else None,
                     'mean_cpu_seconds':mean(r.get('cpu_seconds',0) for r in group),
                     'mean_wall_seconds':mean(r.get('wall_seconds',0) for r in group),
                     'total_prompt_tokens':sum(u.get('prompt_tokens',0) for r in group for u in r['usage']),
                     'total_completion_tokens':sum(u.get('completion_tokens',0) for r in group for u in r['usage']),
                     'api_error_count':sum(len(r['api_errors']) for r in group),
                     'infrastructure_errors':sum(r['status']=='infrastructure_error' for r in group)})
    rows.sort(key=lambda r:(r['split'],-r['feasible_rate'],-r['mean_safe_tir'],r['method']))
    dump(folder/'leaderboard.json',{'label':'Engineering pilot, one run per case/model; no statistical rank claim','agent_profile':args.tag,'reused_baseline_profile':args.baseline_tag,
                                  'failure_denominator':'All attempted cases; infrastructure failures contribute zero to workflow aggregates and are counted separately.',
                                  'rows':rows})
    with (folder/'leaderboard.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    lines=['# Pilot leaderboard','',
           'One run per model/instance. Six development and six sealed cases in one task family. Safety gates were frozen before search. These are route-and-harness results, not authenticated upstream-model rankings. No significance claim.','',
           '| Split | Method / requested route | Valid | Feasible | Mean safe TIR (%) | Mean CPU (s) | API errors |',
           '|---|---|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['split']} | {r['method']} | {r['valid_submissions']}/{r['attempts']} | {r['feasible_cases']}/{r['attempts']} | {r['mean_safe_tir']:.2f} | {r['mean_cpu_seconds']:.2f} | {r['api_error_count']} |")
    lines+=['','`safe_tir` is mean TIR if every trajectory passes all safety gates, and zero otherwise. An infeasible design can have high raw TIR; that does not make it safe. Aggregates include every attempted case. Native solver errors, missing files, API errors, and infrastructure errors are retained in per-trial records.','',
            'The JSON/CSV tables also contain raw TIR (valid trajectories only), wall time, prompt/completion tokens, and infrastructure errors. Actual billing is unavailable. Baseline and agent CPU caps are identical. Provider-default inference effort may differ.','',
            'Development designs, code, transcripts and native traces are open in the per-trial directories. Sealed case details and transcripts remain private; their hashes are included. The full private suite cannot be reproduced from this public repository alone.','']
    (folder/'README.md').write_text('\n'.join(lines))
    print('\n'.join(lines))


if __name__=='__main__':main()

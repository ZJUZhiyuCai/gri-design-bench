"""Complete-matrix reporting for the locally frozen exploratory prescreen."""
import argparse
from collections import defaultdict
import csv
from pathlib import Path
import json
import statistics
import numpy as np
from gri_bench.api import summarize
from .run import EXP,OUT,ROOT,check_plan,read,sha,write_new,design_records,audit_indices


def paired_case_difference(rows,a,b,field='safe_tir'):
    grouped=defaultdict(list)
    for r in rows:grouped[r['method'],r['case']].append(r[field])
    cases=sorted({r['case'] for r in rows})
    values=[statistics.mean(grouped[a,c])-statistics.mean(grouped[b,c]) for c in cases]
    return {'a':a,'b':b,'cases':cases,'differences':values,'mean':statistics.mean(values),
            'positive_cases':sum(v>1e-10 for v in values),'negative_cases':sum(v< -1e-10 for v in values)}


def compute_gates(rows):
    def passes(method):return sum(r['feasible'] for r in rows if r['method']==method)
    validation=paired_case_difference(rows,'de_fixed','de_search')
    adaptive=paired_case_difference(rows,'de_racing','de_fixed')
    means={m:statistics.mean(r['safe_tir'] for r in rows if r['method']==m) for m in {r['method'] for r in rows}}
    best=max(means[m] for m in ('de_search','de_fixed','de_racing','sobol_fixed'))
    return {'validation_gate':validation['mean']>=5 and validation['positive_cases']>=4 and passes('de_fixed')>=passes('de_search')-1,
            'adaptive_gate':adaptive['mean']>=3 and adaptive['positive_cases']>=4 and passes('de_racing')>=passes('de_fixed'),
            'transfer_gate':means['fixed_transfer']>=best-5 and passes('fixed_transfer')>=5,
            'validation_comparison':validation,'adaptive_comparison':adaptive}


def csv_write(path,rows):
    with Path(path).open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    p=check_plan();records=design_records(p);assert len(records)==246
    pairs={(r['case'],r['method'],r['repetition']) for r in records};assert len(pairs)==len(records)
    rows=[];expanded=[];byid={}
    for r in records:
        x=read(OUT/'screen'/f"{r['design_id']}.json");byid[r['design_id']]=x
        assert x['plan_sha256']==sha(EXP/'plan.json')
        for metric,collection in [('primary',rows),('expanded',expanded)]:
            collection.append({k:r[k] for k in ('case','method','repetition','design_id','query_units','cpu_seconds')}|compact_score(x[metric]))
    audits=[];missing=0;original=[]
    for d,x in byid.items():
        for i in audit_indices(x,p):
            path=OUT/'native'/d/f'{i:03}.json'
            if not path.exists():missing+=1;continue
            a=read(path);assert a['trace_sha256']==sha(path.with_suffix('.npz'))
            assert a['plan_sha256']==sha(EXP/'plan.json')
            fast=x['rows'][i]['metrics'];native=a['metrics']
            audits.append({'design_id':d,'index':i,'fast_feasible':summarize([{'metrics':fast}])['feasible'],
                           'native_feasible':summarize([{'metrics':native}])['feasible'],
                           **{k+'_absolute_error':abs(fast[k]-native[k]) for k in ('tir','tbr70','tbr54','minimum')}})
    for r in records:
        if r['method']!='fixed_transfer':continue
        a=OUT/'native'/r['design_id']/'000.json';b=a.with_name('000-original.json')
        if not a.exists() or not b.exists():missing+=1;continue
        aa=np.load(a.with_suffix('.npz'));bb=np.load(b.with_suffix('.npz'))
        maximum=max(float(np.max(np.abs(aa[k]-bb[k]))) for k in aa.files)
        matches=all(np.allclose(aa[k],bb[k],rtol=1e-7,atol=1e-5) for k in aa.files)
        original.append({'case':r['case'],'matched':matches,'maximum_trace_difference':maximum})
    if missing:raise ValueError(f'Native audit incomplete: {missing} required records')
    mismatch=sum(a['fast_feasible']!=a['native_feasible'] for a in audits)
    if not all(a['matched'] for a in original):mismatch+=1
    gates=compute_gates(rows);gates.update(audit_safety_mismatches=mismatch,audited_trajectories=len(audits),original_rhs_checks=original)
    # This immutable decision authorizes only the plan's predetermined extra numerical checks.
    decision=OUT/'screen-decision.json'
    if decision.exists():assert read(decision)==gates
    else:write_new(decision,gates)
    methods=[]
    for name in p['methods']:
        r=[x for x in rows if x['method']==name];e=[x for x in expanded if x['method']==name];feas=[x['mean_tir'] for x in r if x['feasible']]
        methods.append({'method':name,'attempts':len(r),'safe16':sum(x['feasible'] for x in r),'score16':statistics.mean(x['safe_tir'] for x in r),
                        'mean_tir16_all':statistics.mean(x['mean_tir'] for x in r),'conditional_tir16':statistics.mean(feas) if feas else None,
                        'mean_violation_fraction16':statistics.mean(x['violation_fraction'] for x in r),
                        'safe32':sum(x['feasible'] for x in e),'score32':statistics.mean(x['safe_tir'] for x in e),
                        'query_units':r[0]['query_units'],'mean_cpu_seconds':statistics.mean(x['cpu_seconds'] for x in r)})
    contrasts=[('de_fixed','de_search'),('de_racing','de_fixed'),('de_fixed','de_early'),('de_fixed','de_no_margin'),
               ('de_fixed','sobol_fixed'),('de_fixed','constant_fixed'),('constant_fixed','constant_search'),('fixed_transfer','de_fixed')]
    comparisons=[]
    for a,b in contrasts:
        x=paired_case_difference(rows,a,b);rng=np.random.default_rng(2026111388);v=np.array(x['differences'])
        boots=v[rng.integers(len(v),size=(20000,len(v)))].mean(axis=1)
        x['exploratory_case_bootstrap95']=np.quantile(boots,[.025,.975]).tolist()
        x['expanded32_mean']=paired_case_difference(expanded,a,b)['mean'];comparisons.append(x)
    native_confirm=[];confirmation_complete=True
    if gates['validation_gate'] and mismatch==0:
        for r in records:
            if r['method'] not in ('de_search','de_fixed'):continue
            x=byid[r['design_id']];indices=[i for i,t in enumerate(x['rows']) if t['seed'] in p['panels'][r['case']]['evaluation'][:16]]
            paths=[OUT/'native'/r['design_id']/f'{i:03}.json' for i in indices]
            if not all(path.exists() for path in paths):confirmation_complete=False;continue
            score=summarize([{'metrics':read(path)['metrics']} for path in paths])
            native_confirm.append({'case':r['case'],'repetition':r['repetition'],'method':r['method'],**score})
    else:confirmation_complete=False
    preserved=read(EXP/'preservation.json');changed=[n for n,h in preserved.items() if not(ROOT/n).is_file() or sha(ROOT/n)!=h]
    if changed:raise ValueError('Earlier files changed: '+str(changed))
    summary={'plan_sha256':sha(EXP/'plan.json'),'rows':len(rows),'unique_designs':len(byid),'methods':methods,'comparisons':comparisons,
             'gates':gates,'native_confirmation_complete':confirmation_complete,'native_confirmation':native_confirm,
             'protected_files_unchanged':len(preserved),'audit_max_error':{k:max(a[k] for a in audits) for k in ('tir_absolute_error','tbr70_absolute_error','tbr54_absolute_error','minimum_absolute_error')}}
    args.output.mkdir(parents=True,exist_ok=False)
    write_new(args.output/'summary.json',summary);csv_write(args.output/'attempts.csv',rows);csv_write(args.output/'expanded32.csv',expanded);csv_write(args.output/'methods.csv',methods);csv_write(args.output/'native-audit.csv',audits)
    write_new(args.output/'paired-cases.json',comparisons)
    lines=['# 搜索与验证预算：无模型预筛结果','',
           '本轮为六个已见开发患者组上的探索性研究；进餐面板新生成并在运行前本地冻结。未测试新 Agent，未发布。',
           '主分数由 RK4 筛查得到，原生积分器只复核预先指定的样本和全部阈值附近轨迹；不要把选择性复核称为全部设计原生验证。','',
           '| 方法 | 门槛通过 / 次数（16种子） | 全尝试分数 | 32种子分数 | 查询预算 |', '|---|---:|---:|---:|---:|']
    for r in methods:lines.append(f"| {r['method']} | {r['safe16']}/{r['attempts']} | {r['score16']:.2f} | {r['score32']:.2f} | {r['query_units']} |")
    lines+=['','## 冻结判定', '',f"- 固定验证改善门槛：{gates['validation_gate']}。",f"- 自适应验证额外改善门槛：{gates['adaptive_gate']}。",f"- 固定迁移接近在线最优门槛：{gates['transfer_gate']}。",f"- 原生抽检 {len(audits)} 条轨迹，安全分类差异 {mismatch}；原始 RHS 对照 {len(original)} 条。",f"- 完整主要比较原生确认：{confirmation_complete}。",'',
           '这些门槛是预筛决策规则，不是显著性或等效性检验。对照按实例配对，五次重复不增加六个患者组的自由度。', '', '## 主要比较（百分点）','', '| 比较 | 均差 | 正向实例 /6 | 32种子均差 |', '|---|---:|---:|---:|']
    for x in comparisons:lines.append(f"| {x['a']} − {x['b']} | {x['mean']:.2f} | {x['positive_cases']} | {x['expanded32_mean']:.2f} |")
    lines+=['','## 解释边界','',
            '- 固定验证、逐级淘汰与纯搜索的主预算相同，但候选数和独立验证面板分配不同。de_early 只有半预算；de_no_margin 只改验证选择门槛；两者是机制消融。',
            '- 固定迁移排除目标实例设计，使用其他五例的历史精修设计中位数并裁剪到目标边界。在线零查询不等于历史计算成本为零，且这些患者组不是全新外部人群。',
            '- CPU 表用于资源描述；相同查询数不保证相同 CPU，更不等于原 v0.2 的30 CPU秒。本表不能直接与历史 Agent 排行榜作公平胜负判断。',
            '- 同一生理模型、六个已见患者组、小样本、单一参数包络体系；条件TIR与门槛通过率须同时解释，不推断临床安全。',
            f"- 原有 {len(preserved)} 个受保护文件摘要未变。",'',
            '[机器可读摘要](summary.json) · [逐次结果](attempts.csv) · [32种子敏感性](expanded32.csv) · [逐实例配对](paired-cases.json) · [原生抽检](native-audit.csv)','']
    (args.output/'README.md').write_text('\n'.join(lines))
    print(json.dumps({'methods':methods,'gates':gates,'output':str(args.output)},ensure_ascii=False),flush=True)

def compact_score(m):return {k:m[k] for k in ('safe_tir','mean_tir','feasible','max_trajectory_tbr70','max_trajectory_tbr54','minimum_glucose','failed_trajectories','violation_fraction')}

if __name__=='__main__':main()

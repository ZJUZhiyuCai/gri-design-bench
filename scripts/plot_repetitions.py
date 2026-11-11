"""Export the three-round sealed-case stability figure from audited summaries."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from gri_bench.runner import ROOT

folder=ROOT/'results/repetitions-2026-11-11'
data=json.loads((folder/'summary.json').read_text())
audit=json.loads((folder/'audit.json').read_text())
assert audit['passed'] and audit['planned_and_audited_attempts']==108
models=json.loads((ROOT/'contract/pilot-models.json').read_text())['models']
labels=['GPT-6.1 Sol route','DeepSeek V4.1-1017 route','GLM-5.3 route']
colors=['#2563eb','#0f766e','#9333ea'];markers=['o','s','^']
rows={r['model']:r for r in data['rows'] if r['split']=='sealed'}
assert set(rows)==set(models) and all(r['attempts']==18 for r in rows.values())
fig,axes=plt.subplots(1,2,figsize=(12,6.2))
fig.subplots_adjust(left=.07,right=.98,top=.82,bottom=.24,wspace=.27)
x=np.arange(1,4)
reference=next(r['mean_safe_tir'] for r in data['baseline_single_run_reference'] if r['split']=='sealed' and r['method']=='constant_grid')
for i,(model,label,color,marker) in enumerate(zip(models,labels,colors,markers)):
    row=rows[model];xx=x+(i-1)*.035
    axes[0].plot(xx,row['round_means'],marker=marker,color=color,linewidth=2,markersize=7,label=label)
    axes[1].plot(xx,row['feasible_per_round'],marker=marker,color=color,linewidth=2,markersize=7,label=label)
    for xp,y in zip(xx,row['round_means']):
        offset=[9,-16,9][i]
        if i==1 and 0<y-reference<7:offset=9
        axes[0].annotate(f'{y:.1f}',(xp,y),xytext=(0,offset),textcoords='offset points',ha='center',color=color,fontsize=9)
axes[0].axhline(reference,color='#64748b',linestyle='--',linewidth=1.4,label='Original constant-grid reference')
axes[0].set(ylabel='Mean safe TIR (%)',ylim=(0,100),title='Quality across three new repetitions')
axes[1].set(ylabel='Cases passing every safety gate',ylim=(-.3,6.6),yticks=range(7),title='Feasibility across six fixed sealed cases')
for ax in axes:
    ax.set_xticks(x,['Round 1','Round 2','Round 3']);ax.set_xlim(.7,3.3)
    ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2)
fig.suptitle('GRI Design Bench · three additional repetitions\nSame frozen task and configured budgets; failed calls count toward token cap',fontsize=14,fontweight='bold')
handles,legend_labels=axes[0].get_legend_handles_labels()
fig.legend(handles,legend_labels,loc='lower center',bbox_to_anchor=(.5,.075),ncol=2,frameon=False,fontsize=10)
exceptions=sum(r['split']=='sealed' for r in data['resource_sensitivity']['exceptions'])
fig.text(.5,.015,'Points are round means/counts, not confidence intervals. Baseline: one original attempt per case.\n'
         f'Native task scores shown. Resource exceptions in sealed attempts: {exceptions}/54; see companion zero-score sensitivity.',
         ha='center',va='bottom',fontsize=9.5)
fig.savefig(folder/'stability.png',dpi=180)
fig.savefig(folder/'stability.svg')
svg=folder/'stability.svg';svg.write_text('\n'.join(s.rstrip() for s in svg.read_text().splitlines())+'\n')
print(folder/'stability.png')

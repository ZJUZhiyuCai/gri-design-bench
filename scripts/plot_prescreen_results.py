"""Render figures from the saved complete prescreen report; never run experiments."""
import argparse
import csv
import json
from pathlib import Path
from collections import defaultdict
import statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

LABELS={'de_search':'DE: search only','de_fixed':'DE: fixed validation','de_racing':'DE: racing validation',
        'sobol_fixed':'Sobol: fixed validation','constant_search':'Constant: search only',
        'constant_fixed':'Constant: fixed validation','de_no_margin':'DE: no selection margin',
        'de_early':'DE: early checkpoint (half budget)','fixed_transfer':'Fixed transfer (offline donors)'}
COLORS={'de_search':'#46556A','de_fixed':'#245CC0','de_racing':'#B88722'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('report',type=Path);args=parser.parse_args()
    data=json.loads((args.report/'summary.json').read_text());rows=list(csv.DictReader((args.report/'attempts.csv').open()))
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                         'axes.labelcolor':'#263245','text.color':'#263245','xtick.color':'#475569','ytick.color':'#475569',
                         'svg.fonttype':'none','axes.titlesize':12,'axes.titleweight':'bold'})
    methods=data['methods'];grouped=defaultdict(list)
    for r in rows:grouped[r['method'],r['case']].append(float(r['safe_tir']))
    fig,(ax,bx)=plt.subplots(1,2,figsize=(12.6,6.6),gridspec_kw={'width_ratios':[3.2,1.5]})
    fig.subplots_adjust(left=.28,right=.95,top=.82,bottom=.15,wspace=.35)
    for i,r in enumerate(methods):
        color=COLORS.get(r['method'],'#64748B')
        values=[statistics.mean(grouped[r['method'],c]) for c in sorted({x['case'] for x in rows})]
        ax.scatter(values,[i]*6,s=25,facecolors='white',edgecolors='#94A3B8',linewidths=1,zorder=2)
        ax.scatter(r['score16'],i,s=65,c=color,zorder=3)
        ax.scatter(r['score32'],i,s=65,marker='s',facecolors='none',edgecolors=color,linewidths=1.4,zorder=4)
        bx.barh(i,100*r['safe16']/r['attempts'],height=.5,color=color)
        bx.text(103,i,f"{r['safe16']}/{r['attempts']}",va='center',fontsize=10)
    ax.set_yticks(range(len(methods)),[LABELS[r['method']] for r in methods]);ax.invert_yaxis()
    bx.set_yticks(range(len(methods)),[]);bx.invert_yaxis();ax.set_ylim(len(methods)-.4,-.6);bx.set_ylim(len(methods)-.4,-.6)
    ax.set_xlim(0,100);ax.set_xlabel('Safety-gated TIR score (%)');ax.set_title('A  Scores and cohort heterogeneity',loc='left',pad=16)
    bx.set_xlim(0,125);bx.set_xticks([0,50,100]);bx.set_xlabel('Passing attempts (%)');bx.set_title('B  Safety gates, 16 seeds',loc='left',pad=16)
    ax.grid(axis='x',color='#E2E8F0',lw=.7);ax.set_axisbelow(True);bx.spines['left'].set_visible(False)
    from matplotlib.lines import Line2D
    legend=[Line2D([],[],marker='o',ls='',color='#245CC0',label='16-seed mean'),
            Line2D([],[],marker='s',ls='',markerfacecolor='none',color='#245CC0',label='32-seed mean'),
            Line2D([],[],marker='o',ls='',markerfacecolor='white',markeredgecolor='#94A3B8',label='Individual cohort mean')]
    fig.legend(handles=legend,loc='upper left',bbox_to_anchor=(.28,.925),ncol=3,frameon=False,fontsize=9)
    fig.suptitle('Search and validation under a fixed simulation-query budget',x=.04,y=.985,ha='left',fontsize=15,fontweight='bold')
    fig.text(.04,.045,'Exploratory RK4 screen; selective native audit. Six previously seen, disjoint patient groups.\nFive optimizer seeds per online method; fixed transfer has one design per group. Gray dots are not confidence intervals.',fontsize=9,color='#475569')
    for ext in ('png','svg'):
        target=args.report/f'comparison.{ext}'
        if target.exists():raise FileExistsError(target)
        fig.savefig(target,dpi=180,facecolor='white')
    plt.close(fig)
    comparisons=data['comparisons'];selected=[next(x for x in comparisons if (x['a'],x['b'])==pair) for pair in [('de_fixed','de_search'),('de_racing','de_fixed'),('de_fixed','constant_fixed')]]
    fig,ax=plt.subplots(figsize=(9,5.6));fig.subplots_adjust(left=.12,right=.95,top=.76,bottom=.2)
    labels=['Fixed validation − search','Racing − fixed validation','Responsive − constant (both validated)'];colors=['#245CC0','#B88722','#46556A'];markers=['o','s','D']
    for j,(x,label,color,marker) in enumerate(zip(selected,labels,colors,markers)):
        offset=(j-1)*.16;y=np.arange(6)+offset
        ax.scatter(x['differences'],y,c=color,marker=marker,s=45,label=f"{label}  (mean {x['mean']:+.2f} pp)")
    ax.axvline(0,color='#334155',lw=1);ax.set_yticks(range(6),selected[0]['cases']);ax.invert_yaxis()
    ax.set_xlabel('Paired difference in 16-seed safety-gated score (percentage points)');ax.grid(axis='x',color='#E2E8F0',lw=.7);ax.set_axisbelow(True)
    fig.suptitle('The six cohort-level paired effects',x=.04,y=.98,ha='left',fontsize=15,fontweight='bold')
    fig.legend(loc='upper left',bbox_to_anchor=(.11,.93),frameon=False,fontsize=9)
    fig.text(.04,.045,'Each point averages five matched optimizer seeds within one cohort.\nExploratory comparisons on known virtual patients; no clinical or Agent capability claim.',fontsize=9,color='#475569')
    for ext in ('png','svg'):
        target=args.report/f'paired-effects.{ext}'
        if target.exists():raise FileExistsError(target)
        fig.savefig(target,dpi=180,facecolor='white')
    print(args.report/'comparison.png')

if __name__=='__main__':main()

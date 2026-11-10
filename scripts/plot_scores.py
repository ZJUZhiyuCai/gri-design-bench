"""Static scientific scorecard; all values come from exported verified records."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from gri_bench.runner import ROOT

folder=ROOT/'results/pilot-v2'
records=[json.loads(p.read_text()) for p in folder.glob('*/result.json')]
records += [r for p in (ROOT/'results/pilot-v1').glob('*/result.json')
            if (r:=json.loads(p.read_text()))['method']!='agent']
methods=['constant_grid','sobol','differential_evolution']+json.loads((ROOT/'contract/pilot-models.json').read_text())['models']
labels=['Constant grid','Sobol search','Differential evolution','GPT-6.1 Sol route','DeepSeek V4.1-1017 route','GLM-5.3 route']
cases=[f'{split}-{i:02d}' for split in ['dev','sealed'] for i in range(1,7)]
values=np.full((len(cases),len(methods)),np.nan);feasible=np.zeros_like(values,dtype=bool)
for r in records:
    method=r['requested_model'] or r['method']
    if method not in methods:continue
    i=cases.index(r['instance_id']);j=methods.index(method)
    values[i,j]=r['score']['safe_tir'] or 0.
    feasible[i,j]=r['score']['feasible']
if not np.isfinite(values).all():raise RuntimeError('Incomplete matrix: refusing a complete-looking chart')
fig,ax=plt.subplots(figsize=(11,7.5),layout='constrained')
im=ax.imshow(values,vmin=0,vmax=100,cmap='viridis',aspect='auto')
for i in range(len(cases)):
    for j in range(len(methods)):
        text=f'{values[i,j]:.1f}' if feasible[i,j] else '0 ×'
        ax.text(j,i,text,ha='center',va='center',color='black' if values[i,j]>65 else 'white',fontsize=10)
ax.set_xticks(range(len(methods)),labels,rotation=22,ha='right')
ax.set_yticks(range(len(cases)),cases)
ax.axhline(5.5,color='white',linewidth=3);ax.axvline(2.5,color='white',linewidth=2)
ax.set_title('GRI Design Bench · first pilot\nSafe TIR (%) on independently resimulated scenarios',loc='left',fontweight='bold',pad=16)
fig.colorbar(im,ax=ax,label='Mean TIR, gated by all trajectory safety constraints',shrink=.8)
fig.supxlabel('× = safety / submission failure. One run per case and route; no stable model ranking claim.',fontsize=10)
fig.savefig(folder/'scorecard.png',dpi=180)
fig.savefig(folder/'scorecard.svg')
svg=folder/'scorecard.svg'
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
print(folder/'scorecard.png')

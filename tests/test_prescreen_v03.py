from pathlib import Path
import pytest
from gri_bench.api import load_instance, summarize
from gri_bench.prescreen_v03.search import Panel,candidate_search,shortlist,validate_fixed,race,transfer_design,key
ROOT=Path(__file__).resolve().parents[1]
@pytest.fixture
def instance():return load_instance(ROOT/'instances/dev/dev-01.json')
class FakePanel:
    def __init__(self):self.queries=0
    def evaluate(self,d,seeds):
        self.queries+=len(seeds);p=d['parameters'];a=p.get('theta_a',p.get('theta_c'))
        target=.0003 if max(seeds)<100 else .00015
        tir=max(0.,80.-abs(a-target)*100000);tbr=0. if a<=target*2 else 8.
        rows=[{'seed':s,'metrics':{'tir':tir,'tbr70':tbr,'tbr54':0.,'minimum':90.}} for s in seeds]
        return {**summarize(rows),'rows':rows}
def test_common_search_prefix_and_unique_shortlist(instance):
    a,_=candidate_search(instance,[1,2],17,64,panel=FakePanel())
    b,_=candidate_search(instance,[1,2],17,128,panel=FakePanel())
    assert [(r['design'],r['training']) for r in a]==[(r['design'],r['training']) for r in b[:64]]
    chosen=shortlist(a)
    assert len({key(r['design']) for r in chosen})==8
    assert chosen[-1]['design']['parameters']['theta_a']==0
def test_validation_budget_and_racing_zero_fallback(instance):
    records,_=candidate_search(instance,[1,2],18,64,panel=FakePanel());finalists=shortlist(records);seeds=list(range(101,145))
    fixed,fp=validate_fixed(instance,finalists,seeds[:16],panel=FakePanel())
    selected,stages,rp=race(instance,finalists,seeds,panel=FakePanel())
    assert fp.queries==rp.queries==128
    assert [len(s['candidates']) for s in stages]==[8,4,2]
    assert [s['total_seeds'] for s in stages]==[4,12,44]
    assert all(any(c['design']['parameters']['theta_a']==0 for c in s['candidates']) for s in stages)
    assert selected['validation']['feasible']
def test_query_guard_prevents_execution(instance,monkeypatch):
    calls=[]
    class MockExperiment:
        def __init__(self,*args,**kwargs):pass
        def evaluate(self,d):calls.append(d);return FakePanel().evaluate(d,[1,2])
    monkeypatch.setattr('gri_bench.prescreen_v03.search.Experiment',MockExperiment)
    d={'mode':'constant','parameters':{'theta_c':.0002,'theta_L':1.}}
    panel=Panel(instance,2);panel.evaluate(d,[1,2])
    with pytest.raises(ValueError,match='budget'):panel.evaluate(d,[3])
    assert len(calls)==1 and panel.queries==2
def test_transfer_excludes_target(instance):
    def r(name,a):return {'case':name,'design':{'mode':'responsive','parameters':dict(zip(('theta_a','relative_leak','ec50_mg_dl','hill_n','tau_min','theta_L'),(a,1.,150.,2.,5.,2.)))}}
    src=[r('dev-01',.001),r('dev-02',.0002),r('dev-03',.0004)]
    a,donors=transfer_design(instance,src);src[0]['design']['parameters']['theta_a']=.007;b,_=transfer_design(instance,src)
    assert a==b and donors==['dev-02','dev-03']
    assert a['parameters']['theta_a']==pytest.approx(.0003)

def test_no_margin_ablation_can_change_selection_without_new_queries(instance):
    from gri_bench.prescreen_v03.search import loss
    conservative={'mean_tir':60.,'max_trajectory_tbr70':2.,'max_trajectory_tbr54':0.,'minimum_glucose':60.}
    near={'mean_tir':85.,'max_trajectory_tbr70':3.5,'max_trajectory_tbr54':.75,'minimum_glucose':43.}
    assert loss(conservative)<loss(near)
    assert loss(conservative,False)>loss(near,False)

def test_native_index_mapping_matches_public_experiment(instance,monkeypatch):
    from gri_bench.prescreen_v03 import run
    from gri_bench.api import Experiment
    p={'instances':{'dev-01':instance},'panels':{'dev-01':{'evaluation':[111,222]}}}
    monkeypatch.setattr(run,'check_plan',lambda:p)
    run.native_input.cache_clear()
    expected=Experiment(instance,seeds=[111,222])
    import numpy as np
    for i in (0,2,5,6,13,17):
        name,seed,variant,meals=run.native_input('dev-01',i)
        e=expected.jobs[i]
        assert (name,seed,variant)==e[:3]
        np.testing.assert_array_equal(meals,e[-1])
    run.native_input.cache_clear()

def test_gates_use_case_means_not_pooled_trajectory_count():
    from gri_bench.prescreen_v03.analyze import compute_gates,paired_case_difference
    rows=[]
    for c in range(6):
        for method,score in [('de_search',40),('de_fixed',46),('de_racing',47),('sobol_fixed',42),('fixed_transfer',30)]:
            for rep in range(1 if method=='fixed_transfer' else 5):
                rows.append({'case':str(c),'method':method,'safe_tir':score,'feasible':True})
    g=compute_gates(rows)
    assert g['validation_gate'] and not g['adaptive_gate'] and not g['transfer_gate']
    assert paired_case_difference(rows,'de_fixed','de_search')['differences']==[6]*6

def test_frozen_numeric_safety_audit_selection():
    from gri_bench.prescreen_v03.run import audit_indices
    p={'panels':{'x':{'evaluation':[1,2]}}}
    r={'case':'x','rows':[{'seed':1,'metrics':{'tbr70':0,'tbr54':0,'minimum':90}},
         {'seed':2,'metrics':{'tbr70':3.6,'tbr54':0,'minimum':90}},
         {'seed':2,'metrics':{'tbr70':0,'tbr54':0,'minimum':90}}]}
    assert audit_indices(r,p)==[0,1]

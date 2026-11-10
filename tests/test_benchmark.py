import copy
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from gri_bench.api import load_instance, validate_design, individual_design, glucose_metrics, summarize
from gri_bench.physiology import fast_trace, patient_parameters, meal_schedule
from gri_bench.native import native_trace
from gri_bench.evaluate import strict_json

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def case(): return load_instance(ROOT/'instances/dev/dev-01.json')


@pytest.fixture
def design():
    return {'mode':'responsive','parameters':{'theta_a':.0002,'relative_leak':1.,'ec50_mg_dl':150.,'hill_n':4.,'tau_min':10.,'theta_L':2.}}


def test_validation_and_scaling(case,design):
    validate_design(design,case)
    a=individual_design(design,20); b=individual_design(design,40)
    np.testing.assert_equal(b[[0,5]],a[[0,5]]*2)
    np.testing.assert_equal(b[1:5],a[1:5])
    for val in [float('nan'),float('inf'),True,-1,1.]:
        bad=copy.deepcopy(design);bad['parameters']['theta_a']=val
        with pytest.raises(ValueError):validate_design(bad,case)
    bad=copy.deepcopy(design);bad['extra']=1
    with pytest.raises(ValueError):validate_design(bad,case)
    bad=copy.deepcopy(design);bad['parameters']['child#001']=.1
    with pytest.raises(ValueError):validate_design(bad,case)


def test_all_trajectories_safety_and_warmup():
    rows=[{'metrics':{'tir':90.,'tbr70':0.,'tbr54':0.,'minimum':90.}} for _ in range(18)]
    assert summarize(rows)['safe_tir']==90
    rows[-1]['metrics']={'tir':90.,'tbr70':4.1,'tbr54':0.,'minimum':50.}
    assert summarize(rows)['safe_tir']==0  # cannot hide an unsafe case in the mean
    rows[-1]['metrics']={'tir':90.,'tbr70':0.,'tbr54':0.,'minimum':39.99}
    assert not summarize(rows)['feasible']
    trace=np.full((1440,5),100.); minute=np.full(4321,100.);minute[10]=30.
    m=glucose_metrics(trace,minute_plasma=minute)
    assert m['tir']==100 and m['minimum']==30


@pytest.mark.parametrize('mode',['constant','responsive'])
def test_reservoir_mass_conservation(mode):
    p,x=patient_parameters('adult#001'); d=np.array([.2,-1. if mode=='constant' else 1.,150.,4.,10.,.7])
    trace=fast_trace(p,x,np.zeros(60),d)
    assert np.all(trace[:,3]>=0)
    assert np.sum(trace[:,2]*3)<=.7+1e-12
    assert trace[-1,3]==0


def test_native_equivalence_and_no_controller_state_carryover(case,design):
    p,x=patient_parameters('adult#001');meals=meal_schedule(71001)*p.BW/86.0704
    d=individual_design(design,case['tdi']['adult#001'])
    fast=fast_trace(p,x,meals,d); native,minute=native_trace('adult#001',meals,d)
    assert np.max(np.abs(fast[:,0]-native[:,0]))<1.
    a=glucose_metrics(fast);b=glucose_metrics(native,minute_plasma=minute)
    assert abs(a['tir']-b['tir'])<=.25
    # Repeated requests must not inherit the previous candidate's reservoir.
    np.testing.assert_array_equal(fast,fast_trace(p,x,meals,d))


def test_compiled_rhs_matches_upstream_native(design,case):
    p,x=patient_parameters('child#001');meals=meal_schedule(71001)[:180]*p.BW/86.0704
    d=individual_design(design,20.)
    a,_=native_trace('child#001',meals,d)
    b,_=native_trace('child#001',meals,d,original_rhs=True)
    np.testing.assert_allclose(a,b,rtol=1e-7,atol=1e-5)


def test_six_plus_six_and_committed_bound_envelopes():
    cases=sorted((ROOT/'instances/dev').glob('dev-??.json'))
    assert len(cases)==6
    manifest=json.loads((ROOT/'contract/sealed-manifest.json').read_text())
    assert len(manifest['files'])==6
    base=json.loads((ROOT/'contract/contract.json').read_text())['design']['base_bounds']
    inputs=[json.loads(p.read_text()) for p in cases]
    for id,expected in manifest['files'].items():
        p=ROOT/f'private/sealed/{id}.json'
        if p.exists():
            assert hashlib.sha256(p.read_bytes()).hexdigest()==expected
            inputs.append(json.loads(p.read_text())['instance'])
    for c in inputs:
        assert len(c['patients'])==3 and len(set(c['patients']))==3
        for k,(lo,hi) in c['bounds'].items():
            assert base[k][0]<=lo<=hi<=base[k][1]


def test_duplicate_and_nonfinite_json_rejected(tmp_path):
    for txt in ['{"a":1,"a":2}','{"a":NaN}','{"a":Infinity}']:
        p=tmp_path/'bad.json';p.write_text(txt)
        with pytest.raises(ValueError):strict_json(p)


def test_image_allowlist_has_no_instances_or_secrets():
    docker=(ROOT/'Dockerfile').read_text()
    copies=[s for s in docker.splitlines() if s.startswith('COPY ')]
    assert all('private' not in s and 'instances' not in s and '.config' not in s for s in copies)
    assert not any(s.startswith('COPY . ') for s in copies)
    assert 'USER agent' in docker

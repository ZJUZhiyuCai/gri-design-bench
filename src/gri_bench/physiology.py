"""simglucose 0.2.11 physiology; fast training integrator, native final integrator.

The rhs below is a numerical transcription of T1DPatient.model (MIT,
Copyright (c) 2017 Jinyu Xie). Equations, units and meal bookkeeping are unchanged.
Native final runs use T1DSimEnv and its original dopri5 solver; a compiled rhs
only removes pandas attribute overhead. Tests compare the original rhs directly.
"""
from datetime import datetime, timedelta
from collections import namedtuple
from pathlib import Path
import numpy as np
import pandas as pd
from numba import njit
from simglucose.patient.t1dpatient import T1DPatient, PATIENT_PARA_FILE
from simglucose.simulation.scenario_gen import RandomScenario
from simglucose.simulation.env import T1DSimEnv
from simglucose.sensor.cgm import CGMSensor
from simglucose.controller.base import Action
from simglucose.controller.basal_bolus_ctrller import BBController

FIELDS = 'BW kmax kmin b d kabs f kp1 kp2 kp3 Fsnc ke1 ke2 k1 k2 Vm0 Vmx Km0 m2 m4 m1 ka1 ka2 Vi p2u Ib ki m30 kd ksc Vg u2ss'.split()
Parameters = namedtuple('Parameters', FIELDS)
START = datetime(2025, 1, 1)


def patient_parameters(name):
    row = pd.read_csv(PATIENT_PARA_FILE).set_index('Name', drop=False).loc[name]
    return Parameters(*(float(row[k]) for k in FIELDS)), row.iloc[2:15].to_numpy(dtype=float)


@njit(cache=True)
def rhs(x, cho, insulin_rate, p, last_q, last_food):
    dx = np.zeros(13)
    d = cho * 1000
    insulin = insulin_rate * 6000 / p.BW
    qsto = x[0] + x[1]
    dbar = last_q + last_food * 1000
    dx[0] = -p.kmax * x[0] + d
    if dbar > 0:
        aa = 5 / (2 * dbar * (1-p.b)); cc = 5 / (2*dbar*p.d)
        kgut = p.kmin + (p.kmax-p.kmin)/2 * (np.tanh(aa*(qsto-p.b*dbar))-np.tanh(cc*(qsto-p.d*dbar))+2)
    else:
        kgut = p.kmax
    dx[1] = p.kmax*x[0] - x[1]*kgut
    dx[2] = kgut*x[1] - p.kabs*x[2]
    rat = p.f*p.kabs*x[2]/p.BW
    egp = p.kp1-p.kp2*x[3]-p.kp3*x[8]
    excretion = p.ke1*(x[3]-p.ke2) if x[3] > p.ke2 else 0.
    dx[3] = (x[3]>=0)*(max(egp,0.)+rat-p.Fsnc-excretion-p.k1*x[3]+p.k2*x[4])
    uid = (p.Vm0+p.Vmx*x[6])*x[4]/(p.Km0+x[4])
    dx[4] = (x[4]>=0)*(-uid+p.k1*x[3]-p.k2*x[4])
    dx[5] = (x[5]>=0)*(-(p.m2+p.m4)*x[5]+p.m1*x[9]+p.ka1*x[10]+p.ka2*x[11])
    it = x[5]/p.Vi
    dx[6] = -p.p2u*x[6]+p.p2u*(it-p.Ib)
    dx[7] = -p.ki*(x[7]-it)
    dx[8] = -p.ki*(x[8]-x[7])
    dx[9] = (x[9]>=0)*(-(p.m1+p.m30)*x[9]+p.m2*x[5])
    dx[10] = (x[10]>=0)*(insulin-(p.ka1+p.kd)*x[10])
    dx[11] = (x[11]>=0)*(p.kd*x[10]-p.ka2*x[11])
    dx[12] = (x[12]>=0)*(-p.ksc*x[12]+p.ksc*x[3])
    return dx


def meal_schedule(seed, days=3, variant='ordinary'):
    """Call the real RandomScenario at each minute, including midnight resets."""
    scenario = RandomScenario(START, seed=seed)
    meals = np.array([scenario.get_action(START+timedelta(minutes=t)).meal for t in range(days*1440)], dtype=float)
    # Both challenges are defined on day 2; the ordinary warmup is preserved.
    if variant == 'missed_lunch':
        meals[1440+600:1440+840] = 0.
    elif variant == 'large_dinner':
        meals[1440+960:1440+1201] *= 1.5
    elif variant != 'ordinary':
        raise ValueError(variant)
    return meals


@njit(cache=True)
def fast_trace(p, initial, meals, design, substeps=4):
    """Three-minute controller, one-minute meals, RK4 at 0.25 min by default.

    design = [amplitude, leak, EC50, n, tau, load]; constant uses leak=-1, with a finite reservoir.
    Plasma glucose (state[3]/Vg) is the primary physiological outcome.
    """
    x = initial.copy()
    output = np.empty((len(meals)//3, 5))
    interval_min = x[3]/p.Vg
    pending = 0.; last_cho = 0.; last_q = x[0]+x[1]; food = 0.; eating = False
    geff = 0.; remaining = design[5]; rate = 0.; dt = 1./substeps
    for minute in range(len(meals)):
        if minute % 3 == 0:
            if design[1] < 0:
                rate = min(design[0], remaining/3.)
                remaining = max(0.,remaining-3.*rate)
            else:
                g = max(0., x[12]/p.Vg)
                mid = g+(geff-g)*np.exp(-1.5/design[4])
                geff = g+(geff-g)*np.exp(-3./design[4])
                z = design[3]*(np.log(design[2])-np.log(max(mid,1e-300)))
                response = 1./(1.+np.exp(min(700.,max(-700.,z))))
                rate = min(design[0]*(design[1]+response),remaining/3.)
                remaining = max(0.,remaining-3.*rate)
        pending += meals[minute]
        cho = min(5.,pending); pending = max(0.,pending-cho)
        if cho > 0 and last_cho <= 0:
            last_q = x[0]+x[1]; food = 0.; eating = True
        if eating:
            food += cho
        if cho <= 0 and last_cho > 0:
            eating = False
        last_cho = cho
        for j in range(substeps):
            k1 = rhs(x,cho,rate,p,last_q,food)
            k2 = rhs(x+dt*k1/2,cho,rate,p,last_q,food)
            k3 = rhs(x+dt*k2/2,cho,rate,p,last_q,food)
            k4 = rhs(x+dt*k3,cho,rate,p,last_q,food)
            x += dt/6*(k1+2*k2+2*k3+k4)
        interval_min = min(interval_min, x[3]/p.Vg)
        if minute % 3 == 2:
            output[minute//3] = np.array([x[3]/p.Vg,x[12]/p.Vg,rate,remaining,interval_min])
            interval_min = x[3]/p.Vg
    return output


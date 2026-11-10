"""Trusted native resimulation. Never executes code from a submission."""
from collections import namedtuple
from datetime import timedelta
import numpy as np
from simglucose.patient.t1dpatient import T1DPatient
from simglucose.sensor.cgm import CGMSensor
from simglucose.controller.base import Action
from simglucose.simulation.env import T1DSimEnv
from .physiology import START, patient_parameters, rhs
from .release import release_step
from .api import Experiment, individual_design, validate_design, glucose_metrics, summarize


class DirectInput:
    def basal(self, x): return float(x)
    def bolus(self, x): return float(x)
    def reset(self): pass


class ScheduledMeals:
    def __init__(self, meals):
        self.start_time = START; self.meals = meals
    def get_action(self, t):
        minute = int((t-START).total_seconds()/60)
        return namedtuple('Meal', 'meal')(float(self.meals[minute]) if minute < len(self.meals) else 0.)
    def reset(self): pass


class AuditedEnvironment(T1DSimEnv):
    def mini_step(self, action):
        result = super().mini_step(action)
        if not self.patient._odesolver.successful() or not np.isfinite(self.patient.state).all():
            raise ValueError('Native ODE solver failure or nonfinite state')
        self.minute_plasma.append(float(self.patient.state[3]/self.patient._params.Vg))
        return result


def native_trace(name, meals, design, patient_seed=2026111101, original_rhs=False):
    p, _ = patient_parameters(name)
    patient = T1DPatient.withName(name, seed=patient_seed, random_init_bg=False)
    if not original_rhs:
        def compiled(t, x, action, params, last_q, last_food):
            return rhs(x, float(action.CHO), float(action.insulin), p, last_q, last_food)
        patient.model = compiled
        patient.reset()
    env = AuditedEnvironment(patient, CGMSensor.withName('Dexcom', seed=1), DirectInput(), ScheduledMeals(meals))
    env.reset(); env.minute_plasma = [float(patient.state[3]/p.Vg)]
    effective = 0.; remaining = float(design[5]); rows = []
    for minute in range(0, len(meals), 3):
        if design[1] < 0:
            rate = min(float(design[0]), remaining/3.); remaining = max(0., remaining-rate*3.)
        else:
            rate, effective, remaining = release_step(float(patient.state[12]/p.Vg), effective, remaining, 3., *design[:5])
        env.step(Action(basal=rate, bolus=0.))
        rows.append([patient.state[3]/p.Vg, patient.state[12]/p.Vg, rate, remaining, min(env.minute_plasma[-3:])])
    return np.asarray(rows), np.asarray(env.minute_plasma)


def verify_design(instance, design, seeds, trace_path=None):
    validate_design(design, instance)
    experiment = Experiment(instance, seeds=seeds)
    rows, traces = [], {}
    for i, (name, seed, variant, p, initial, meals) in enumerate(experiment.jobs):
        trace, minute = native_trace(name, meals, individual_design(design, instance['tdi'][name]), instance['patient_seed'])
        rows.append({'patient': name, 'seed': seed, 'variant': variant,
                     'metrics': glucose_metrics(trace, instance['warmup_minutes'], minute)})
        traces[f'trace_{i:02d}'] = trace
        traces[f'minute_{i:02d}'] = minute
    if trace_path:
        np.savez_compressed(trace_path, **traces)
    return {**summarize(rows), 'rows': rows, 'format_valid': True, 'native_integrator': 'simglucose-dopri5'}

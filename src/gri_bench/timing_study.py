"""Paired, dose-matched replays in the existing virtual-patient model."""

import numpy as np
from simglucose.patient.t1dpatient import Action, T1DPatient

from .api import glucose_metrics, individual_design
from .native import native_trace
from .physiology import patient_parameters, rhs


STEPS_PER_DAY = 480
MINUTES_PER_STEP = 3
ARMS = ("responsive", "daily_flat", "daily_shift_12h")
METRICS = ("tir", "tbr70", "tbr54", "minimum")


def replay_rates(responsive):
    """Hold day one fixed and preserve each later day's total insulin."""
    days = np.asarray(responsive, dtype=float).reshape(3, STEPS_PER_DAY)
    flat = days.copy()
    flat[1:] = days[1:].mean(axis=1, keepdims=True)
    shifted = days.copy()
    shifted[1:] = np.roll(days[1:], STEPS_PER_DAY // 2, axis=1)
    return {ARMS[1]: flat.ravel(), ARMS[2]: shifted.ravel()}


def replay(patient_name, meals, rates, patient_seed):
    """Apply a prescribed rate each minute with the native patient ODE solver."""
    params, _ = patient_parameters(patient_name)
    patient = T1DPatient.withName(patient_name, seed=patient_seed, random_init_bg=False)

    def compiled_rhs(t, state, action, patient_params, last_q, last_food):
        return rhs(state, float(action.CHO), float(action.insulin), params, last_q, last_food)

    patient.model = compiled_rhs
    patient.reset()
    plasma = np.empty(len(meals) + 1)
    plasma[0] = patient.state[3] / params.Vg
    for minute, meal in enumerate(meals):
        rate = rates[minute // MINUTES_PER_STEP]
        patient.step(Action(CHO=float(meal), insulin=float(rate)))
        if not patient._odesolver.successful() or not np.isfinite(patient.state).all():
            raise RuntimeError(f"Native replay failed at minute {minute + 1}")
        plasma[minute + 1] = patient.state[3] / params.Vg
    return plasma


def measure(minute_plasma, warmup_minutes):
    endpoints = minute_plasma[MINUTES_PER_STEP::MINUTES_PER_STEP, None]
    return {k: v for k, v in glucose_metrics(endpoints, warmup_minutes, minute_plasma).items() if k in METRICS}


def evaluate_scenario(instance, design, patient_name, seed, variant, meals):
    patient_seed = instance["patient_seed"]
    warmup = instance["warmup_minutes"]
    trace, original = native_trace(
        patient_name, meals, individual_design(design, instance["tdi"][patient_name]), patient_seed
    )
    rates = trace[:, 2]
    replayed = replay(patient_name, meals, rates, patient_seed)
    identity_error = float(np.max(np.abs(replayed - original)))
    if identity_error > 1e-5:
        raise ValueError(f"Identity replay diverged by {identity_error:.6g} mg/dL")

    results = []
    for arm, schedule in {ARMS[0]: rates, **replay_rates(rates)}.items():
        plasma = original if arm == ARMS[0] else replay(patient_name, meals, schedule, patient_seed)
        if not np.allclose(plasma[:1441], original[:1441], rtol=0, atol=1e-5):
            raise ValueError("Warmup plasma diverged under an unchanged day-one schedule")
        dose = schedule.reshape(3, STEPS_PER_DAY).sum(axis=1) * MINUTES_PER_STEP
        if not np.allclose(dose, rates.reshape(3, STEPS_PER_DAY).sum(axis=1) * MINUTES_PER_STEP,
                           rtol=0, atol=1e-9):
            raise ValueError("A replay changed the amount delivered per day")
        results.append({
            "patient": patient_name, "seed": seed, "variant": variant, "arm": arm,
            "rate_u_min": schedule.tolist(), "daily_dose_u": dose.tolist(), **measure(plasma, warmup),
        })
    return results, identity_error

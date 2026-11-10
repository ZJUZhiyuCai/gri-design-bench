"""Glucose response in mg/dL and minutes; dose amplitude is in U/min."""
import numpy as np


def hill(glucose, ec50, n):
    g = np.maximum(np.asarray(glucose), 0.0)
    return 1.0 / (1.0 + np.exp(np.clip(n * (np.log(ec50) - np.log(np.maximum(g, 1e-300))), -700, 700)))


def steady_rate(glucose, amplitude, relative_leak, ec50, n):
    return amplitude * (relative_leak + hill(glucose, ec50, n))


def release_step(glucose, effective_glucose, remaining, dt, amplitude, relative_leak, ec50, n, tau):
    """Exact filter update, midpoint flux, and mass-conserving reservoir cap."""
    midpoint = glucose + (effective_glucose - glucose) * np.exp(-dt / (2 * tau))
    next_g = glucose + (effective_glucose - glucose) * np.exp(-dt / tau)
    dose = min(float(steady_rate(midpoint, amplitude, relative_leak, ec50, n)) * dt, remaining)
    return dose / dt, next_g, max(0.0, remaining - dose)

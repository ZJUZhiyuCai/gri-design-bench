"""Budgeted baseline and long-budget reference search on training scenarios."""
import time

import numpy as np
from scipy.optimize import differential_evolution
from scipy.stats import qmc

from gri_bench.api import PARAMETERS, Experiment


def training_seeds(instance):
    """Use the provided training panel, with a reproducible second seed if needed."""
    seeds = list(instance["training_seeds"])
    if len(seeds) == 1:
        seeds.append((seeds[0] + 1_000_000_007) % 2**32)
    return seeds


def zero_design(instance, mode="constant"):
    bounds = instance["bounds"]
    if mode == "constant":
        parameters = {"theta_c": 0.0, "theta_L": bounds["theta_L"][1]}
    else:
        parameters = {name: bounds[name][1] for name in PARAMETERS}
        parameters["theta_a"] = 0.0
    return {"mode": mode, "parameters": parameters}


def robust_loss(metrics):
    violation = (
        max(0.0, metrics["max_trajectory_tbr70"] - 3.0)
        + 4.0 * max(0.0, metrics["max_trajectory_tbr54"] - 0.5)
        + max(0.0, 45.0 - metrics["minimum_glucose"]) / 5.0
    )
    return (1000.0 + 100.0 * violation if violation else 0.0) - metrics["mean_tir"]


def search(instance, mode, seed, milestones, on_checkpoint, on_improvement=None, start=None):
    """Advance one search through CPU milestones using the best completed evaluation."""
    start = time.process_time() if start is None else start
    scenarios = Experiment(instance, seeds=training_seeds(instance))
    milestones = iter(milestones)
    deadline = next(milestones)
    best = None
    evaluations = 0
    rng = np.random.default_rng(seed)
    keys = PARAMETERS if mode == "responsive" else ("theta_c", "theta_L")
    bounds = [instance["constant_theta_c_bounds"] if k == "theta_c" else instance["bounds"][k] for k in keys]
    low, high = np.array(bounds).T
    log_low = np.log(np.maximum(low, 1e-7))
    log_span = np.log(high) - log_low

    def unpack(unit):
        values = np.clip(np.exp(log_low + np.asarray(unit) * log_span), low, high)
        return {"mode": mode, "parameters": dict(zip(keys, map(float, values)))}

    class Finished(Exception):
        pass

    def checkpoint():
        nonlocal deadline
        elapsed = time.process_time() - start
        while elapsed >= deadline:
            if best is None:
                raise RuntimeError("No candidate evaluated within the first CPU milestone")
            on_checkpoint({
                "cpu_budget_seconds": deadline,
                "cpu_seconds": elapsed,
                "completed_candidates": evaluations,
                **best,
            })
            deadline = next(milestones, None)
            if deadline is None:
                raise Finished

    def candidate(design):
        nonlocal best, evaluations
        checkpoint()
        try:
            metrics = scenarios.evaluate(design)
        except (ValueError, FloatingPointError):
            evaluations += 1
            return 1e9
        # A simulation crossing a milestone is excluded from that checkpoint.
        checkpoint()
        evaluations += 1
        loss = robust_loss(metrics)
        if best is None or loss < best["training_loss"]:
            best = {
                "design": design,
                "training_loss": loss,
                "training": {k: v for k, v in metrics.items() if k != "rows"},
            }
            if on_improvement:
                on_improvement(best)
        return loss

    try:
        candidate(zero_design(instance, mode))
        if mode == "constant":
            # Include both reservoir limits and the two-dimensional interior.
            for rate in np.geomspace(1e-7, high[0], 32):
                for load in (low[1], high[1]):
                    candidate({"mode": mode, "parameters": {"theta_c": float(rate), "theta_L": float(load)}})
        sampler = qmc.Sobol(len(keys), scramble=True, rng=rng)
        for unit in sampler.random_base2(5):
            candidate(unpack(unit))

        while True:
            init = qmc.Sobol(len(keys), scramble=True, rng=rng).random_base2(5)
            # Restart periodically with a fresh population and keep the incumbent.
            values = np.array([best["design"]["parameters"][key] for key in keys])
            init[0] = np.clip((np.log(np.maximum(values, 1e-7)) - log_low) / log_span, 0.0, 1.0)
            differential_evolution(
                lambda unit: candidate(unpack(unit)),
                [(0.0, 1.0)] * len(keys),
                init=init, rng=rng, maxiter=64, tol=0.0, atol=0.0, polish=False,
                mutation=(0.45, 1.0), recombination=0.85, workers=1,
            )
    except Finished:
        return best

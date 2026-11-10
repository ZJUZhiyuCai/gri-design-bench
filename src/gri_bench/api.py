"""Public training API. No sealed file paths, seeds, or outcomes are imported."""
import json
from pathlib import Path
import numpy as np
from .physiology import patient_parameters, meal_schedule, fast_trace

PARAMETERS = ('theta_a', 'relative_leak', 'ec50_mg_dl', 'hill_n', 'tau_min', 'theta_L')


def load_instance(path='/task/instance.json'):
    return json.loads(Path(path).read_text())


def validate_design(design, instance):
    if not isinstance(design, dict) or set(design) != {'mode', 'parameters'}:
        raise ValueError('Expected exactly mode and parameters')
    mode, values = design['mode'], design['parameters']
    keys = PARAMETERS if mode == 'responsive' else ('theta_c', 'theta_L') if mode == 'constant' else ()
    if not keys or not isinstance(values, dict) or set(values) != set(keys):
        raise ValueError('Invalid design mode or parameter keys')
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
            raise ValueError('Parameters must be finite real numbers')
        lo, hi = instance['constant_theta_c_bounds'] if key == 'theta_c' else instance['bounds'][key]
        if not lo <= value <= hi:
            raise ValueError(f'{key} outside [{lo}, {hi}]')
    return design


def individual_design(design, tdi):
    p = design['parameters']
    if design['mode'] == 'constant':
        return np.array([p['theta_c']*tdi, -1., 100., 2., 10., p['theta_L']*tdi])
    return np.array([p['theta_a']*tdi, p['relative_leak'], p['ec50_mg_dl'], p['hill_n'], p['tau_min'], p['theta_L']*tdi])


def glucose_metrics(trace, warmup=1440, minute_plasma=None):
    trace = np.asarray(trace)
    bg = trace[warmup//3:, 0]
    minimum = np.asarray(minute_plasma) if minute_plasma is not None else trace[:, 4]
    if not len(bg) or not np.isfinite(trace).all() or not np.isfinite(minimum).all():
        raise ValueError('Empty or nonfinite physiology')
    return {'tir': float(100*np.mean((bg >= 70) & (bg <= 180))),
            'tbr70': float(100*np.mean(bg < 70)), 'tbr54': float(100*np.mean(bg < 54)),
            'minimum': float(minimum.min()), 'mean_glucose': float(bg.mean())}


def summarize(rows):
    if not rows:
        raise ValueError('No trajectories')
    m = [r['metrics'] for r in rows]
    result = {'mean_tir': float(np.mean([x['tir'] for x in m])),
              'max_trajectory_tbr70': max(x['tbr70'] for x in m),
              'max_trajectory_tbr54': max(x['tbr54'] for x in m),
              'minimum_glucose': min(x['minimum'] for x in m), 'trajectories': len(m)}
    result['feasible'] = (result['max_trajectory_tbr70'] <= 4 and
                          result['max_trajectory_tbr54'] <= 1 and result['minimum_glucose'] >= 40)
    result['safe_tir'] = result['mean_tir'] if result['feasible'] else 0.
    return result


class Experiment:
    """Cached known cohort/scenarios; candidates share no physiological state."""
    def __init__(self, instance, seeds=None, variants=None):
        self.instance = instance
        seeds = instance['training_seeds'] if seeds is None else seeds
        variants = instance['variants'] if variants is None else variants
        schedules = {(s, v): meal_schedule(s, instance['days'], v) for s in seeds for v in variants}
        self.jobs = []
        for name in instance['patients']:
            p, initial = patient_parameters(name)
            for (seed, variant), base in schedules.items():
                self.jobs.append((name, seed, variant, p, initial, base*p.BW/instance['reference_weight_kg']))
        self.evaluations = 0

    def evaluate(self, design):
        validate_design(design, self.instance)
        self.evaluations += 1
        rows = []
        for name, seed, variant, p, initial, meals in self.jobs:
            trace = fast_trace(p, initial, meals, individual_design(design, self.instance['tdi'][name]))
            rows.append({'patient': name, 'seed': seed, 'variant': variant,
                         'metrics': glucose_metrics(trace, self.instance['warmup_minutes'])})
        return {**summarize(rows), 'rows': rows}


def save_design(design, path='/work/output/design.json'):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(design, indent=2, allow_nan=False)+'\n')
    temporary.replace(path)

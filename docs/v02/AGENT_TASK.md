# Design a glucose-responsive insulin formulation

Choose a single static formulation for the three virtual patients in `/task/instance.json`. Your score is the mean percentage of evaluated time with plasma glucose at 70–180 mg/dL. Every patient and meal trajectory must have time below 70 mg/dL at most 4%, time below 54 mg/dL at most 1%, and full-horizon minimum glucose at least 40 mg/dL. A safety failure scores zero. The simulation lasts three days. Time-in-range and time-below-range exclude the first day; the minimum includes it.

Use `submit_design` to send a design to the verifier. The tool checks the exact parameter names and instance bounds immediately. The latest accepted design before the cutoff is scored. Submit a legal candidate early and update it after you have tested improvements. You may leave search code and an explanation at `/work/output/search.py` and `/work/output/rationale.md` for the audit.

The `mode` field is `responsive` or `constant`. For `responsive`, `parameters` contains `theta_a` (release scale), `relative_leak`, `ec50_mg_dl`, `hill_n`, `tau_min`, and `theta_L` (reservoir). The responsive rate is amplitude × [relative leak + Hill(filtered interstitial glucose)], capped by the remaining reservoir. For `constant`, `parameters` contains `theta_c` (constant release scale) and `theta_L`. Amplitude and reservoir are scaled by each patient's native total daily insulin dose. The vector is shared across patients. The task allows a static vector with passive release and excludes separate patient coefficients, a live controller, and meal boluses.

Use the `shell` tool to run Python search programs. NumPy, SciPy, pandas and Numba are available in the isolated Linux workspace. For a design object you choose:

```python
from gri_bench.api import load_instance, Experiment
instance = load_instance()
experiment = Experiment(instance)
metrics = experiment.evaluate(design)
```

Reuse the experiment across candidates. It uses the training seeds and meal variants from the instance. Each scenario starts from the same physiological state. You can pass `seeds=[...]` to test additional training meals. The independent verifier uses new meal seeds and a separate native integrator. The public source is in `/opt/gri_bench`.

The sandbox allows one CPU, 2 GiB RAM, 30 CPU seconds after warmup and 90 seconds of cumulative tool time. The model has up to 12 calls, 6,000 completion tokens per call, 18,000 completion tokens total, and 360 seconds overall including API waits. Leave time to call `submit_design`. You can submit after shell compute stops while model time and tokens remain.

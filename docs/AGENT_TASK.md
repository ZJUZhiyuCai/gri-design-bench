# GRI static formulation design

Design a formulation for the known cohort in `/task/instance.json`. Maximize the mean percentage of post-warmup plasma glucose in [70,180] mg/dL on NEW meal scenarios. The final design receives zero if ANY patient/scenario has TBR70 > 4%, TBR54 > 1%, or ANY full-horizon minute has glucose < 40 mg/dL. Three days, first day omitted from TIR/TBR but included in minimum glucose. This is a simulation benchmark, not a clinical recommendation.

Submit `/work/output/design.json`, `/work/output/search.py` (your reproducible search code), and `/work/output/rationale.md` before budget expiry. Only design.json determines the simulated design; your code is retained for audit and never executed by the trusted verifier. Write an initial valid design early, checkpoint improvements atomically. Required files must be nonempty regular files.

Example output (check instance bounds):
```json
{"mode":"responsive","parameters":{"theta_a":0.0002,"relative_leak":1.5,"ec50_mg_dl":200.0,"hill_n":2.0,"tau_min":10.0,"theta_L":1.0}}
```
Alternatively `{"mode":"constant","parameters":{"theta_c":0.0002,"theta_L":1.0}}`. Every coefficient is shared across the cohort. Rate amplitude = theta_a × native TDI (U/min), load = theta_L × TDI (U); constant rate uses theta_c × TDI and the same finite reservoir. No individual fitted coefficients, custom online controller, external insulin or meal boluses. Shape bounds and synthetic material/load constraints are in the instance.

The public physiology is simglucose 0.2.11. Responsive rate is amplitude × [relative_leak + Hill(filtered interstitial glucose)], with exact first-order glucose filtering, midpoint flux every 3 minutes, and reservoir cap. Reference code: `/opt/gri_bench`. Meals are native RandomScenario, scaled by BW/86.0704; challenges are day-2 missed lunch and 50% larger dinner. All 30 simulator patient profiles are public. Patients in YOUR instance are known; evaluation uses fresh meal seeds.

Python API:
```python
from gri_bench.api import load_instance, Experiment, save_design
instance = load_instance()
experiment = Experiment(instance)  # cached 3 patients × 3 training variants
metrics = experiment.evaluate(design)  # fast RK4; final verifier uses native dopri5
print(metrics)  # mean_tir, safety metrics and per-trajectory rows
save_design(design)
```
`Experiment(instance, seeds=[...], variants=[...])` permits custom scenario validation within your compute budget. Every evaluation starts from the same native initial state; no carryover. Use `gri_bench.api.PARAMETERS` for responsive parameter ordering. NumPy, SciPy, pandas, Numba are installed. No network or package installation is available in the container.

Budget: 1 CPU, 2 GiB RAM, 30 CPU seconds for ALL container activity after warmup; up to 90 cumulative tool wall seconds; up to 360 seconds including model calls; at most 6 model calls, 6000 completion tokens per call and 18000 total. The container is paused during model requests. Tool output is truncated at 12000 characters. Imported libraries and scenario preparation after trial start count toward the CPU budget, so leave room for setup and saving. Simulator evaluation counts are diagnostic, not an enforceable cap. You may inspect source and implement your own search. Final metrics are independently recomputed; changing simulator code in your container cannot change the verifier.

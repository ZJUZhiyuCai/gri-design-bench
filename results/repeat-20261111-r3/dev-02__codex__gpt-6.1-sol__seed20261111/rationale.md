# Shared glucose-responsive formulation

The submitted formulation uses one common set of six coefficients for all three known adolescents. Amplitude and reservoir scale only with the supplied native TDI. No individual fitting, external insulin, or meal boluses are used.

Final parameters: `{"ec50_mg_dl": 140.3572742900074, "hill_n": 7.364078888958533, "relative_leak": 0.7331951945603498, "tau_min": 0.05, "theta_L": 4.0, "theta_a": 0.0003601111964280245}`.

The response combines basal leakage with glucose-dependent release. Fast sensing avoids adding filter lag to the existing interstitial and insulin-action delays. The Hill curve supplies additional insulin at high glucose while reducing release as glucose falls. The reservoir is set to the permitted maximum to avoid deliberately relying on early exhaustion.

## Search and validation

`search.py` performs deterministic differential evolution over amplitude, leakage, EC50 and Hill exponent, followed by local refinement on three public meal seeds. Sensing time and reservoir size are fixed at their permitted lower and upper limits, respectively. The objective penalizes any observed time below 70, all time below 54, and minimum glucose below 60. Candidates are screened on six further seeds, each with ordinary meals, missed lunch and larger dinner. The resulting design receives an additional 30-seed stress check (270 patient/scenario trajectories), with an explicit 3% amplitude reduction rule if hypoglycemia margins are thin. Atomic replacement writes the final design.

Before the stress check, the six-seed validation mean TIR was 72.4672%, maximum TBR70 0.0000%, maximum TBR54 0.0000%, and full-horizon minimum 69.9695 mg/dL. Those figures describe the candidate before any stress-driven adjustment.

For the **final submitted formulation**, the additional 30-seed check gave mean TIR **68.8260%**, maximum trajectory TBR70 **2.1875%**, maximum trajectory TBR54 **0.0000%**, and full-horizon minimum **68.8897 mg/dL**. Each seed covers all three patients and all three variants. TIR and TBR omit the first day; minimum glucose includes it.

These are public fast-RK4 simulation results, not native-dopri5 results or guarantees for unseen scenarios. No native integration was run within this compute budget. All observed outcomes are saved in `results.json` and `stress.json`; finite meal validation cannot establish universal safety. This is a simulation benchmark design, not a clinical recommendation.

Reproduce with `OPENBLAS_NUM_THREADS=1 python /work/output/search.py` in the benchmark environment. It uses only public physiology and meal schedules, with fixed random seeds. The final design file alone controls the independent evaluation.

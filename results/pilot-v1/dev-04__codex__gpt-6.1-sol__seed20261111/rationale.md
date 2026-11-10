# Shared static formulation

The submitted responsive formulation uses one coefficient set for all three known patients, with native TDI scaling and the maximum permitted reservoir (1.25 times TDI). All bounds are respected. No meal boluses or individualized coefficients are used.

A deterministic grid and seeded random search compared constant release and responsive shapes. Initial screening used the public RK4 physiology with one substep per minute. Candidates were penalized for TBR70 above 1%, any TBR54, and minimum glucose below 55 mg/dL, providing a margin relative to the rejection thresholds. Finalists were screened on three additional meal seeds; five were compared on eight further seeds, each with all three meal variants and all three patients. Final selected results were recomputed at the API default four RK4 substeps per minute.

Selected parameters:

```json
{
  "mode": "responsive",
  "parameters": {
    "theta_a": 0.00051,
    "relative_leak": 0.5124966150526034,
    "ec50_mg_dl": 59.264,
    "hill_n": 0.5881,
    "tau_min": 0.05,
    "theta_L": 1.25
  }
}
```

Training (9 trajectories): mean TIR 29.641%; maximum trajectory TBR70 0.000%; maximum TBR54 0.000%; full-horizon minimum 83.485 mg/dL.

Additional eight seeds (72 trajectories): mean TIR 27.015%; maximum trajectory TBR70 0.000%; maximum TBR54 0.000%; full-horizon minimum 83.507 mg/dL.

The finite reservoir limits performance: increasing release can improve early glucose while exhausting insulin earlier. Selection balances time in range against depletion and low-glucose margins. These public simulations do not establish safety on unseen scenarios, and the native dopri5 verifier may differ from RK4. The eight additional seeds were used for final selection, so their metrics are selection-validation estimates rather than an unbiased heldout guarantee.

Reproduction: run `PYTHONPATH=/opt OPENBLAS_NUM_THREADS=1 python /work/output/search.py`. All search stages and random seeds are included in that file. Supporting metrics are stored in final_metrics.json.

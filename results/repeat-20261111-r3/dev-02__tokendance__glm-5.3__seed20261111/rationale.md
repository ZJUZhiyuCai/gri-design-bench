# GRI static formulation — dev-02 (initial checkpoint)

Initial placeholder responsive design (example-shaped). `search.py` refines
theta_a / relative_leak / ec50 / hill_n / tau within instance bounds using the
cached gri_bench `Experiment` on training seed 6111002 across the three
variants (ordinary, missed_lunch, large_dinner), enforcing hard safety
(TBR70<=4%, TBR54<=1%, min glucose>=40 mg/dL incl. day-1 warmup) and
maximizing mean TIR on days 2-3. Checkpoints design.json atomically on each
improvement. Rationale updated as search proceeds.

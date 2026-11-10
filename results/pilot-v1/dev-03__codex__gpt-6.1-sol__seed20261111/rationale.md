# Final shared formulation

The submitted responsive formulation is shared across child#001, child#002 and child#003. It uses the minimum permitted relative leak, a near-immediate filter, a smooth Hill response, and the maximum allowed finite reservoir (four times native TDI). All bounds are respected. No patient-specific coefficients or external insulin are used.

Search: 430 random/local candidates on the training seed, validation of the leading 22 candidates on six additional seeds, then 60 nearby candidates screened jointly on those seven seeds. The local screen required minimum glucose >=65 mg/dL, TBR70 <=1%, and zero TBR54. Four leading candidates and the prior design were checked on twelve further seeds, requiring minimum >=60 mg/dL, TBR70 <=1.5%, and zero TBR54; selection maximized combined mean TIR. All three meal variants and all three patients were included. Fixed RNG seeds in search.py reproduce the process.

Seven search/validation seeds: 63 trajectories, mean TIR 82.252%, worst TBR70 0.000%, worst TBR54 0.000%, full-horizon minimum 70.062 mg/dL.

Twelve further seeds: 108 trajectories, mean TIR 81.445%, worst TBR70 0.000%, worst TBR54 0.000%, full-horizon minimum 70.002 mg/dL.

Final results use RK4 with 0.25-minute steps. Day one is omitted from TIR/TBR but included in the minimum. The final native dopri5 verifier was not run within the compute budget. Sampled scenario safety does not guarantee heldout safety. Details of final checks are in refinement.json. The three required submission files are design.json, search.py and rationale.md.

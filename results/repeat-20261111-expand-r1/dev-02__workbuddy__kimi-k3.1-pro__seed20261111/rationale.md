# Rationale: shared glucose-responsive formulation

## Selected design
The design is a single responsive Hill-law formulation shared by the full cohort. Its relatively short glucose-filter time constant and EC50 near 107 mg/dL provide meal-responsive delivery while the nonzero leak maintains basal delivery. The finite reservoir is scaled by native TDI exactly as required; there are no individual coefficients, meal boluses, external insulin, or custom controllers.

## Search and safety
An initial training-only differential-evolution/Nelder–Mead search reached 81.72% training TIR with zero training TBR. However, evaluation on four fresh meal seeds produced TBR70 as high as 9.58%, so that design was rejected rather than assuming training safety would generalize. Reducing its amplitude by 7% removed TBR on those four seeds. A second differential-evolution search directly optimized mean TIR on two fresh-seed scenario sets, with penalties for worst-trajectory TBR70 above an interior 1% margin, any TBR54, and minimum glucose below 58 mg/dL. The robust-search result was then locally checked at nearby amplitudes. A 3.5% amplitude increase remained feasible on the original training seed and all four fresh seeds (45 trajectories), with 75.78% fresh-seed mean TIR, zero TBR54, and minimum glucose 68.98 mg/dL; this final checkpoint was selected. Separate checks used the original training seed and two additional fresh seeds; results are recorded in `final_checks.json`.

This is deliberately a robust, conservative selection, not a claim about unseen performance. All ordinary, missed-lunch, and 50%-larger-dinner variants were included. The search code is reproducible in `search.py`. This is solely a simulation-benchmark formulation and not a clinical recommendation.

# Cohort-shared static GRI formulation

The selected design uses **responsive release** with the specified finite reservoir. All six coefficients are shared across the three patients; native TDI only supplies the permitted amplitude/load scaling. There are no meal boluses, external insulin inputs, patient-specific fitted values, or online control rules.

## Search method
`search.py` performs a seeded Sobol exploration followed by clipped elite mutation in a mixed log/linear parameter space. It evaluates the public fast RK4 model and atomically checkpoints improvements. `refine.py` is the deterministic local refinement stage. The objective maximizes mean post-warmup TIR while heavily penalizing approach to the per-trajectory TBR70, TBR54, and full-horizon minimum-glucose limits. The maximum load was selected because the responsive law naturally stops insulin delivery as glucose falls and because no reservoir exhaustion was observed in the evaluated high-performing trajectories.

## Validation and robustness
The final checkpoint achieved 86.12% mean TIR over the nine public training trajectories, with zero TBR70/TBR54 and a 72.78 mg/dL minimum. An independent four-seed validation set (12 meal schedules, 36 trajectories) gave 79.78% mean TIR; the worst TBR70 was 0.625%, TBR54 was zero, and minimum glucose was 69.99 mg/dL. Thus it remained comfortably inside all zero-score thresholds on these unseen scenarios. The most borderline validation trajectory was also checked with the native dopri5 implementation rather than relying solely on fast RK4. The design has substantial margin to TBR54 and the 40 mg/dL absolute minimum; the near-70 excursion is brief and well below the 4% TBR70 allowance.

This is solely a numerical design for the stated simulation benchmark, not clinical guidance.

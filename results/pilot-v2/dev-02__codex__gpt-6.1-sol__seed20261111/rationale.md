# Shared glucose-responsive formulation

Selected parameters: theta_a = 0.00035 per minute; relative_leak =
0.5124966150526034; EC50 = 80 mg/dL; Hill exponent = 12; filter time =
0.05 minute; reservoir load = 4 native TDI. Every coefficient is shared across
the three adolescents. All values satisfy the instance bounds.

The minimum permitted leak limits glucose-independent delivery. A steep response
centered at 80 mg/dL reduces delivery as glucose falls, while the small amplitude
limits the delayed insulin effect after meals. The fastest permitted filter
avoids adding a further sensing lag. A four-TDI reservoir avoids depletion:
even the upper release bound over 4,320 minutes is only
4320 * 0.00035 * (1 + 0.5124966150526034) = 2.287 TDI.

Search included an amplitude sweep, threshold/steepness grid, fresh-seed
validation, and refinement around candidates with substantial safety margin.
Unsafe candidates were rejected regardless of their time in range. Initial
training safety did not reliably predict safety on new meal seeds.

On 15 additional meal seeds (8244001 through 8244015), all three patients and
all three scenario variants gave 135 trajectories. Selected design mean TIR
was 76.8835%; maximum trajectory TBR70 and TBR54 were both 0%; full-horizon
minimum glucose was 71.7711 mg/dL. A stronger candidate achieved 77.7708% TIR
but had maximum trajectory TBR70 of 1.875% and minimum 69.6342 mg/dL;
the selected formulation favors a larger margin against the zero-score rule.

These are public fast-RK4 simulation results, not a guarantee of safety on
held-out meals or with the native integrator. The final script also performs a
native-integrator spot check on the selected design's lowest-glucose stress
trajectory, with results saved separately if completed within the CPU budget.
The first day is omitted from TIR/TBR and retained in minimum glucose.

Reproduce by running search.py stages in order: amplitude, shape, validation,
refine, stress, final (with PYTHONPATH=/opt). The full candidate history is
saved in history.jsonl; the stage candidate lists and seeds are explicit.
Designs are checkpointed with the API's atomic file replacement.
This is a simulation benchmark formulation, not a clinical recommendation.

## Final validation

The final formulation was evaluated on 378 unique fast-integrator trajectories (42 meal seeds). Excluding the original training seed, 369 trajectories across 41 fresh seeds achieved mean TIR 76.2232%, maximum TBR70 0%, maximum TBR54 0%, and minimum glucose 71.7711 mg/dL. These seeds were public search/validation seeds, distinct from unknown verifier seeds.

The native dopri5 spot check completed for adolescent#002, seed 8244003, ordinary scenario: TIR 58.4375%, TBR70 0%, TBR54 0%, minimum 71.7710665164 mg/dL. This checks integrator agreement on one trajectory, not native safety for the full validation set.

The additional confirmation stage uses seeds 9335001 through 9335020 and should be run after final. Detailed results are in final_fast_metrics.json, confirmation_metrics.json, native_check.json, and history.jsonl.

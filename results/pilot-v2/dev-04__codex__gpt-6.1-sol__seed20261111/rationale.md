# Shared formulation for dev-04

The submitted formulation is responsive, with theta_a=0.0006, relative_leak=0.5124966150526034, EC50=200 mg/dL, Hill exponent=0.5880395112623367, filter time constant=0.05 min, and reservoir load=1.25 times native TDI. All parameters are shared by adult#004, adult#005, and adult#006, and lie within the instance bounds. Release and load scale only by native TDI, as prescribed.

## Search and choice

The reproducible search.py screens a deterministic grid of amplitudes, glucose thresholds and Hill slopes using public physiology and RK4 with one substep per minute. It compares constant formulations, refines promising responsive regions, and screens on six additional meal seeds. A subsequent pooled search uses the training seed and three additional seeds, followed by four-substep-per-minute validation of five finalists on 12 seeds, each with ordinary, missed-lunch and large-dinner variants. Reservoir load is fixed at the upper bound to retain the available insulin inventory, leak at its lower bound to allow glucose dependence, and filtering at its lower bound to limit additional delay. These are search restrictions, not proofs of global optimality. Every trajectory starts from the native initial state. Designs are checkpointed by atomic replacement.

The selected formulation uses a gentle Hill response. The broad response provided better performance than the initially considered steep response under the limited three-day reservoir. A high release rate can exhaust the reservoir early, producing substantial later hyperglycemia. The final design balances insulin rate against this depletion; considerable hyperglycemia remains under this restricted load.

## Numerical evidence

On the 108 trajectories used for finalist comparison, mean post-warmup TIR was 27.9880%, maximum trajectory TBR70 and TBR54 were both zero, and the full-horizon minimum was 84.0633 mg/dL.

After fixing the design, an untouched reserve set of six meal seeds (200003, 220009, 240007, 260003, 280001, 300007), all three patients and all three variants yielded 54 trajectories. Mean TIR was 28.3025%, maximum trajectory TBR70 was 0.0000%, maximum trajectory TBR54 was 0.0000%, and full-horizon minimum glucose was 83.9583 mg/dL. Reserve feasibility: True. These reserve scenarios were not used to tune or select the formulation.

Metrics omit day one for TIR/TBR and retain the entire horizon for the minimum, including one-minute glucose minima. Finalist and reserve checks use the public default 0.25-minute RK4 integrator. Native dopri5 verification was not run within the compute budget. Numerical agreement and safety on the verifier's new meal scenarios are not guaranteed by these results. This is a simulation benchmark, not a clinical recommendation.

The complete evaluated designs and metrics are in history.jsonl; finalist metrics are in final_metrics.json and reserve metrics in reserve_metrics.json. Only design.json defines the submitted formulation.

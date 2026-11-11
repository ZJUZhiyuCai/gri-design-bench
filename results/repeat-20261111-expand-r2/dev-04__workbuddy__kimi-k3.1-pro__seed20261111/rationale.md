# Shared GRI formulation for dev-04

## Design and mechanism

The selected responsive law is `theta_a=0.00038840357100622955`, `relative_leak=0.8974970117785624`, `ec50_mg_dl=156.9124602254804`, `hill_n=1.4835170168738452`, `tau_min=13.920134776044947`, and `theta_L=1.25`. Amplitude and finite load scale only with each patient's native TDI. The large reservoir prevents early depletion; a moderate basal leak maintains effect during extreme hyperglycemia, while the weak/moderate Hill response and long glucose filter reduce meal-driven overdelivery. All values lie inside the instance bounds.

## Search and observed results

I explored broad log-amplitude, leak, threshold, Hill, filter, and load ranges, then used coordinate and log-normal local refinements. Alternative high-amplitude formulations with high EC50 were also tested. Candidate selection used a safety-penalized objective so that TIR could not compensate for hypoglycemia. Designs were checkpointed atomically with the supplied API.

For the nine cached training trajectories (three patients and ordinary, missed-lunch, and large-dinner variants), the final design has **mean TIR 30.4745%**, **maximum TBR70 0%**, **maximum TBR54 0%**, and **minimum full-horizon glucose 91.3341 mg/dL** under the public fast RK4 API. Independent fresh-seed fast-RK4 checks also remained feasible: seeds 42 and 137 jointly gave mean TIR 28.6632%, maximum TBR70/TBR54 0%, and minimum 91.7715 mg/dL; seed 6111008 gave 22.0255%, 0%, 0%, and 91.1620 mg/dL, respectively. Additional fresh seeds 6111005--6111007 were feasible with minima above 91.7 mg/dL.

The final choice favors the observed wide hypoglycemia margin over more aggressive candidates that sometimes improved post-meal control but approached or crossed the TBR/minimum-glucose limits. Training and validation success does not guarantee safety on every unseen meal draw; final outcomes must be independently recomputed with native dopri5. This is solely a simulation-benchmark formulation, not a clinical recommendation.

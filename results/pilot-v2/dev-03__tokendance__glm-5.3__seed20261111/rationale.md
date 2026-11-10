# GRI static formulation design (initial placeholder)

Cohort dev-03: child#001..003. Objective: maximize TIR on fresh meal scenarios with hard
safety gates (TBR70<=4%, TBR54<=1%, min glucose>=40). Initial submission = provided example
responsive parameters. Search strategy to be refined: grid/coordinate search over
(theta_a, relative_leak, ec50_mg_dl, hill_n, tau_min, theta_L) using a local re-implementation
of the public physiology for speed, verified against gri_bench.api Experiment.

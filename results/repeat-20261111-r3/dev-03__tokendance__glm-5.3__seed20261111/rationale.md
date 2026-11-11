# GRI static formulation design — dev-03

Final rationale (updated during search). Initial version below.

## Goal
Maximize mean TIR (plasma glucose in [70,180] mg/dL, post-warmup, 3-min samples)
over 3 child patients x 3 scenario variants with SHARED responsive coefficients.
Hard failure: any trajectory with TBR70>4%, TBR54>1%, or any full-horizon minute
plasma glucose <40 mg/dL (includes day-1 warmup).

## Approach
Grid + coordinate search over responsive parameters with `gri_bench` fast_trace
(RK4 proxy), validated across several meal seeds to avoid seed overfitting, with a
hypo-safety margin (target min glucose >= ~50 mg/dL and near-zero TBR) because the
final verifier uses the native dopri5 integrator and fresh meal seeds.

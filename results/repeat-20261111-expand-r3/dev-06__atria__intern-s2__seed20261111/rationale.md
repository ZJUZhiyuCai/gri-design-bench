# Rationale — dev-06 (child#004, child#005, child#006)

## Mode
`responsive`: a glucose-dependent basal-shaped release lets insulin delivery rise for
the large-dinner challenge and fall toward the missed-lunch challenge, which a fixed
`constant` rate cannot do.

## Parameter roles
- `theta_a` scales the amplitude by each patient's native TDI (U/min).
- `relative_leak` sets the glucose-independent floor of the release.
- `ec50_mg_dl` / `hill_n` set the sigmoidal turn-on of the Hill response versus
  filtered interstitial glucose.
- `tau_min` is the first-order filter lag; a moderate lag smooths controller noise
  without delaying meal response excessively.
- `theta_L` sets the finite reservoir (total U = theta_L * TDI) over the 3-day horizon.

## Safety strategy
The missed-lunch variant is the dominant hypoglycaemia risk. A low `relative_leak`
keeps the floor small, and the Hill term collapses as glucose falls, so delivery
approaches zero in the low range. `theta_L` is chosen large enough to cover the
enlarged dinner but not so large that the reservoir forces excess insulin during a
missed meal.

## Search
Coarse grid over the six parameters followed by coordinate ascent on the penalized
training objective (mean TIR with penalties for TBR70 > 4%, TBR54 > 1% and
minimum glucose < 40 mg/dL), then a robustness check on held-out meal seeds.

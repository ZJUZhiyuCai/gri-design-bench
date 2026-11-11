# Static GRI formulation — dev-05

## Design

The submitted formulation is **responsive**, with one coefficient set shared by all three patients. It uses the minimum permitted relative leak, a finite reservoir at the maximum permitted TDI-scaled load, and an effectively unlagged interstitial-glucose filter (`tau_min = 0.05`). The Hill curve supplies additional release with rising glucose rather than relying on a high glucose-independent rate.

## Search and safety logic

I searched amplitude, EC50, Hill exponent, and filter time with the public RK4 training simulator. The objective was mean post-warmup TIR minus large penalties for maximum trajectory TBR70, TBR54, and low full-horizon glucose. Initial coarse grids showed that excessive basal delivery produced severe hypoglycemia, while overly weak delivery left adolescents #004 and #005 hyperglycemic. Subsequent local searches therefore concentrated near `theta_a = 0.00032`, `EC50 = 180–210`, and `hill_n = 1.4–1.5`.

Meal scenarios with independent seeds were used for model selection and safety screening, including all ordinary, missed-lunch, and 50%-larger-dinner variants. The selected final candidate retained zero TBR54 and zero TBR70 across 54 evaluated training/validation trajectories (six independent seeds), with mean TIR 88.50% and minimum glucose 70.52 mg/dL in the six-seed run; the more aggressive neighboring settings sometimes exceeded the TBR70 limit. `theta_L = 4` avoids premature reservoir exhaustion, and the fast glucose filter was marginally better and more consistent than slower filters.

This is a simulation-benchmark design, not a clinical recommendation. Fresh-seed performance is not guaranteed by training safety, so the final parameters deliberately avoid the highest-dose, highest-TIR candidates that crossed safety constraints.

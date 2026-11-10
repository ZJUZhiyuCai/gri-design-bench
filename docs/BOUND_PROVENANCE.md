# What the design bounds mean

The shape box is an **optimistic prescreen design envelope**, expanded from a prior conditional fit. It is not a measured manufacturing-feasibility region or a joint confidence region. The frozen instance field's shorthand “prior fitted shape envelope” refers to that expanded design envelope; this clarification changes no numerical input or score.

The historical calibration used the time-resolved i-crystal-1 release data in [Xu et al., 2025, Figure 2i](https://www.nature.com/articles/s41565-025-01860-0/figures/2). The original material was polymer-membrane-coated insulin crystals. This benchmark is a glucose-only surrogate; it does not reproduce the paper's full dual glucose/β-hydroxybutyrate response. Transferring its response shape to a passive interstitial-glucose release surrogate is a modeling assumption. Absolute in-vivo dose amplitude and reservoir load were not obtained by directly converting the assay's mg/mL release amplitude into U/min.

| Parameter | Historical conditional profile support, approximate | Frozen benchmark design envelope, approximate |
|---|---:|---:|
| Relative basal leakage / responsive amplitude | 1.02–2.76 | 0.5125–5.5189 |
| EC50, mg/dL | 119–408 | 59.263–816.114 |
| Hill exponent | 1.18–12 | 0.588–24 |
| Response time, minutes | 0.1–10 | 0.05–20 |

The prior protocol combined conditional profile and replicate-bootstrap intervals and applied a preregistered twofold range expansion, limited by its declared search domain. The Hill upper end and the fast-response end of tau were unresolved by that fit. Ten-minute assay sampling does not establish sub-minute response kinetics. Cross-parameter identifiability and real material realizability are not established.

Historical provenance: prescreen-v1 configuration SHA-256 `5361bf0f1aa54ce17ccf96d4e511cbd9fa268cec4a0bf694877cfad2955c172e`; calibration fit SHA-256 `3b5575c212836c51d36970f6e64c5b855121ad0627f46e3106e4dad0e1b5a6fd`. These are prior local research artifacts, not claims of independent public preregistration. The original STOP/CONTINUE studies were not edited for this benchmark.

The benchmark's dose and load coefficients, and case-specific subranges, are synthetic optimization constraints. They test design under a declared simulator contract. A high score does not establish that the selected material can be synthesized or that it will behave similarly in an animal or human.

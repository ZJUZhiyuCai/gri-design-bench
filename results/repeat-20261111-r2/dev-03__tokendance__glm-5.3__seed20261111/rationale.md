# GRI dev-03 initial rationale (placeholder, to be updated)
Responsive shared-coefficient rate: amplitude*theta_a*TDI*(leak + Hill(filtered interstitial G)).
Reservoir theta_L=4*TDI to avoid depletion. Search: penalty-weighted TIR with hypo margins over
3x3 training trajectories + extra seeds. Safety first: zero if TBR70>4, TBR54>1, min<40.

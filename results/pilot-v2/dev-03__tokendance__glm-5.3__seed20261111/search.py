# Placeholder search code; will be replaced with reproducible optimization script.
import json
design = {"mode":"responsive","parameters":{"theta_a":0.0002,"relative_leak":1.5,"ec50_mg_dl":200.0,"hill_n":2.0,"tau_min":10.0,"theta_L":1.0}}
json.dump(design, open('/work/output/design.json','w'))

import json,sys
sys.path.insert(0,'/opt')
from gri_bench.api import load_instance, Experiment
inst=load_instance(); ex=Experiment(inst)
d=json.load(open('/work/output/design.json'))
m=ex.evaluate(d)
print({k:v for k,v in m.items() if k!='rows'})
for r in m['rows']: print(r['patient'],r['variant'],{k:round(v,2) for k,v in r['metrics'].items()})

# Placeholder search script (to be improved)
from gri_bench.api import load_instance, Experiment, save_design
import json

def main():
    instance = load_instance()
    exp = Experiment(instance)
    design = json.load(open("/work/output/design.json"))
    metrics = exp.evaluate(design)
    print(metrics)
    save_design(design)

if __name__ == "__main__":
    main()

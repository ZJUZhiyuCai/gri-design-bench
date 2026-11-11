# Placeholder search script (to be improved)
from gri_bench.api import load_instance, Experiment, save_design
import json

def main():
    instance = load_instance()
    exp = Experiment(instance)
    design = json.load(open("/work/output/design.json"))
    m = exp.evaluate(design)
    print(m)
    save_design(design)

if __name__ == "__main__":
    main()

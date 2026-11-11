"""Run, grade or check the six-model expansion without editing frozen runners."""
import argparse
from gri_bench.expansion import grade_matrix, run_matrix, verify_expansion_freeze


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['check', 'run', 'grade'])
    action = parser.parse_args().action
    if action == 'run':
        run_matrix()
    elif action == 'grade':
        grade_matrix()
    else:
        plan = verify_expansion_freeze()
        print('Frozen expansion verified:', len(plan['jobs']), 'planned trials')

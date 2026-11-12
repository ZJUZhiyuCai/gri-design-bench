"""Run a fair-compute search in the same image and emit complete checkpoints."""
import argparse
import json

from baseline_search import search
from gri_bench.api import load_instance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("constant", "responsive"), required=True)
    args = parser.parse_args()

    def emit(kind, record):
        print(json.dumps({"kind": kind, **record}, allow_nan=False), flush=True)

    # Leave headroom for cgroup polling and checkpoint transfer. Imports and
    # setup count toward this interpreter's timed search.
    search(load_instance(), args.mode, 20261113, (29.0,), lambda r: emit("complete", r),
           lambda r: emit("candidate", r), start=0.0)


if __name__ == "__main__":
    main()

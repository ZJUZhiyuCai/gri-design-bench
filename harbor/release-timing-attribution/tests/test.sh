#!/bin/sh
set -eu
mkdir -p /logs/verifier
status=0
python -I -m pytest -p no:cacheprovider --ctrf /logs/verifier/ctrf.json /tests/test_results.py -rA || status=$?
case "$status" in
    0) echo 1 > /logs/verifier/reward.txt ;;
    1) echo 0 > /logs/verifier/reward.txt ;;
    *) exit "$status" ;;
esac

#!/bin/sh
set -eu
cp /solution/solve.py /app/output/reproduce.py
python -I /app/output/reproduce.py

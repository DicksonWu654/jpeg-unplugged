#!/bin/bash
# Periodic second-pass (retry) sweeps while the main run is going. Usage: nohup scripts/census/retry_loop.sh &
cd "$(dirname "$0")/../.."
while true; do
  .venv/bin/python -I scripts/census/census.py retry --min-age 1500 --concurrency 150 >> data/census/retry_loop.out 2>&1
  sleep 600
done

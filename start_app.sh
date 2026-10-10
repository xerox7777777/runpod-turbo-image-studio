#!/usr/bin/env bash
set -euo pipefail

# Keep the RunPod base image's SSH and web-terminal startup available.
/start.sh &
sleep 2
exec python -u /app/app.py

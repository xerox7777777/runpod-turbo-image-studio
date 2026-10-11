#!/usr/bin/env bash
set -euo pipefail
exec python -u /app/startup.py "$@"

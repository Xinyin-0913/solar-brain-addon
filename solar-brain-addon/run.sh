#!/usr/bin/env sh
set -e

echo "[solar-brain] Starting Solar Brain add-on..."
cd /usr/src/solar-brain
exec uvicorn app.main:app --host 0.0.0.0 --port 8099 --log-level info

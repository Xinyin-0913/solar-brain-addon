"""Seed a demo database with a plausible day of telemetry (for UI checks)."""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import database
from app.models import TelemetrySnapshot

database.init_db()
now = datetime.now(timezone.utc)

# 8 hours of snapshots every 60 s: morning ramp-up to a midday peak.
for i in range(8 * 60):
    t = now - timedelta(minutes=8 * 60 - i)
    progress = i / (8 * 60)
    solar = max(0.0, 4300 * (1 - abs(progress - 0.75) * 2))  # peak near the end
    load = 1500 + 400 * ((i % 30) / 30)
    export = max(0.0, solar - load)
    database.insert_snapshot(TelemetrySnapshot(
        timestamp=t.isoformat(timespec="seconds"),
        solar_power_w=round(solar, 1),
        home_load_w=round(load, 1),
        grid_export_w=round(export, 1),
        battery_soc=70.0,
    ))

print(f"Seeded {database.snapshot_count()} snapshots into {database.DB_PATH}")

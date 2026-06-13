"""Seed device_samples with a plausible few hours for /devices UI checks."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import database

database.init_db()
now = datetime.now(timezone.utc)

# Per-device fixed power profile over the last 4 hours, 60 s cadence.
profile = {
    "light.kitchen": 9.0,
    "light.living_room": 9.0,
    "switch.tv_plug": 1.0,
    "sensor.fridge_power": 95.0,        # measured power sensor (W)
    "binary_sensor.hall_motion": 0.1,
}
rows = []
for i in range(4 * 60):
    ts = (now - timedelta(minutes=4 * 60 - i)).isoformat(timespec="seconds")
    for eid, power in profile.items():
        rows.append((ts, eid, power, None))
database.insert_device_samples(rows)
print(f"Seeded {len(rows)} device samples for {len(profile)} devices")

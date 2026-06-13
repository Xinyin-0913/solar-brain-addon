"""SQLite persistence: entity mappings and telemetry history.

Uses /data (persists across add-on restarts/updates) when running under the
Supervisor, a local ./data directory otherwise. Plain sqlite3 with a
connection per operation - more than enough at this scale, no ORM needed.
"""

import logging
import os
import sqlite3
from pathlib import Path

from .models import TelemetrySnapshot

logger = logging.getLogger("solar_brain.db")

SITE_ID = "default"  # single-site for now; column exists for the future


def _data_dir() -> Path:
    override = os.getenv("SOLAR_BRAIN_DATA_DIR")
    if override:
        return Path(override)
    if Path("/data").exists():
        return Path("/data")
    return Path(__file__).resolve().parent.parent / "data"


DB_PATH = _data_dir() / "solar_brain.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entity_mappings (
    site_id    TEXT NOT NULL,
    role       TEXT NOT NULL,
    entity_id  TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (site_id, role)
);
CREATE TABLE IF NOT EXISTS telemetry_snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id       TEXT NOT NULL,
    ts            TEXT NOT NULL,
    solar_power_w REAL,
    battery_soc   REAL,
    grid_import_w REAL,
    grid_export_w REAL,
    home_load_w   REAL,
    ev_power_w    REAL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_site_ts
    ON telemetry_snapshots (site_id, ts);
CREATE TABLE IF NOT EXISTS device_samples (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id    TEXT NOT NULL,
    ts         TEXT NOT NULL,
    entity_id  TEXT NOT NULL,
    power_w    REAL,
    energy_kwh REAL
);
CREATE INDEX IF NOT EXISTS idx_device_samples_site_entity_ts
    ON device_samples (site_id, entity_id, ts);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.info("Database ready at %s", DB_PATH)


def get_mappings() -> dict[str, str]:
    """Return current role -> entity_id mapping."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT role, entity_id FROM entity_mappings WHERE site_id = ?",
            (SITE_ID,),
        ).fetchall()
    return {row["role"]: row["entity_id"] for row in rows}


def save_mappings(changes: dict[str, str | None], updated_at: str) -> dict[str, str]:
    """Upsert mappings; a None value removes the role. Returns the full mapping."""
    with _connect() as conn:
        for role, entity_id in changes.items():
            if entity_id:
                conn.execute(
                    "INSERT INTO entity_mappings (site_id, role, entity_id, updated_at) "
                    "VALUES (?, ?, ?, ?) "
                    "ON CONFLICT (site_id, role) DO UPDATE "
                    "SET entity_id = excluded.entity_id, updated_at = excluded.updated_at",
                    (SITE_ID, role, entity_id, updated_at),
                )
            else:
                conn.execute(
                    "DELETE FROM entity_mappings WHERE site_id = ? AND role = ?",
                    (SITE_ID, role),
                )
    logger.info("Saved entity mappings: %s", changes)
    return get_mappings()


def insert_snapshot(snapshot: TelemetrySnapshot) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO telemetry_snapshots "
            "(site_id, ts, solar_power_w, battery_soc, grid_import_w, "
            " grid_export_w, home_load_w, ev_power_w) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                SITE_ID,
                snapshot.timestamp,
                snapshot.solar_power_w,
                snapshot.battery_soc,
                snapshot.grid_import_w,
                snapshot.grid_export_w,
                snapshot.home_load_w,
                snapshot.ev_power_w,
            ),
        )


def get_snapshots_since(start_ts: str | None) -> list[dict]:
    """Snapshots with ts >= start_ts (all when None), oldest first.

    Timestamps are stored as UTC ISO strings with identical formatting, so
    lexicographic comparison is chronologically correct.
    """
    query = (
        "SELECT ts, solar_power_w, home_load_w, grid_export_w "
        "FROM telemetry_snapshots WHERE site_id = ?"
    )
    params: list = [SITE_ID]
    if start_ts is not None:
        query += " AND ts >= ?"
        params.append(start_ts)
    query += " ORDER BY ts ASC"
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_first_snapshot_ts() -> str | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT MIN(ts) AS first_ts FROM telemetry_snapshots WHERE site_id = ?",
            (SITE_ID,),
        ).fetchone()
    return row["first_ts"]


def insert_device_samples(rows: list[tuple[str, str, float | None, float | None]]) -> None:
    """Batch-insert device samples: (ts, entity_id, power_w, energy_kwh)."""
    if not rows:
        return
    with _connect() as conn:
        conn.executemany(
            "INSERT INTO device_samples (site_id, ts, entity_id, power_w, energy_kwh) "
            "VALUES (?, ?, ?, ?, ?)",
            [(SITE_ID, ts, eid, p, e) for (ts, eid, p, e) in rows],
        )


def get_device_samples_since(start_ts: str | None) -> list[dict]:
    """Device samples with ts >= start_ts (all when None), by entity then time."""
    query = (
        "SELECT ts, entity_id, power_w, energy_kwh FROM device_samples "
        "WHERE site_id = ?"
    )
    params: list = [SITE_ID]
    if start_ts is not None:
        query += " AND ts >= ?"
        params.append(start_ts)
    query += " ORDER BY entity_id ASC, ts ASC"
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_first_device_sample_ts() -> str | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT MIN(ts) AS first_ts FROM device_samples WHERE site_id = ?",
            (SITE_ID,),
        ).fetchone()
    return row["first_ts"]


def prune_device_samples(before_ts: str) -> int:
    """Delete device samples older than before_ts. Returns rows removed."""
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM device_samples WHERE site_id = ? AND ts < ?",
            (SITE_ID, before_ts),
        )
        return cur.rowcount


def snapshot_count() -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM telemetry_snapshots WHERE site_id = ?",
            (SITE_ID,),
        ).fetchone()
    return int(row["n"])

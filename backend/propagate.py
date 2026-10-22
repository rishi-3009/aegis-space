"""SGP4 propagation of every catalogue object over a 24 hour window."""

import os
import time
from datetime import datetime, timezone

import numpy as np
from sgp4.api import Satrec, SatrecArray, jday

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PRIMARY_TLE = os.path.join(ROOT, "data", "tle_primaries.txt")
DEBRIS_TLE = os.path.join(ROOT, "data", "tle_debris.txt")


def load_tles(path):
    """Parse a 3-line TLE file (name, line 1, line 2) into a list of dicts."""
    with open(path, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]

    objects = []
    for i in range(0, len(lines) - 2, 3):
        name, line1, line2 = lines[i], lines[i + 1], lines[i + 2]
        objects.append({
            "id": line1[2:7].strip(),
            "name": name,
            "line1": line1,
            "line2": line2,
        })
    return objects


def build_catalog():
    """Load primaries and debris. Primaries are identified by the NORAD ids in tle_primaries.txt."""
    primaries = load_tles(PRIMARY_TLE)
    primary_ids = {p["id"] for p in primaries}

    seen = set()
    catalog = []
    for obj in primaries + load_tles(DEBRIS_TLE):
        if obj["id"] in seen:
            continue
        seen.add(obj["id"])
        obj["is_primary"] = obj["id"] in primary_ids
        catalog.append(obj)
    return catalog


def default_start():
    """UTC time rounded down to the minute, or START_TIME from the environment."""
    env = os.environ.get("START_TIME")
    if env:
        return datetime.fromisoformat(env.replace("Z", "+00:00"))
    return datetime.now(timezone.utc).replace(second=0, microsecond=0)


def propagate_all(start=None, steps=1440, step_seconds=60):
    """Return (objects, pos, vel) for every object that SGP4 can propagate.

    pos has shape (N, steps, 3) in km, vel has shape (N, steps, 3) in km/s.
    Objects with a non-zero SGP4 error code at any step (decayed or bad TLE) are dropped.
    """
    t0 = time.perf_counter()
    start = start or default_start()

    catalog = build_catalog()
    sats = [Satrec.twoline2rv(o["line1"], o["line2"]) for o in catalog]

    jd0, fr0 = jday(start.year, start.month, start.day, start.hour, start.minute, start.second)
    offsets = np.arange(steps) * step_seconds / 86400.0
    jd = np.full(steps, jd0)
    fr = fr0 + offsets

    err, pos, vel = SatrecArray(sats).sgp4(jd, fr)

    ok = np.all(err == 0, axis=1)
    kept = [o for o, keep in zip(catalog, ok) if keep]

    pos = pos[ok].astype(np.float32)
    vel = vel[ok].astype(np.float32)

    print(f"propagate_all: {len(kept)}/{len(catalog)} objects kept, "
          f"shape {pos.shape}, {time.perf_counter() - t0:.2f}s")
    return kept, pos, vel


if __name__ == "__main__":
    objects, pos, vel = propagate_all()
    for i, obj in enumerate(objects):
        if obj["is_primary"]:
            alt = np.linalg.norm(pos[i], axis=1) - 6378.137
            print(f"{obj['name']:<20} altitude {alt.min():7.1f} to {alt.max():7.1f} km")

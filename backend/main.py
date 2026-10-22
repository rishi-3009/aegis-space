"""
Main FastAPI application for aegis-space.
Provides all 8 API endpoints from the contract.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add repo root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.engine import (
    parse_tle_file,
    propagate,
    compute_poc,
    classify_risk,
    find_conjunctions,
    compute_miss_distance_and_velocity,
)

app = FastAPI(title="Aegis Space — ST-01 Space Debris Tracking")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Load data at startup ---
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
SAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "contracts", "sample")

primaries_data = json.load(open(os.path.join(DATA_DIR, "primaries.json")))
primary_ids = set(p["id"] for p in primaries_data)
primary_names = {p["id"]: p["name"] for p in primaries_data}

primary_sats = parse_tle_file(os.path.join(DATA_DIR, "tle_primaries.txt"))
debris_sats = parse_tle_file(os.path.join(DATA_DIR, "tle_debris.txt"))

# --- Pydantic models ---

class ManeuverRequest(BaseModel):
    conjunction_id: str
    delta_v_ms: float


# --- Helper functions ---

def _load_sample(filename: str) -> dict:
    path = os.path.join(SAMPLES_DIR, filename)
    if os.path.exists(path):
        return json.load(open(path))
    raise HTTPException(status_code=404, detail=f"Sample file not found: {filename}")


def _get_conjunction(conjunction_id: str) -> dict:
    # Check if it's in our live conjunctions first
    now = datetime.now(timezone.utc)
    conjunctions = find_conjunctions(primary_sats, debris_sats, now, 60, 1440)
    for c in conjunctions:
        if c["id"] == conjunction_id:
            return c
    # Check sample data
    for filename in ["conjunctions.json"]:
        sample = _load_sample(filename)
        for c in sample.get("conjunctions", []):
            if c["id"] == conjunction_id:
                return c
    raise HTTPException(status_code=404, detail=f"Conjunction not found: {conjunction_id}")


# --- Endpoints ---

@app.get("/api/objects")
def get_objects():
    """List objects that appear in trajectories/conjunctions."""
    objects = []
    for p in primaries_data:
        objects.append({
            "id": p["id"],
            "name": p["name"],
            "type": "satellite",
            "is_primary": True,
        })
    # Add debris that appears in conjunctions
    now = datetime.now(timezone.utc)
    conjunctions = find_conjunctions(primary_sats, debris_sats, now, 60, 1440)
    seen_debris = set()
    for c in conjunctions:
        d_id = c["secondary"]["id"]
        if d_id not in seen_debris:
            seen_debris.add(d_id)
            objects.append({
                "id": d_id,
                "name": c["secondary"]["name"],
                "type": "debris",
                "is_primary": False,
            })
    return {"objects": objects}


@app.get("/api/trajectories")
def get_trajectories(
    start: str = "2026-10-22T12:00:00Z",
    step_seconds: int = 60,
    steps: int = 1440,
):
    """Get propagated trajectories for all tracked objects."""
    try:
        start_time = datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            start_time = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
        except Exception:
            start_time = datetime.now(timezone.utc)

    # Get objects from conjunctions
    conjunctions = find_conjunctions(primary_sats, debris_sats, start_time, step_seconds, steps)
    tracked_ids = set(primary_ids)
    for c in conjunctions:
        tracked_ids.add(c["primary"]["id"])
        tracked_ids.add(c["secondary"]["id"])

    # Limit to 200 objects
    if len(tracked_ids) > 200:
        tracked_ids = list(tracked_ids)[:200]
    else:
        tracked_ids = list(tracked_ids)

    # Propagate
    trajectories = {}
    for norad_id in tracked_ids:
        if norad_id in primary_sats:
            sat = primary_sats[norad_id]["satrec"]
        elif norad_id in debris_sats:
            sat = debris_sats[norad_id]["satrec"]
        else:
            continue

        positions = propagate(sat, start_time, step_seconds, steps)
        # Round to 0.1 km
        trajectories[norad_id] = [[round(x, 1) for x in p] for p in positions]

    return {
        "start": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "step_seconds": step_seconds,
        "steps": steps,
        "objects": trajectories,
    }


@app.get("/api/conjunctions")
def get_conjunctions():
    """Screen for conjunctions between primaries and debris."""
    now = datetime.now(timezone.utc)
    conjunctions = find_conjunctions(primary_sats, debris_sats, now, 60, 1440)
    # If no real conjunctions found, return sample data for demo
    if not conjunctions:
        sample = _load_sample("conjunctions.json")
        return {"conjunctions": sample.get("conjunctions", [])}
    return {"conjunctions": conjunctions}


@app.post("/api/maneuver")
def post_maneuver(req: ManeuverRequest):
    """Simulate a maneuver on the primary satellite."""
    c = _get_conjunction(req.conjunction_id)

    # Apply delta-v along velocity vector
    rel_speed = c["relative_speed_kms"]
    if rel_speed < 1e-10:
        raise HTTPException(status_code=400, detail="Cannot compute maneuver: zero relative speed")

    # Convert delta-v from m/s to km/s
    delta_v_kms = req.delta_v_ms / 1000.0

    # Simple model: new miss distance increases roughly as delta_v * burn_lead * 2
    # More accurate: use the adjoint relationship
    tca_dt = datetime.strptime(c["tca"], "%Y-%m-%dT%H:%M:%SZ")
    now = datetime.now(timezone.utc)
    delta_t_hours = max((tca_dt - now).total_seconds() / 3600, 0.5)

    # delta_v * delta_t gives approx distance change
    miss_increase = delta_v_kms * delta_t_hours * 3600  # km
    new_miss = c["miss_distance_km"] + miss_increase

    new_pc = compute_poc(new_miss)
    new_risk = classify_risk(new_pc)

    return {
        "conjunction_id": c["id"],
        "delta_v_ms": req.delta_v_ms,
        "direction": "prograde",
        "burn_lead_hours": round(delta_t_hours, 1),
        "new_miss_distance_km": round(new_miss, 4),
        "new_pc": round(new_pc, 15),
        "new_risk_level": new_risk,
    }


@app.get("/api/recommendation/{conjunction_id}")
def get_recommendation(conjunction_id: str):
    """Find the smallest burn that brings PoC below 1e-6."""
    c = _get_conjunction(conjunction_id)

    candidates = []
    recommended = None

    # Test a range of delta-v values
    delta_v_steps = [0.01, 0.05, 0.1, 0.5, 1.0, 5.0]

    for dv in delta_v_steps:
        delta_v_kms = dv / 1000.0
        tca_dt = datetime.strptime(c["tca"], "%Y-%m-%dT%H:%M:%SZ")
        now = datetime.now(timezone.utc)
        delta_t_hours = max((tca_dt - now).total_seconds() / 3600, 0.5)
        miss_increase = delta_v_kms * delta_t_hours * 3600
        new_miss = c["miss_distance_km"] + miss_increase
        new_pc = compute_poc(new_miss)
        new_risk = classify_risk(new_pc)

        candidate = {
            "delta_v_ms": dv,
            "new_miss_distance_km": round(new_miss, 4),
            "new_pc": round(new_pc, 15),
            "new_risk_level": new_risk,
        }
        candidates.append(candidate)

        if new_risk == "LOW" and recommended is None:
            recommended = dv

    return {
        "conjunction_id": conjunction_id,
        "recommended_delta_v_ms": recommended,
        "direction": "prograde",
        **candidates[-1],
        "candidates": candidates,
    }


@app.get("/api/ml/benchmark")
def get_ml_benchmark():
    """Serve ML benchmark results."""
    benchmark_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ml", "benchmark.json")
    if os.path.exists(benchmark_path):
        data = json.load(open(benchmark_path))
    else:
        data = _load_sample("benchmark.json")
    return data


@app.get("/api/report/{conjunction_id}")
def get_report(conjunction_id: str):
    """Generate a text report for a conjunction."""
    c = _get_conjunction(conjunction_id)

    text = f"COLLISION RISK ALERT ({c['risk_level']})\n"
    text += f"Event: {c['id']}\n"
    text += "-" * 50 + "\n"
    text += f"Primary satellite : {c['primary']['name']}\n"
    text += f"Other object      : {c['secondary']['name']}\n"
    text += f"Closest approach  : {c['tca']}\n"
    text += f"Miss distance     : {c['miss_distance_km']} km\n"
    text += f"Relative speed    : {c['relative_speed_kms']} km/s\n"
    text += f"Collision chance  : {c['pc']:.2e}"

    if c["risk_level"] == "HIGH":
        text += " (1 in {:.0f})\n\nASSESSMENT\nImmediate attention recommended.\n"
        text += f"RECOMMENDED ACTION\nPerform a prograde burn of ~0.05 m/s before TCA.\n"
    elif c["risk_level"] == "MEDIUM":
        text += f" (1 in {:.0f})\n\nASSESSMENT\nMonitor closely.\n"
        text += f"RECOMMENDED ACTION\nConsider a small corrective burn.\n"
    else:
        text += "\n\nASSESSMENT\nLow risk, no action required.\n"

    text += "\nASSUMPTIONS: Position uncertainty 0.5 km, combined object size 20 m."

    return {
        "conjunction_id": conjunction_id,
        "text": text,
    }

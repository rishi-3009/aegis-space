"""FastAPI app serving every endpoint in contracts/api_contract.md.

Run from the repo root:  uvicorn backend.main:app --reload --port 8000
"""

import json
import os
import sys
import time

import numpy as np
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.conjunction import build_conjunctions  # noqa: E402
from backend.maneuver import evaluate_burn, recommend_burn  # noqa: E402
from backend.propagate import default_start, propagate_all  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES_DIR = os.path.join(ROOT, "contracts", "sample")
BENCHMARK_PATH = os.path.join(ROOT, "ml", "benchmark.json")
MAX_TRACKED = 200

from tools.report import generate_report  # noqa: E402

STATE = {}


class ManeuverRequest(BaseModel):
    conjunction_id: str
    delta_v_ms: float


def _public(conj):
    """Drop the '_' internal fields before a conjunction leaves the server."""
    return {k: v for k, v in conj.items() if not k.startswith("_")}


def _find(conjunction_id):
    _ensure_state()
    conj = STATE["conjunctions_by_id"].get(conjunction_id)
    if conj is None:
        raise HTTPException(status_code=404, detail=f"Conjunction not found: {conjunction_id}")
    return conj


def _tracked_indices(objects, conjunctions):
    """Primaries, every conjunction object, then filler debris up to MAX_TRACKED in catalogue order."""
    primaries = [i for i, o in enumerate(objects) if o["is_primary"]]
    tracked = list(primaries)
    for c in conjunctions:
        for idx in (c["_primary_index"], c["_secondary_index"]):
            if idx not in tracked:
                tracked.append(idx)
    if len(tracked) > MAX_TRACKED:
        print(f"warning: {len(tracked)} objects needed for conjunctions, above the {MAX_TRACKED} limit")
    for i in range(len(objects)):
        if len(tracked) >= MAX_TRACKED:
            break
        if i not in tracked:
            tracked.append(i)
    return tracked


def _ensure_state():
    """Compute everything once, on first use. Serverless hosts (Vercel) do not run startup hooks."""
    if STATE:
        return
    t0 = time.perf_counter()
    start = default_start()
    objects, pos, vel = propagate_all(start)
    objects, pos, vel, conjunctions = build_conjunctions(objects, pos, vel, start)

    tracked = _tracked_indices(objects, conjunctions)
    # float64 before rounding, otherwise float32 digits bloat the JSON
    trajectories = {
        objects[i]["id"]: np.round(pos[i].astype(np.float64), 1).tolist() for i in tracked
    }
    # Encode once; encoding ~200 x 1440 points per request is too slow for the 1 s limit
    trajectories_json = json.dumps({
        "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "step_seconds": 60,
        "steps": pos.shape[1],
        "objects": trajectories,
    }, separators=(",", ":")).encode("utf-8")

    STATE["start"] = start
    STATE["objects"] = objects
    STATE["conjunctions"] = conjunctions
    STATE["conjunctions_by_id"] = {c["id"]: c for c in conjunctions}
    STATE["tracked"] = tracked
    STATE["trajectories_json"] = trajectories_json
    print(f"state: {len(objects)} objects, {len(conjunctions)} conjunctions, "
          f"{len(tracked)} tracked, {time.perf_counter() - t0:.1f}s")


app = FastAPI(title="Aegis Space: ST-01 Space Debris Tracking")
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/objects")
def get_objects():
    _ensure_state()
    objects = STATE["objects"]
    return {"objects": [
        {
            "id": objects[i]["id"],
            "name": objects[i]["name"],
            "type": "satellite" if objects[i]["is_primary"] else "debris",
            "is_primary": objects[i]["is_primary"],
        }
        for i in STATE["tracked"]
    ]}


@app.get("/api/trajectories")
def get_trajectories():
    _ensure_state()
    return Response(content=STATE["trajectories_json"], media_type="application/json")


@app.get("/api/conjunctions")
def get_conjunctions():
    _ensure_state()
    return {"conjunctions": [_public(c) for c in STATE["conjunctions"]]}


@app.post("/api/maneuver")
def post_maneuver(req: ManeuverRequest):
    conj = _find(req.conjunction_id)
    return evaluate_burn(conj, req.delta_v_ms)


@app.get("/api/recommendation/{conjunction_id}")
def get_recommendation(conjunction_id: str):
    return recommend_burn(_find(conjunction_id))


@app.get("/api/ml/benchmark")
def get_ml_benchmark():
    path = BENCHMARK_PATH if os.path.exists(BENCHMARK_PATH) else os.path.join(SAMPLES_DIR, "benchmark.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/report/{conjunction_id}")
def get_report(conjunction_id: str):
    conj = _find(conjunction_id)
    return {
        "conjunction_id": conjunction_id,
        "text": generate_report(_public(conj), recommend_burn(conj)),
    }

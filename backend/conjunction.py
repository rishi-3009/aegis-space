"""Conjunction screening: coarse search on the 60 s grid, 1 s refinement, PoC and a labelled demo event."""

from datetime import datetime, timedelta, timezone

import numpy as np
from scipy.integrate import solve_ivp
from sgp4.api import Satrec, SatrecArray, jday

MU_KM3_S2 = 398600.4418
COARSE_CUT_KM = 500.0      # coarse stage keeps local minima closer than this
SCREEN_KM = 20.0           # refined pairs farther apart than this are dropped
REFINE_WINDOW_S = 90       # +/- seconds around each coarse minimum
DUPLICATE_WINDOW_S = 300   # same pair with TCAs this close counts as one event
SIGMA_KM = 0.5             # assumed combined position uncertainty
RADIUS_KM = 0.02           # assumed combined hard-body radius (20 m)
DEMO_TIME_STEP = 600       # demo event TCA at 10 h (600 x 60 s)
DEMO_OFFSET_KM = 0.8


def probability_of_collision(miss_km, sigma_km=SIGMA_KM, radius_km=RADIUS_KM):
    """Simple 2D Gaussian PoC approximation from the API contract."""
    denom = 2 * sigma_km ** 2
    return (radius_km ** 2 / denom) * np.exp(-(miss_km ** 2) / denom)


def risk_level(pc):
    if pc >= 1e-4:
        return "HIGH"
    if pc >= 1e-6:
        return "MEDIUM"
    return "LOW"


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _coarse_candidates(pos, primary_idx):
    """Local minima of primary-to-object distance on the 60 s grid, below COARSE_CUT_KM."""
    candidates = []
    for p in primary_idx:
        dist = np.linalg.norm(pos - pos[p], axis=2)          # (N, T)
        mid = dist[:, 1:-1]
        is_min = (mid < dist[:, :-2]) & (mid <= dist[:, 2:]) & (mid < COARSE_CUT_KM)
        is_min[primary_idx] = False                           # never pair primaries together
        objs, steps = np.nonzero(is_min)
        candidates += [(p, int(j), int(t) + 1) for j, t in zip(objs, steps)]
    return candidates


def _refine(cand, objects, sats, start, step_seconds):
    """Re-propagate one pair at 1 s resolution around the coarse minimum. Returns None if no usable TCA."""
    p, j, t = cand
    centre = t * step_seconds
    offsets = np.arange(-REFINE_WINDOW_S, REFINE_WINDOW_S + 1)     # seconds from window start
    window_start = start + timedelta(seconds=centre - REFINE_WINDOW_S)
    jd0, fr0 = jday(window_start.year, window_start.month, window_start.day,
                    window_start.hour, window_start.minute, window_start.second)
    jd = np.full(len(offsets), jd0)
    fr = fr0 + offsets / 86400.0

    pair = SatrecArray([sats[p], sats[j]])
    err, r, v = pair.sgp4(jd, fr)
    if np.any(err != 0):
        return None

    dist = np.linalg.norm(r[0] - r[1], axis=1)
    k = int(np.argmin(dist))
    tca_s = centre - REFINE_WINDOW_S + k
    if tca_s < 0 or tca_s > (r.shape[1] - 1) * step_seconds:
        return None  # TCA falls outside the 24 h window

    miss = float(dist[k])
    if miss >= SCREEN_KM:
        return None

    return {
        "primary_index": p,
        "secondary_index": j,
        "tca_seconds": int(tca_s),
        "tca": start + timedelta(seconds=int(tca_s)),
        "miss_km": miss,
        "relative_speed_kms": float(np.linalg.norm(v[0, k] - v[1, k])),
        "rel_pos_km": (r[0, k] - r[1, k]).astype(float),           # primary minus secondary
        "primary_pos_km": r[0, k].astype(float),
        "primary_vel_kms": v[0, k].astype(float),
    }


def screen(objects, pos, vel, start, step_seconds, primary_idx):
    """Coarse then refine screening. Returns internal conjunction records (no ids yet)."""
    sats = {}
    for idx in primary_idx:
        sats[idx] = Satrec.twoline2rv(objects[idx]["line1"], objects[idx]["line2"])

    records = []
    seen_pairs = {}
    for cand in _coarse_candidates(pos, primary_idx):
        p, j, _ = cand
        for idx in (p, j):
            if idx not in sats:
                sats[idx] = Satrec.twoline2rv(objects[idx]["line1"], objects[idx]["line2"])
        rec = _refine(cand, objects, sats, start, step_seconds)
        if rec is None:
            continue
        pair = (p, j)
        if any(abs(rec["tca_seconds"] - s) < DUPLICATE_WINDOW_S for s in seen_pairs.get(pair, [])):
            continue
        seen_pairs.setdefault(pair, []).append(rec["tca_seconds"])
        records.append(rec)
    return records


def add_demo_event(objects, pos, vel, start, step_seconds, primary_idx):
    """Inject one clearly labelled synthetic debris object that passes DEMO_OFFSET_KM from a primary.

    Built from the primary's own state at DEMO_TIME_STEP. Its orbit is two-body only (no SGP4),
    so TCA, miss distance and relative position come straight from the construction.
    Returns (objects, pos, vel, record) with the demo object appended.
    """
    p = primary_idx[0]
    steps = pos.shape[1]
    r0 = pos[p, DEMO_TIME_STEP].astype(float)
    v0 = vel[p, DEMO_TIME_STEP].astype(float)

    # Offset the position radially and turn the velocity 90 degrees out of the orbit plane.
    r_hat = r0 / np.linalg.norm(r0)
    v_mag = np.linalg.norm(v0)
    cross_hat = np.cross(r_hat, v0 / v_mag)
    cross_hat /= np.linalg.norm(cross_hat)
    demo_r = r0 + DEMO_OFFSET_KM * r_hat
    demo_v = v_mag * cross_hat

    def gravity(_t, y):
        r = y[:3]
        return np.concatenate([y[3:], -MU_KM3_S2 * r / np.linalg.norm(r) ** 3])

    t_grid = np.arange(steps) * step_seconds                       # seconds from start
    t_tca = DEMO_TIME_STEP * step_seconds
    y0 = np.concatenate([demo_r, demo_v])
    opts = dict(method="DOP853", rtol=1e-10, atol=1e-9, dense_output=False)

    fwd = solve_ivp(gravity, (t_tca, t_grid[-1]), y0, t_eval=t_grid[t_grid >= t_tca], **opts)
    bwd = solve_ivp(gravity, (t_tca, t_grid[0]), y0, t_eval=t_grid[t_grid <= t_tca][::-1], **opts)

    demo_traj = np.zeros((steps, 6))
    demo_traj[t_grid >= t_tca] = fwd.y.T
    demo_traj[t_grid <= t_tca] = bwd.y.T[::-1]

    demo_obj = {
        "id": "DEMO-001",
        "name": "DEMO DEBRIS (SYNTHETIC)",
        "type": "debris",
        "is_primary": False,
        "synthetic": True,
    }
    objects = objects + [demo_obj]
    pos = np.concatenate([pos, demo_traj[None, :, :3].astype(np.float32)], axis=0)
    vel = np.concatenate([vel, demo_traj[None, :, 3:].astype(np.float32)], axis=0)

    record = {
        "primary_index": p,
        "secondary_index": len(objects) - 1,
        "tca_seconds": t_tca,
        "tca": start + timedelta(seconds=t_tca),
        "miss_km": DEMO_OFFSET_KM,
        "relative_speed_kms": float(np.linalg.norm(demo_v - v0)),
        "rel_pos_km": r0 - demo_r,
        "primary_pos_km": r0,
        "primary_vel_kms": v0,
        "synthetic": True,
    }
    return objects, pos, vel, record


def build_conjunctions(objects, pos, vel, start, step_seconds=60):
    """Full pipeline: screen, add the demo event, then assign ids and sort by PoC.

    Returns (objects, pos, vel, conjunctions). Each conjunction is in contract format,
    plus '_'-prefixed internal fields the maneuver code needs.
    """
    primary_idx = [i for i, o in enumerate(objects) if o["is_primary"]]
    records = screen(objects, pos, vel, start, step_seconds, primary_idx)
    objects, pos, vel, demo = add_demo_event(objects, pos, vel, start, step_seconds, primary_idx)
    records.append(demo)

    for rec in records:
        rec["pc"] = float(probability_of_collision(rec["miss_km"]))
    records.sort(key=lambda r: r["pc"], reverse=True)

    conjunctions = []
    for n, rec in enumerate(records, start=1):
        p, j = objects[rec["primary_index"]], objects[rec["secondary_index"]]
        conjunctions.append({
            "id": f"c{n:03d}",
            "primary": {"id": p["id"], "name": p["name"]},
            "secondary": {"id": j["id"], "name": j["name"]},
            "tca": _iso(rec["tca"]),
            "tca_step": int(round(rec["tca_seconds"] / step_seconds)),
            "miss_distance_km": round(rec["miss_km"], 4),
            "relative_speed_kms": round(rec["relative_speed_kms"], 4),
            "pc": float(f"{rec['pc']:.3e}"),
            "risk_level": risk_level(rec["pc"]),
            "synthetic": bool(rec.get("synthetic", False)),
            "_primary_index": rec["primary_index"],
            "_secondary_index": rec["secondary_index"],
            "_rel_pos_km": rec["rel_pos_km"],
            "_primary_pos_km": rec["primary_pos_km"],
            "_primary_vel_kms": rec["primary_vel_kms"],
        })
    return objects, pos, vel, conjunctions

"""Collision avoidance burn evaluation.

Simplified model: the burn is an along-track impulse on the primary, applied `lead_hours`
before TCA, and the displacement at TCA comes from Clohessy-Wiltshire (Hill) equations.
Assumes a near-circular orbit and that TCA itself does not move. Good for small burns only.
"""

import numpy as np

from backend.conjunction import MU_KM3_S2, probability_of_collision, risk_level

SAFE_PC = 1e-6
BURN_STEPS_MS = [0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0]


def _cw_displacement(dv_kms, n, tau):
    """Radial (x), along-track (y) displacement at TCA for an along-track impulse dv."""
    x = (2 * dv_kms / n) * (1 - np.cos(n * tau))
    y = (dv_kms / n) * (4 * np.sin(n * tau) - 3 * n * tau)
    return x, y


def _mean_motion(r, v):
    """Mean motion n = sqrt(mu / a^3), with a from the vis-viva equation."""
    inv_a = 2 / np.linalg.norm(r) - np.dot(v, v) / MU_KM3_S2
    a = 1 / inv_a
    return np.sqrt(MU_KM3_S2 / a ** 3)


def evaluate_burn(conj, dv_ms, lead_hours=6.0):
    """Miss distance and PoC after a burn of dv_ms (m/s), trying both prograde and retrograde."""
    r = conj["_primary_pos_km"]
    v = conj["_primary_vel_kms"]
    rel = conj["_rel_pos_km"]

    n = _mean_motion(r, v)
    tau = lead_hours * 3600.0
    x, y = _cw_displacement(dv_ms / 1000.0, n, tau)

    radial = r / np.linalg.norm(r)
    along = v / np.linalg.norm(v)
    shift = x * radial + y * along                 # cross-track is zero for an in-plane burn

    miss_plus = float(np.linalg.norm(rel + shift))
    miss_minus = float(np.linalg.norm(rel - shift))
    if miss_plus >= miss_minus:
        direction, new_miss = "prograde", miss_plus
    else:
        direction, new_miss = "retrograde", miss_minus

    new_pc = float(probability_of_collision(new_miss))
    return {
        "conjunction_id": conj["id"],
        "delta_v_ms": dv_ms,
        "direction": direction,
        "burn_lead_hours": lead_hours,
        "new_miss_distance_km": round(new_miss, 4),
        "new_pc": float(f"{new_pc:.3e}"),
        "new_risk_level": risk_level(new_pc),
    }


def recommend_burn(conj, lead_hours=6.0):
    """Smallest tested burn that brings PoC below SAFE_PC. Falls back to the largest burn if none works."""
    candidates = []
    for dv in BURN_STEPS_MS:
        result = evaluate_burn(conj, dv, lead_hours)
        candidates.append({
            "delta_v_ms": dv,
            "new_miss_distance_km": result["new_miss_distance_km"],
            "new_pc": result["new_pc"],
            "new_risk_level": result["new_risk_level"],
        })

    safe = next((c for c in candidates if c["new_pc"] < SAFE_PC), None)
    chosen = safe or candidates[-1]
    best = evaluate_burn(conj, chosen["delta_v_ms"], lead_hours)
    return {
        "conjunction_id": conj["id"],
        "recommended_delta_v_ms": safe["delta_v_ms"] if safe else None,
        "direction": best["direction"],
        "new_miss_distance_km": best["new_miss_distance_km"],
        "new_pc": best["new_pc"],
        "new_risk_level": best["new_risk_level"],
        "candidates": candidates,
    }

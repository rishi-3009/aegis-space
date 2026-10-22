"""
Maneuver scanner for aegis-space.
Tests multiple delta-v values to find optimal collision avoidance burn.

Contains two approaches:
- scan_maneuver: computes the physics directly from raw numbers (from main).
- recommend_burn: uses an evaluator callback to test candidate burns
  (from person4/data-tools).
"""

import math


# ---------------------------------------------------------------------------
# From main: self-contained maneuver scan
# ---------------------------------------------------------------------------
def scan_maneuver(miss_distance_km: float, relative_speed_kms: float, burn_lead_hours: float,
                  min_pc: float = 1e-6) -> dict:
    """Test delta-v values and return the smallest effective maneuver.

    Returns dict with recommended_delta_v_ms and candidates.
    """
    candidates = []
    recommended = None

    delta_v_steps = [0.01, 0.05, 0.1, 0.5, 1.0, 5.0]

    for dv in delta_v_steps:
        delta_v_kms = dv / 1000.0
        miss_increase = delta_v_kms * burn_lead_hours * 3600
        new_miss = miss_distance_km + miss_increase

        # Compute PoC
        sigma = 0.5
        R = 0.02
        if new_miss < 1e-10:
            new_pc = 1.0
        else:
            denom = 2 * sigma ** 2
            new_pc = (R ** 2) / denom * math.exp(-(new_miss ** 2) / denom)

        if new_pc >= 1e-4:
            new_risk = "HIGH"
        elif new_pc >= 1e-6:
            new_risk = "MEDIUM"
        else:
            new_risk = "LOW"

        candidates.append({
            "delta_v_ms": dv,
            "new_miss_distance_km": round(new_miss, 4),
            "new_pc": round(new_pc, 15),
            "new_risk_level": new_risk,
        })

        if new_risk == "LOW" and recommended is None:
            recommended = dv

    return {
        "recommended_delta_v_ms": recommended,
        "candidates": candidates,
    }


# ---------------------------------------------------------------------------
# From person4/data-tools: evaluator-based burn recommendation
# ---------------------------------------------------------------------------

# Find the smallest tested burn that reduces collision probability below the threshold.
def recommend_burn(
    evaluate_fn,
    conjunction: dict,
    pc_threshold: float = 1e-6,
    candidates: list | None = None,
) -> dict:
    """Test all candidates and return the smallest safe burn, if one exists."""

    if candidates is None:
        candidates = [0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0]

    tested_candidates = []
    safe_candidates = []

    for delta_v_ms in candidates:
        # Pass both the conjunction ID and the candidate burn to the evaluator.
        result = evaluate_fn(conjunction["id"], delta_v_ms)

        # Store exactly the required details for each tested candidate.
        candidate_result = {
            "delta_v_ms": delta_v_ms,
            "new_miss_distance_km": result["new_miss_distance_km"],
            "new_pc": result["new_pc"],
            "new_risk_level": result["new_risk_level"],
        }
        tested_candidates.append(candidate_result)

        # Keep the full recommendation details when a candidate is safe.
        if result["new_pc"] < pc_threshold:
            safe_candidates.append({
                "delta_v_ms": delta_v_ms,
                "direction": result["direction"],
                "new_miss_distance_km": result["new_miss_distance_km"],
                "new_pc": result["new_pc"],
                "new_risk_level": result["new_risk_level"],
            })

    # Select the smallest safe burn, or return None values if none works.
    if safe_candidates:
        best = min(safe_candidates, key=lambda item: item["delta_v_ms"])
    else:
        best = {
            "delta_v_ms": None,
            "direction": None,
            "new_miss_distance_km": None,
            "new_pc": None,
            "new_risk_level": None,
        }

    return {
        "conjunction_id": conjunction["id"],
        "recommended_delta_v_ms": best["delta_v_ms"],
        "direction": best["direction"],
        "new_miss_distance_km": best["new_miss_distance_km"],
        "new_pc": best["new_pc"],
        "new_risk_level": best["new_risk_level"],
        "candidates": tested_candidates,
    }


# Simulate the result of evaluating a candidate burn.
def fake_evaluate_fn(_conjunction_id, delta_v_ms):
    miss = 1.0 + 80 * delta_v_ms
    pc = 8e-4 * math.exp(-(miss ** 2) / 0.5)

    if pc >= 1e-4:
        risk_level = "HIGH"
    elif pc >= 1e-6:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "new_miss_distance_km": miss,
        "new_pc": pc,
        "new_risk_level": risk_level,
        "direction": "prograde",
    }


# Simulate a case where no candidate reduces probability below the threshold.
def no_burn_evaluate_fn(_conjunction_id, delta_v_ms):
    miss = 0.5
    pc = 8e-4 * math.exp(-(miss ** 2) / 0.5)

    if pc >= 1e-4:
        risk_level = "HIGH"
    elif pc >= 1e-6:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "new_miss_distance_km": miss,
        "new_pc": pc,
        "new_risk_level": risk_level,
        "direction": "prograde",
    }


# Print the results for a successful burn and a case with no safe burn.
if __name__ == "__main__":
    example_conjunction = {"id": "c001"}

    result = recommend_burn(fake_evaluate_fn, example_conjunction)
    print("Successful-burn test:")
    print(result)

    no_safe_result = recommend_burn(
        no_burn_evaluate_fn,
        example_conjunction,
    )
    print("\nNo-safe-burn test:")
    print(no_safe_result)

    print("\nBoth test scenarios executed.")
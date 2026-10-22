"""
Maneuver scanner for aegis-space.
Tests multiple delta-v values to find optimal collision avoidance burn.
"""


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
            new_pc = (R ** 2) / denom * __import__('math').exp(-(new_miss ** 2) / denom)
        
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

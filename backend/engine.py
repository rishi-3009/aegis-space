"""
SGP4 propagation engine.
Parses TLE files, propagates orbits, computes miss distances and PoC.
"""

import numpy as np
from sgp4.api import Satrec, twoline2rv
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import List, Tuple, Optional


@dataclass
class OrbitState:
    """ECI position/velocity at a given time."""
    time: datetime
    position: List[float]  # [x, y, z] in km
    velocity: List[float]  # [vx, vy, vz] in km/s


def parse_tle_file(filepath: str) -> dict:
    """Parse a TLE file into {norad_id: Satrec}.
    File format: 3 lines per object (name, line1, line2).
    """
    satellites = {}
    with open(filepath) as f:
        lines = [l.strip() for l in f if l.strip()]

    i = 0
    while i < len(lines) - 2:
        name = lines[i]
        line1 = lines[i + 1]
        line2 = lines[i + 2]
        sat = Satrec.twoline2rv(line1, line2)
        norad_id = line1[2:7].strip()
        satellites[norad_id] = {
            "name": name,
            "satrec": sat,
            "line1": line1,
            "line2": line2,
        }
        i += 3

    return satellites


def propagate(satrec: Satrec, start_time: datetime, step_seconds: int, steps: int) -> List[List[float]]:
    """Propagate orbit, return list of ECI positions [x, y, z] in km."""
    positions = []
    dt = timedelta(seconds=step_seconds)
    for _ in range(steps):
        e, position, velocity = satrec.sgp4(start_time)
        if e == 0:
            positions.append([position.x, position.y, position.z])
        else:
            # Failed to propagate; pad with last position or NaN
            if positions:
                positions.append(positions[-1])
            else:
                positions.append([0.0, 0.0, 0.0])
        start_time += dt
    return positions


def compute_miss_distance_and_velocity(
    pos1: np.ndarray, vel1: np.ndarray,
    pos2: np.ndarray, vel2: np.ndarray
) -> Tuple[float, float]:
    """Compute miss distance and relative speed between two satellites at the same time."""
    rel_pos = pos1 - pos2
    rel_vel = vel1 - vel2

    miss_distance_km = np.linalg.norm(rel_pos)
    relative_speed_kms = np.linalg.norm(rel_vel)

    return miss_distance_km, relative_speed_kms


def compute_poc(miss_distance_km: float, sigma_km: float = 0.5, R_km: float = 0.02) -> float:
    """Compute probability of collision using Gaussian uncertainty model.
    
    sigma: combined position uncertainty (km)
    R: combined hard-body radius (km)
    """
    if miss_distance_km < 1e-10:
        return 1.0

    denom = 2 * sigma_km ** 2
    exponent = -(miss_distance_km ** 2) / denom
    coeff = (R_km ** 2) / denom

    return coeff * np.exp(exponent)


def classify_risk(pc: float) -> str:
    if pc >= 1e-4:
        return "HIGH"
    elif pc >= 1e-6:
        return "MEDIUM"
    return "LOW"


def find_conjunctions(
    primary_sats: dict,
    debris_sats: dict,
    start_time: datetime,
    step_seconds: int,
    steps: int,
    screen_radius_km: float = 20.0,
    min_pc: float = 1e-10
) -> List[dict]:
    """Screen primary satellites against debris for conjunctions.
    
    Returns list of conjunction dicts sorted by PoC (highest first).
    """
    conjunctions = []
    primary_ids = list(primary_sats.keys())
    debris_ids = list(debris_sats.keys())

    # Propagate all objects
    all_positions = {}
    for norad_id in primary_ids + debris_ids:
        sat = primary_sats.get(norad_id) or debris_sats.get(norad_id)
        positions = propagate(sat["satrec"], start_time, step_seconds, steps)
        all_positions[norad_id] = np.array(positions)

    # Screen: primary vs every debris object
    for p_id in primary_ids:
        for d_id in debris_ids:
            p_pos = all_positions[p_id]
            d_pos = all_positions[d_id]

            # Compute distance at each time step
            distances = np.linalg.norm(p_pos - d_pos, axis=1)

            # Find minimum distance
            min_idx = np.argmin(distances)
            min_dist = distances[min_idx]

            if min_dist > screen_radius_km:
                continue

            # Compute relative velocity at TCA
            # Need velocity for this; approximate from propagated states
            # Use sgp4 output for velocity
            p_sat = primary_sats[p_id]["satrec"]
            d_sat = debris_sats[d_id]["satrec"]
            dt = timedelta(seconds=step_seconds)
            
            _, _, p_vel_arr = p_sat.sgp4(start_time + dt * min_idx)
            _, _, d_vel_arr = d_sat.sgp4(start_time + dt * min_idx)
            
            p_vel = np.array([p_vel_arr.vx, p_vel_arr.vy, p_vel_arr.vz])
            d_vel = np.array([d_vel_arr.vx, d_vel_arr.vy, d_vel_arr.vz])

            miss_dist, rel_speed = compute_miss_distance_and_velocity(
                p_pos[min_idx], p_vel,
                d_pos[min_idx], d_vel
            )

            pc = compute_poc(miss_dist)
            risk = classify_risk(pc)

            if pc < min_pc:
                continue

            tca = start_time + timedelta(seconds=step_seconds * min_idx)

            conjunctions.append({
                "id": f"c_{p_id}_{d_id}",
                "primary": {"id": p_id, "name": primary_sats[p_id]["name"]},
                "secondary": {"id": d_id, "name": debris_sats[d_id]["name"]},
                "tca": tca.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "tca_step": int(min_idx),
                "miss_distance_km": round(float(miss_dist), 4),
                "relative_speed_kms": round(float(rel_speed), 4),
                "pc": round(float(pc), 10),
                "risk_level": risk,
                "synthetic": False,
            })

    # Sort by PoC, highest first
    conjunctions.sort(key=lambda c: c["pc"], reverse=True)
    return conjunctions


def get_era_epoch(start_time: datetime):
    """Compute Julian century from J2000 epoch (2000-01-01 12:00:00 UTC)."""
    j2000 = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    delta = start_time - j2000
    return delta.total_seconds() / 86400.0 / 36525.0

"""
build_dataset.py — Parse TLEs, build training/test dataset for Aegis PINN.

Parses data/tle_debris.txt, runs SGP4 + reference propagation, and saves
ml/data/dataset.npz with 15-input features and 6-output targets.
"""

import os
import sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from sgp4.api import Satrec
from reference_sim import reference_propagate, propagate_two_body, RE, MU

# Constants for parsing
DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'tle_debris.txt')
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'dataset.npz')

MAX_OBJECTS = 150
N_TIMES = 97  # 0 to 48h in 1800s steps
HOURS = np.array([1, 6, 12, 24, 48])
TIME_POINTS_H = np.arange(0, 49, 1.5)  # 0 to 48h in 1.5h steps = 65 points
# Actually the spec says 0, 1800, ..., 172800 which is every 1800s = 0.5h
# 0 to 48h in 1800s steps: 172800/1800 + 1 = 97 points
TIME_POINTS_H_ARRAY = np.arange(0, 49, 0.5)
TIME_POINTS_S = TIME_POINTS_H_ARRAY * 3600


def parse_tles(path):
    """Parse TLE file. Returns list of (name, line1, line2)."""
    with open(path, 'r') as f:
        lines = f.readlines()

    tles = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith('1 ') and i + 1 < len(lines):
            l1 = lines[i].strip()
            l2 = lines[i + 1].strip()
            if l2.startswith('2 '):
                # Name is the previous line
                name = lines[i - 1].strip() if i > 0 else "unknown"
                tles.append((name, l1, l2))
        i += 1

    return tles


def check_orbit_validity(sat):
    """Check if an orbit is valid for our purposes.
    
    Returns (valid, reason) tuple.
    """
    # Get perigee altitude from orbital elements
    # sat.eccn = eccentricity, sat.incn = inclination (rad), sat.argper = arg perigee
    # sat.nodeo = RAAN
    # sat.seco = semi-major axis in km
    if sat.seco <= 0:
        return False, "Invalid semi-major axis"
    
    a = sat.seco
    e = sat.eccn
    perigee_alt = a * (1 - e) - RE
    
    if perigee_alt < 300:
        return False, f"perigee too low: {perigee_alt:.0f} km"
    
    return True, ""


def get_sgp4_array(sat, t_hours):
    """Get SGP4 state at multiple times.
    
    Returns (pos, vel) in km, km/s.
    """
    jds = np.full(len(t_hours), sat.jdsatepoch)
    jdf = sat.jdsatepochF + np.array(t_hours)
    
    errors, r, v = sat.sgp4_array(jds, jdf)
    
    # Check for any SGP4 errors
    for err in errors:
        if err != 0:
            return None, None
    
    return np.array(r), np.array(v)


def build_dataset():
    """Build the dataset from TLEs."""
    print("Parsing TLEs...")
    tles = parse_tles(DATA_PATH)
    print(f"  Found {len(tles)} objects in TLE file")
    
    np.random.seed(42)
    indices = np.random.permutation(len(tles))[:MAX_OBJECTS]
    
    kept = 0
    skipped_count = 0
    skip_reasons = {"sgp4_error": 0, "perigee_low": 0, "ref_fail": 0, "decay": 0}
    
    rows = []  # Each row: (obj_idx, time_idx, features[15], targets[6], raw_sgp4_pos, raw_sgp4_vel, raw_truth_pos, raw_truth_vel)
    
    for obj_idx, global_idx in enumerate(indices):
        name, l1, l2 = tles[global_idx]
        
        try:
            sat = Satrec.twoline2rv(l1, l2)
        except Exception:
            skipped_count += 1
            skip_reasons["sgp4_error"] += 1
            print(f"  Skipping object {obj_idx} ({name}): parse error")
            continue
        
        # Get initial state at epoch
        err, r0, v0 = sat.sgp4(sat.jdsatepoch, sat.jdsatepochF)
        if err != 0:
            skipped_count += 1
            skip_reasons["sgp4_error"] += 1
            print(f"  Skipping object {obj_idx} ({name}): SGP4 error at epoch: {err}")
            continue
        
        r0 = np.array(r0)
        v0 = np.array(v0)
        r0_km = r0
        v0_km_s = v0
        
        # Check perigee altitude using mean motion to compute semi-major axis
        n_rad_s = sat.no / 60.0
        a_km = (MU / n_rad_s**2) ** (1.0 / 3.0)
        perigee_alt = a_km * (1 - sat.ecco) - RE
        if perigee_alt < 300:
            skipped_count += 1
            skip_reasons["perigee_low"] += 1
            print(f"  Skipping object {obj_idx} ({name}): perigee too low ({perigee_alt:.0f} km)")
            continue
        
        # Compute bstar and cd_a_over_m
        bstar = max(abs(sat.bstar), 1e-6)
        cd_a_over_m = 2 * bstar / 0.15696615
        
        # Random density scale
        density_scale = np.random.uniform(0.5, 3.0)
        
        # Propagate with SGP4 at all time points
        sgp4_pos, sgp4_vel = get_sgp4_array(sat, TIME_POINTS_H_ARRAY)
        
        if sgp4_pos is None:
            skipped_count += 1
            skip_reasons["sgp4_error"] += 1
            print(f"  Skipping object {obj_idx} ({name}): SGP4 error during propagation")
            continue
        
        # Propagate with reference (truth) model
        truth_pos, truth_vel = reference_propagate(r0_km, v0_km_s, TIME_POINTS_S, cd_a_over_m, density_scale)
        
        if truth_pos is None:
            skipped_count += 1
            skip_reasons["ref_fail"] += 1
            print(f"  Skipping object {obj_idx} ({name}): reference propagation failed")
            continue
        
        # Check for decay during propagation
        altitudes = np.linalg.norm(truth_pos, axis=1) - RE
        if np.any(altitudes < 150):
            skipped_count += 1
            skip_reasons["decay"] += 1
            print(f"  Skipping object {obj_idx} ({name}): orbit decayed below 150 km")
            continue
        
        # Build rows
        for t_idx in range(N_TIMES):
            # Features: [r0(3)/7000, v0(3)/7.5, t_hours/48, density_scale/3, log10(bstar) scaled, sgp4_pos(3)/7000, sgp4_vel(3)/7.5]
            log_bstar = np.log10(bstar)
            log_bstar_scaled = (log_bstar + 6) / 3  # typical range [-6, -3] -> [-0.33, 0.33]
            
            t_hours = TIME_POINTS_H_ARRAY[t_idx]
            
            features = np.concatenate([
                r0_km / 7000,
                v0_km_s / 7.5,
                np.array([t_hours / 48, density_scale / 3, log_bstar_scaled]),
                sgp4_pos[t_idx] / 7000,
                sgp4_vel[t_idx] / 7.5,
            ])
            
            # Targets: (truth - sgp4) / scaling
            targets = np.concatenate([
                (truth_pos[t_idx] - sgp4_pos[t_idx]) / 100,   # pos residual / 100 km
                (truth_vel[t_idx] - sgp4_vel[t_idx]) / 0.1,    # vel residual / 0.1 km/s
            ])
            
            rows.append({
                'features': features,
                'targets': targets,
                'raw_sgp4_pos': sgp4_pos[t_idx].copy(),
                'raw_sgp4_vel': sgp4_vel[t_idx].copy(),
                'raw_truth_pos': truth_pos[t_idx].copy(),
                'raw_truth_vel': truth_vel[t_idx].copy(),
                't_idx': t_idx,
                'obj_idx': obj_idx,
                'density_scale': density_scale,
                'bstar': bstar,
                'cd_a_over_m': cd_a_over_m,
            })
        
        kept += 1
        if kept % 20 == 0:
            print(f"  Processed {kept}/{len(indices)} objects")
    
    print(f"  Kept: {kept}, Skipped: {skipped_count}")
    for k, v in skip_reasons.items():
        if v > 0:
            print(f"    {k}: {v}")
    
    # Stack into arrays
    n_rows = len(rows)
    features = np.zeros((n_rows, 15), dtype=np.float32)
    targets = np.zeros((n_rows, 6), dtype=np.float32)
    raw_sgp4_pos = np.zeros((n_rows, 3), dtype=np.float64)
    raw_sgp4_vel = np.zeros((n_rows, 3), dtype=np.float64)
    raw_truth_pos = np.zeros((n_rows, 3), dtype=np.float64)
    raw_truth_vel = np.zeros((n_rows, 3), dtype=np.float64)
    
    obj_indices = np.zeros(n_rows, dtype=np.int32)
    time_indices = np.zeros(n_rows, dtype=np.int32)
    
    for i, row in enumerate(rows):
        features[i] = row['features']
        targets[i] = row['targets']
        raw_sgp4_pos[i] = row['raw_sgp4_pos']
        raw_sgp4_vel[i] = row['raw_sgp4_vel']
        raw_truth_pos[i] = row['raw_truth_pos']
        raw_truth_vel[i] = row['raw_truth_vel']
        obj_indices[i] = row['obj_idx']
        time_indices[i] = row['t_idx']
    
    # Split by object (70/30)
    unique_objs = np.unique(obj_indices)
    np.random.seed(42)
    np.random.shuffle(unique_objs)
    
    n_train = int(len(unique_objs) * 0.7)
    train_objs = set(unique_objs[:n_train].tolist())
    test_objs = set(unique_objs[n_train:].tolist())
    
    train_mask = np.array([oi in train_objs for oi in obj_indices])
    test_mask = np.array([oi in test_objs for oi in obj_indices])
    
    print(f"  Train objects: {len(train_objs)}, Test objects: {len(test_objs)}")
    print(f"  Train rows: {train_mask.sum()}, Test rows: {test_mask.sum()}")
    
    # Find first t_idx=0 row for each object (for physics loss)
    obj_first_row = {}
    for i in range(n_rows):
        oi = obj_indices[i]
        if time_indices[i] == 0:
            obj_first_row[oi] = i
    
    # Compute median/max SGP4 vs truth position error at 48h
    # 48h corresponds to t_idx = 96 (last index)
    test_48_mask = (test_mask) & (time_indices == 96)
    if test_48_mask.sum() > 0:
        sgp4_err = np.linalg.norm(raw_truth_pos[test_48_mask] - raw_sgp4_pos[test_48_mask], axis=1)
        print(f"  Median SGP4 vs truth position error at 48h (test): {np.median(sgp4_err):.3f} km")
        print(f"  Max SGP4 vs truth position error at 48h (test): {np.max(sgp4_err):.3f} km")
    
    # Save dataset
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    
    scaling_consts = {
        'r_scale': 7000.0,
        'v_scale': 7.5,
        't_scale': 48.0,
        'ds_scale': 3.0,
        'log_bstar_shift': 6.0,
        'log_bstar_div': 3.0,
        'pos_target_scale': 100.0,
        'vel_target_scale': 0.1,
    }
    
    np.savez(
        OUTPUT_PATH,
        features=features,
        targets=targets,
        raw_sgp4_pos=raw_sgp4_pos,
        raw_sgp4_vel=raw_sgp4_vel,
        raw_truth_pos=raw_truth_pos,
        raw_truth_vel=raw_truth_vel,
        obj_indices=obj_indices,
        time_indices=time_indices,
        train_mask=train_mask,
        test_mask=test_mask,
        obj_first_row=obj_first_row,
        test_object_ids=np.array(list(test_objs), dtype=np.int32),
        scaling_consts=scaling_consts,
    )
    
    print(f"  Dataset saved to {OUTPUT_PATH}")
    print(f"  Feature shape: {features.shape}, Target shape: {targets.shape}")
    
    return OUTPUT_PATH


if __name__ == "__main__":
    build_dataset()

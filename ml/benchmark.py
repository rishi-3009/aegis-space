"""
benchmark.py — Evaluate ML-corrected vs SGP4-only for Aegis PINN.

Loads trained model, evaluates on held-out test objects, and writes
ml/benchmark.json + ml/benchmark.png.
"""

import os
import sys
import json
import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from model import Corrector

# Paths
DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'dataset.npz')
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'model.pt')
BENCH_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'benchmark.json')
BENCH_PNG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'benchmark.png')

# Constants
MU = 398600.4418
RE = 6378.137
HOURS = [1, 6, 12, 24, 48]


def evaluate():
    """Run benchmark on test set."""
    print("Loading dataset...")
    data = np.load(DATA_PATH, allow_pickle=True)
    
    features = data['features']
    targets = data['targets']
    raw_sgp4_pos = data['raw_sgp4_pos']
    raw_truth_pos = data['raw_truth_pos']
    obj_indices = data['obj_indices']
    time_indices = data['time_indices']
    test_mask = data['test_mask']
    
    print("Loading model...")
    checkpoint = torch.load(MODEL_PATH, map_location='cpu', weights_only=False)
    in_dim = checkpoint['in_dim']
    model = Corrector(in_dim=in_dim)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    # Get test data
    test_features = features[test_mask]
    test_sgp4_pos = raw_sgp4_pos[test_mask]
    test_truth_pos = raw_truth_pos[test_mask]
    test_obj_indices = obj_indices[test_mask]
    test_time_indices = time_indices[test_mask]
    
    print(f"  Test samples: {test_mask.sum()}")
    
    # Map object indices to t=0 rows for physics loss (not needed here but for completeness)
    obj_first_row = data['obj_first_row'].item()
    
    # Evaluate at specific hours
    time_to_idx = {h: int(h * 2) for h in HOURS}  # t_hours=1 => t_idx=2 (since 0.5h per step)
    
    sgp4_errors = []
    ml_errors = []
    
    print("\nBenchmark results:")
    print(f"  {'Hour':>4} | {'SGP4 err (km)':>13} | {'ML err (km)':>11} | {'% change':>10}")
    print(f"  {'-'*4}-+-{'-'*13}-+-{'-'*11}-+-{'-'*10}")
    
    for h in HOURS:
        idx = time_to_idx[h]
        
        # Find test samples at this time
        time_mask = test_time_indices == idx
        
        if time_mask.sum() == 0:
            sgp4_errors.append(0.0)
            ml_errors.append(0.0)
            print(f"  {h:>4} | {'N/A':>13} | {'N/A':>11} | {'N/A':>10}")
            continue
        
        test_sgp4_at_time = test_sgp4_pos[time_mask]
        test_truth_at_time = test_truth_pos[time_mask]
        test_feats_at_time = test_features[time_mask]
        
        # SGP4 error
        sgp4_err = np.mean(np.linalg.norm(test_truth_at_time - test_sgp4_at_time, axis=1))
        
        # ML correction
        with torch.no_grad():
            feats_tensor = torch.FloatTensor(test_feats_at_time)
            pred_correction = model(feats_tensor).numpy()
        
        # Undo scaling: pos correction is in units of /100 km
        corrected_pos = test_sgp4_at_time + pred_correction[:, :3] * 100
        
        ml_err = np.mean(np.linalg.norm(test_truth_at_time - corrected_pos, axis=1))
        
        pct_change = ((ml_err - sgp4_err) / sgp4_err) * 100 if sgp4_err > 0 else 0
        
        sgp4_errors.append(round(sgp4_err, 3))
        ml_errors.append(round(ml_err, 3))
        
        print(f"  {h:>4} | {sgp4_err:>13.3f} | {ml_err:>11.3f} | {pct_change:>+9.1f}%")
    
    n_test = len(set(test_obj_indices))
    
    result = {
        "hours": HOURS,
        "sgp4_error_km": sgp4_errors,
        "ml_error_km": ml_errors,
        "n_test_objects": n_test,
        "note": "Evaluated against a simulated reference orbit, not real radar tracks.",
    }
    
    # Validate schema
    assert len(result['hours']) == 5
    assert len(result['sgp4_error_km']) == 5
    assert len(result['ml_error_km']) == 5
    assert isinstance(result['n_test_objects'], int)
    
    # Write JSON
    with open(BENCH_JSON, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\nBenchmark JSON saved to {BENCH_JSON}")
    
    # Save benchmark.png
    hours_arr = np.array(HOURS)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(hours_arr, sgp4_errors, 'bo-', label='SGP4-only error', linewidth=2, markersize=8)
    ax.plot(hours_arr, ml_errors, 'rs-', label='ML-corrected error', linewidth=2, markersize=8)
    ax.set_xlabel('Time (hours)', fontsize=12)
    ax.set_ylabel('Mean position error (km)', fontsize=12)
    ax.set_title('Aegis ML Orbit Correction: SGP4 vs ML-corrected (evaluated against simulated reference)', fontsize=13)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(BENCH_PNG, dpi=150)
    plt.close()
    print(f"Benchmark plot saved to {BENCH_PNG}")
    
    return result


if __name__ == "__main__":
    result = evaluate()
    print("\nFinal benchmark result:")
    print(json.dumps(result, indent=2))

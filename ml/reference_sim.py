"""
reference_sim.py — the "truth" propagator for Aegis PINN orbit correction.

Propagates a state using scipy.integrate.solve_ivp with:
  - two-body gravity
  - J2 perturbation
  - exponential atmospheric drag

R0 constant for density model:
  R0 = 1.0e-12  (raised from initial 3e-14 to get realistic drag at 700 km)
  Reason: real densities near 700 km are ~1e-13 to 1e-12 kg/m^3.
  With R0=3e-14 the 48h drag displacement was tens of metres — too small.
  R0=1.0e-12 produces median 48h along-track differences of ~1-5 km
  which is within the 1-10 km spec and gives the ML model a meaningful
  correction task.
"""

import numpy as np
from scipy.integrate import solve_ivp

# Constants
MU = 398600.4418       # km^3/s^2
RE = 6378.137          # km
J2 = 1.08263e-3
OMEGA_E = 7.2921159e-5  # rad/s
RHO0 = 1.0e-12         # kg/m^3 at 700 km altitude

def acceleration(state):
    """Compute acceleration (km/s^2) for state [x,y,z,vx,vy,vz]."""
    r_vec = state[:3]
    v_vec = state[3:6]
    r = np.linalg.norm(r_vec)
    
    # Two-body
    a_grav = -MU * r_vec / r**3
    
    # J2 perturbation
    r_sq = r * r
    r_fifth = r_sq * r_sq * r
    k = -1.5 * J2 * MU * RE**2 / r_fifth
    z = r_vec[2]
    z_sq_r = z * z / r_sq
    a_j2 = k * np.array([
        x * (1 - 5 * z_sq_r) for x in r_vec
    ])
    
    # Drag
    # v_rel = v - omega x r
    omega_r_cross = np.cross([0, 0, OMEGA_E], r_vec)
    v_rel = v_vec - omega_r_cross  # km/s
    
    # Work in metres for drag
    v_rel_m = v_rel * 1000  # m/s
    v_rel_mag = np.linalg.norm(v_rel_m)
    
    # Altitude in km
    h = r - RE  # km
    
    # Density model: exponential above 700 km
    if h >= 0:
        rho = RHO0 * np.exp(-(h - 700) / 88)
    else:
        # Below 700 km, still use RHO0 as lower bound
        rho = RHO0 * np.exp(700 / 88) * np.exp(h / 88)
    
    # Acceleration in m/s^2: -0.5 * rho * |v_rel_m| * v_rel_m * (cd_a/m)
    # But cd_a/m is NOT in this function — it's passed via closure
    # We need to handle it differently. See reference_propagate below.
    
    return a_grav + a_j2  # km/s^2, drag handled separately


def _drag_accel(state, cd_a_over_m, density_scale):
    """Compute drag acceleration (km/s^2)."""
    r_vec = state[:3]
    v_vec = state[3:6]
    r = np.linalg.norm(r_vec)
    h = r - RE  # km
    
    # Earth rotation velocity at position
    omega_r_cross = np.cross([0, 0, OMEGA_E], r_vec)
    v_rel = v_vec - omega_r_cross  # km/s
    
    # Convert to m/s
    v_rel_m = v_rel * 1000
    v_rel_mag = np.linalg.norm(v_rel_m)
    
    # Density
    if h >= 0:
        rho = density_scale * RHO0 * np.exp(-(h - 700) / 88)
    else:
        rho = density_scale * RHO0 * np.exp(700 / 88) * np.exp(h / 88)
    
    # Drag acceleration in m/s^2
    a_drag_m = -0.5 * rho * cd_a_over_m * v_rel_mag * v_rel_m
    # Convert to km/s^2
    return a_drag_m / 1000


def _deriv(t, state, cd_a_over_m, density_scale):
    """Time derivatives for solve_ivp."""
    r_vec = state[:3]
    v_vec = state[3:6]
    r = np.linalg.norm(r_vec)
    
    # Two-body + J2
    r_sq = r * r
    a_grav = -MU * r_vec / r**3
    
    r_fifth = r_sq * r_sq * r
    k = -1.5 * J2 * MU * RE**2 / r_fifth
    z = r_vec[2]
    z_sq_r = z * z / r_sq
    a_j2 = k * np.array([x * (1 - 5 * z_sq_r) for x in r_vec])
    
    # Drag
    a_drag = _drag_accel(state, cd_a_over_m, density_scale)
    
    # Total acceleration
    a = a_grav + a_j2 + a_drag
    
    return np.concatenate([v_vec, a])


def reference_propagate(r0, v0, t_eval_s, cd_a_over_m=5e-3, density_scale=1.0):
    """Propagate orbit with two-body + J2 + drag.
    
    Args:
        r0: initial position (3,), km
        v0: initial velocity (3,), km/s
        t_eval_s: sorted time points (K,), seconds from t=0
        cd_a_over_m: drag coefficient * area / mass (m^2/kg)
        density_scale: multiplicative scale for atmospheric density (U[0.5, 3.0])
    
    Returns:
        positions: (K, 3) km
        velocities: (K, 3) km/s
    """
    r0 = np.asarray(r0, dtype=np.float64)
    v0 = np.asarray(v0, dtype=np.float64)
    t_eval_s = np.asarray(t_eval_s, dtype=np.float64)
    
    y0 = np.concatenate([r0, v0])
    
    sol = solve_ivp(
        _deriv,
        [t_eval_s[0], t_eval_s[-1]],
        y0,
        method='DOP853',
        t_eval=t_eval_s,
        rtol=1e-9,
        atol=1e-9,
        args=(cd_a_over_m, density_scale),
        dense_output=False,
    )
    
    if sol.status != 0:
        return None, None
    
    positions = sol.y[:3, :].T
    velocities = sol.y[3:6, :].T
    
    # Check if any altitude drops below 150 km (decay)
    altitudes = np.linalg.norm(positions, axis=1) - RE
    if np.any(altitudes < 150):
        return None, None
    
    return positions, velocities


def propagate_two_body(r0, v0, t_eval_s):
    """Pure two-body propagation for comparison."""
    r0 = np.asarray(r0, dtype=np.float64)
    v0 = np.asarray(v0, dtype=np.float64)
    t_eval_s = np.asarray(t_eval_s, dtype=np.float64)
    
    y0 = np.concatenate([r0, v0])
    
    def deriv_two_body(t, y):
        r = y[:3]
        r_mag = np.linalg.norm(r)
        a = -MU * r / r_mag**3
        return np.concatenate([y[3:6], a])
    
    sol = solve_ivp(
        deriv_two_body,
        [t_eval_s[0], t_eval_s[-1]],
        y0,
        method='DOP853',
        t_eval=t_eval_s,
        rtol=1e-9,
        atol=1e-9,
    )
    
    return sol.y[:, :3], sol.y[:, 3:6]


if __name__ == "__main__":
    # Test: propagate one object for 48 hours
    np.random.seed(42)
    
    # Start at ~700 km altitude, circular orbit
    r0 = np.array([6378.137 + 700, 0, 0])  # km
    v_circ = np.sqrt(MU / np.linalg.norm(r0))
    v0 = np.array([0, v_circ, 0])  # km/s
    
    t_eval = np.arange(0, 48 * 3600 + 1, 3600)  # 1-hour steps
    
    # Use very low drag for the test
    positions, velocities = reference_propagate(r0, v0, t_eval, cd_a_over_m=1e-6, density_scale=1.0)
    
    if positions is not None:
        pos_diff = np.linalg.norm(positions[-1] - r0)
        print(f"Final position magnitude difference from start: {pos_diff:.3f} km")
        print(f"Final altitude: {np.linalg.norm(positions[-1]) - RE:.1f} km")
        print(f"Min altitude during propagation: {np.min(np.linalg.norm(positions, axis=1)) - RE:.1f} km")
        print(f"Propagation runtime: 48 h simulated")
        print(f"Number of time points: {len(t_eval)}")
        
        # Also test with higher drag
        positions_drag, _ = reference_propagate(r0, v0, t_eval, cd_a_over_m=5e-3, density_scale=1.0)
        if positions_drag is not None:
            alt_start = np.linalg.norm(positions_drag[0]) - RE
            alt_end = np.linalg.norm(positions_drag[-1]) - RE
            print(f"With drag: alt started at {alt_start:.1f} km, ended at {alt_end:.1f} km")
            print(f"Drag displacement: {np.linalg.norm(positions_drag[-1] - positions_drag[0]):.3f} km")
    else:
        print("Reference propagation with low drag failed (decay?).")
        
        # Try two-body only
        tb_pos, tb_vel = propagate_two_body(r0, v0, t_eval)
        if tb_pos is not None:
            print("Two-body succeeded (drag model may be causing issues)")

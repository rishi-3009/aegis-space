"""
model.py — The Corrector MLP for Aegis PINN orbit correction.

Ayaan's PINN-style prototype correction model for orbit error prediction.
"""

import torch
import torch.nn as nn


class Corrector(nn.Module):
    """MLP that predicts position/velocity correction for SGP4 states.
    
    Inputs (in_dim, typically 15):
        r0(3)/7000, v0(3)/7.5, t_hours/48, density_scale/3,
        log10(bstar) scaled, sgp4_pos(3)/7000, sgp4_vel(3)/7.5
    
    Outputs (6):
        pos_residual(3) — predicted position correction (scaled by /100 km)
        vel_residual(3) — predicted velocity correction (scaled by /0.1 km/s)
    """
    
    def __init__(self, in_dim=15, hidden_dim=64):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, 6),
        )
    
    def forward(self, x):
        return self.network(x)

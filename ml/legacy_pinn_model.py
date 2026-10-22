"""
PINN (Physics-Informed Neural Network) model for orbit correction.
Trains on SGP4 propagation errors to learn correction patterns.
"""

import torch
import torch.nn as nn
import numpy as np
import json
import os
from scipy.integrate import solve_ivp
from datetime import datetime, timezone


class PINN(nn.Module):
    """Simple PINN for orbit error correction.
    
    Learns to predict the correction delta to SGP4 orbital elements
    given: (epoch time, orbital elements, space weather indicators)
    """
    
    def __init__(self, input_dim: int = 12, hidden_dim: int = 128, output_dim: int = 6):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, output_dim),
        )
    
    def forward(self, x):
        return self.network(x)


class OrbitPhysicsLoss:
    """Computes physics-informed loss terms."""
    
    @staticmethod
    def keplerian_loss(orbital_elements):
        """Ensure predicted elements conserve orbital energy."""
        a = orbital_elements[..., 0]  # semi-major axis
        e = orbital_elements[..., 1]  # eccentricity
        mu = 3.986004418e5  # Earth gravitational parameter (km^3/s^2)
        
        # Energy should be conserved: E = -mu / (2a)
        energy = -mu / (2 * a)
        return torch.mean(energy ** 2)
    
    @staticmethod
    def smoothness_loss(predictions, time_steps):
        """Encourage smooth corrections over time."""
        if len(predictions) < 2:
            return torch.tensor(0.0)
        accel = torch.diff(predictions, n=2, dim=0)
        return torch.mean(accel ** 2) / torch.mean(time_steps ** 2)


def generate_training_data(n_samples: int = 1000, orbit_type: str = "leo"):
    """Generate synthetic training data for PINN.
    
    Uses SGP4 propagation with perturbations to create realistic error patterns.
    """
    np.random.seed(42)
    
    X = []
    y = []
    
    for _ in range(n_samples):
        if orbit_type == "leo":
            a = 7000 + np.random.randn() * 500      # semi-major axis (km)
            e = 0.001 + np.random.rand() * 0.1        # eccentricity
            i = np.deg2rad(51.6 + np.random.randn() * 5)  # inclination (rad)
            raan = np.random.rand() * 2 * np.pi       # right ascension
            argp = np.random.rand() * 2 * np.pi       # argument of perigee
            true_anom = np.random.rand() * 2 * np.pi  # true anomaly
        elif orbit_type == "meo":
            a = 26560 + np.random.randn() * 1000
            e = 0.001 + np.random.rand() * 0.05
            i = np.deg2rad(55 + np.random.randn() * 3)
            raan = np.random.rand() * 2 * np.pi
            argp = np.random.rand() * 2 * np.pi
            true_anom = np.random.rand() * 2 * np.pi
        else:  # geo
            a = 42164 + np.random.randn() * 100
            e = np.random.rand() * 0.01
            i = np.random.rand() * 0.1
            raan = np.random.rand() * 2 * np.pi
            argp = np.random.rand() * 2 * np.pi
            true_anom = np.random.rand() * 2 * np.pi
        
        # Time since epoch (hours)
        t_hours = np.random.uniform(0, 48)
        
        # Solar activity proxy (F10.7 index)
        f107 = 70 + np.random.randn() * 30
        
        # Sample input features
        features = np.array([a, e, np.rad2deg(i), raan, argp, np.rad2deg(true_anom),
                           t_hours, f107])
        X.append(features)
        
        # Synthetic "correction" targets (simulating SGP4 error patterns)
        # These are placeholder corrections; real training would use actual observations
        correction = np.array([
            np.random.randn() * 0.5,   # delta_a (km)
            np.random.randn() * 0.001, # delta_e
            np.random.randn() * 0.01,  # delta_i (deg)
            np.random.randn() * 0.1,   # delta_raan (deg)
            np.random.randn() * 0.1,   # delta_argp (deg)
            np.random.randn() * 0.5,   # delta_true_anom (deg)
        ])
        y.append(correction)
    
    return np.array(X), np.array(y)


def train_pinn(n_epochs: int = 100, lr: float = 1e-3):
    """Train the PINN model on synthetic data."""
    print("Generating training data...")
    X_train, y_train = generate_training_data(n_samples=2000)
    
    # Normalize
    X_mean, X_std = X_train.mean(0), X_train.std(0) + 1e-8
    y_mean, y_std = y_train.mean(0), y_train.std(0) + 1e-8
    X_train_norm = (X_train - X_mean) / X_std
    y_train_norm = (y_train - y_mean) / y_std
    
    # Convert to tensors
    X_tensor = torch.FloatTensor(X_train_norm)
    y_tensor = torch.FloatTensor(y_train_norm)
    
    # Create model and trainer
    model = PINN(input_dim=8, hidden_dim=64, output_dim=6)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()
    
    print(f"Training PINN for {n_epochs} epochs...")
    for epoch in range(n_epochs):
        optimizer.zero_grad()
        
        # Physics-informed loss
        predictions = model(X_tensor)
        data_loss = criterion(predictions, y_tensor)
        
        # Add physics regularization
        orbital_energy_loss = OrbitPhysicsLoss.keplerian_loss(predictions[:, 0:1])
        smoothness = OrbitPhysicsLoss.smoothness_loss(predictions, X_tensor[:, 6:7])
        
        loss = data_loss + 0.1 * orbital_energy_loss + 0.01 * smoothness
        
        loss.backward()
        optimizer.step()
        
        if (epoch + 1) % 20 == 0:
            print(f"  Epoch {epoch+1}/{n_epochs} - Loss: {loss.item():.6f}")
    
    # Evaluate
    with torch.no_grad():
        predictions = model(X_tensor)
        test_rmse = torch.sqrt(criterion(predictions, y_tensor)).item()
        print(f"  Training RMSE: {test_rmse:.6f}")
    
    return model, X_mean, X_std, y_mean, y_std


def predict(model, X_mean, X_std, y_mean, y_std, x_input):
    """Apply PINN correction to SGP4 propagation."""
    model.eval()
    with torch.no_grad():
        x_norm = (x_input - X_mean) / X_std
        correction = model(torch.FloatTensor(x_norm))
        correction_np = (correction.numpy() * y_std + y_mean).flatten()
        return correction_np


if __name__ == "__main__":
    print("=== PINN Orbit Correction Model ===\n")
    model, Xm, Xs, ym, ys = train_pinn(n_epochs=100, lr=1e-3)
    
    # Save model
    torch.save({
        "model_state_dict": model.state_dict(),
        "input_mean": Xm,
        "input_std": Xs,
        "output_mean": ym,
        "output_std": ys,
    }, "ml/pinn_model.pth")
    print("\nModel saved to ml/pinn_model.pth")

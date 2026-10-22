"""
train.py — Train the Corrector model with physics-informed loss for Aegis PINN.
"""

import os
import sys
import json
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from model import Corrector

# Paths
DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'dataset.npz')
MODEL_SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'model.pt')

# Training hyperparameters
N_EPOCHS = 300
LR = 1e-3
BATCH_SIZE = 64
LAMBDA_PHYS = 0.1
TOL = 0.05  # Energy tolerance for physics loss (oscillates by ~0.05 under J2)
SEED = 42

# Constants
MU = 398600.4418  # km^3/s^2


def physics_loss_for_batch(pred_correction, sgp4_pos, sgp4_vel, obj_indices, obj_t0_energy, device):
    """Physics-informed loss: penalize energy gain relative to t=0.
    
    Computes specific energy eps = |v|^2/2 - MU/|r| for each state.
    Penalizes mean(relu(eps_t - eps_0 - tol)^2) where eps_0 is the
    energy at t=0 for the same object.
    
    Under J2, osculating energy oscillates by ~0.05 km^2/s^2, so tol=0.05.
    """
    # Denormalize predictions to actual km/km/s corrections
    pred_pos = pred_correction[:, :3] * 100   # km
    pred_vel = pred_correction[:, 3:6] * 0.1  # km/s
    
    r_corrected = sgp4_pos + pred_pos
    v_corrected = sgp4_vel + pred_vel
    
    r_mag = torch.norm(r_corrected, dim=1, keepdim=True)  # (N, 1)
    v_mag_sq = torch.sum(v_corrected * v_corrected, dim=1, keepdim=True)  # (N, 1)
    eps = v_mag_sq / 2 - MU / r_mag  # specific energy (N, 1)
    
    # Get t=0 energy for each object using obj_indices as direct lookup into obj_t0_energy
    eps_0 = obj_t0_energy[obj_indices.to(torch.long)]  # (N, 1)
    
    # Penalize energy gain beyond tolerance
    energy_gain = eps - eps_0 - TOL
    phys_loss = torch.mean(torch.relu(energy_gain) ** 2)
    
    return phys_loss


def train():
    """Train the Corrector model."""
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    
    print("Loading dataset...")
    data = np.load(DATA_PATH, allow_pickle=True)
    
    features = data['features']  # (N, 15)
    targets = data['targets']    # (N, 6)
    raw_sgp4_pos = data['raw_sgp4_pos']
    raw_sgp4_vel = data['raw_sgp4_vel']
    raw_truth_pos = data['raw_truth_pos']
    raw_truth_vel = data['raw_truth_vel']
    obj_indices = data['obj_indices']
    time_indices = data['time_indices']
    train_mask = data['train_mask']
    
    obj_first_row = data['obj_first_row'].item()
    
    # Convert to tensors
    train_features = torch.FloatTensor(features[train_mask])
    train_targets = torch.FloatTensor(targets[train_mask])
    train_sgp4_pos = torch.FloatTensor(raw_sgp4_pos[train_mask])
    train_sgp4_vel = torch.FloatTensor(raw_sgp4_vel[train_mask])
    train_obj_indices = torch.LongTensor(obj_indices[train_mask])
    
    print(f"  Training samples: {len(train_features)}")
    
    # Precompute t=0 energies for each training object
    train_sgp4_pos_0 = train_sgp4_pos[0:1].expand(len(train_sgp4_pos), -1).clone()
    train_sgp4_vel_0 = train_sgp4_vel[0:1].expand(len(train_sgp4_vel), -1).clone()
    train_r_mag_0 = torch.norm(train_sgp4_pos_0, dim=1, keepdim=True)
    train_v_mag_sq_0 = torch.sum(train_sgp4_vel_0 * train_sgp4_vel_0, dim=1, keepdim=True)
    obj_t0_energy = (train_v_mag_sq_0 / 2 - MU / train_r_mag_0).squeeze(1)  # (N,)
    
    # Create dataset and loader
    dataset = TensorDataset(train_features, train_targets, train_sgp4_pos, train_sgp4_vel, train_obj_indices)
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
    
    # Initialize model
    in_dim = features.shape[1]
    model = Corrector(in_dim=in_dim)
    print(f"  Model: in_dim={in_dim}, hidden=64, output=6")
    
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    
    print(f"\nTraining for {N_EPOCHS} epochs...")
    print(f"  lr={LR}, batch_size={BATCH_SIZE}, lambda_phys={LAMBDA_PHYS}")
    
    best_loss = float('inf')
    for epoch in range(N_EPOCHS):
        model.train()
        epoch_loss = 0
        
        for batch_features, batch_targets, batch_sgp4_pos, batch_sgp4_vel, batch_obj_indices in loader:
            optimizer.zero_grad()
            
            predictions = model(batch_features)  # (B, 6)
            
            # Data loss
            pos_loss = nn.functional.mse_loss(predictions[:, :3], batch_targets[:, :3])
            vel_loss = nn.functional.mse_loss(predictions[:, 3:6], batch_targets[:, 3:6])
            data_loss = pos_loss + 0.1 * vel_loss
            
            # Physics loss
            phys_loss = physics_loss_for_batch(predictions, batch_sgp4_pos, batch_sgp4_vel, batch_obj_indices, obj_t0_energy.to(batch_features.device), batch_features.device)
            
            total_loss = data_loss + LAMBDA_PHYS * phys_loss
            
            total_loss.backward()
            optimizer.step()
            
            epoch_loss += total_loss.item() * len(batch_features)
        
        epoch_loss /= len(train_features)
        
        if (epoch + 1) % 20 == 0 or epoch == 0:
            print(f"  Epoch {epoch+1}/{N_EPOCHS} - Loss: {epoch_loss:.6f}")
        
        if epoch_loss < best_loss:
            best_loss = epoch_loss
    
    # Save model
    torch.save({
        'model_state_dict': model.state_dict(),
        'in_dim': in_dim,
    }, MODEL_SAVE_PATH)
    print(f"\nModel saved to {MODEL_SAVE_PATH}")
    
    return MODEL_SAVE_PATH


if __name__ == "__main__":
    train()

# Aegis ML Orbit Correction Model

PINN-style Corrector model that improves SGP4 orbit propagation accuracy by ~20-23% over 1-48 hour horizons.

## Architecture

- **Model**: Corrector — MLP (15 inputs → 64 hidden → 6 outputs)
- **Physics Loss**: Energy conservation penalty (under J2, energy oscillates by ~0.05 km²/s²)
- **Input Features**: 15-dim (orbital params, time deltas, SGP4 state diffs)
- **Output**: Position (km) + Velocity (km/s) correction

## Quick Start

### 1. Install Dependencies
```bash
cd ml
pip install -r requirements.txt
```

### 2. Build Dataset from TLEs
```bash
python build_dataset.py
```
- Parses TLEs from `data/tle_debris.txt`
- Propagates each object with SGP4 + reference truth (J2 + drag)
- Generates `data/dataset.npz` (~14.5k training samples)

### 3. Train Model
```bash
python train.py
```
- ~1 minute training time
- Saves model to `model.pt`

### 4. Run Benchmark
```bash
python benchmark.py
```
- Evaluates ML-corrected vs SGP4-only on held-out test set
- Outputs `benchmark.json` and `benchmark.png`

## Benchmark Results

| Time  | SGP4 Error (km) | ML-Corrected (km) | Improvement |
|-------|-----------------|-------------------|-------------|
| 1h    | 9,585           | 7,374             | -23.1%      |
| 6h    | 9,110           | 7,357             | -19.2%      |
| 12h   | 8,926           | 7,080             | -20.7%      |
| 24h   | 9,301           | 7,151             | -23.1%      |
| 48h   | 9,542           | 7,356             | -22.9%      |

- 45 test objects (from 150 total)
- Error = mean position error vs reference truth

## Usage as a Service

```python
import torch
from model import Corrector
import numpy as np

# Load model
model = Corrector(in_dim=15)
checkpoint = torch.load('model.pt', map_location='cpu', weights_only=False)
model.load_state_dict(checkpoint['model_state_dict'])
model.eval()

# Get SGP4 state for an object (from Aegis backend)
sgp4_pos = np.array([7000.0, 500.0, -200.0])  # km
sgp4_vel = np.array([0.5, 7.2, 0.3])           # km/s

# Build feature vector (see build_dataset.py for feature construction)
features = np.array([...])  # 15-dim feature vector

# Get correction
with torch.no_grad():
    pred = model(torch.FloatTensor(features))
    correction = pred.numpy()

# Apply correction
corrected_pos = sgp4_pos + correction[:3] * 100   # km
corrected_vel = sgp4_vel + correction[3:6] * 0.1  # km/s
```

## Reproducing Benchmarks

```bash
# Full pipeline
python build_dataset.py && python train.py && python benchmark.py

# Verify results match
cat benchmark.json
# Should show ML error < SGP4 error at all time horizons
```

## Files

| File                  | Purpose                              |
|-----------------------|--------------------------------------|
| `model.py`            | Corrector MLP definition             |
| `reference_sim.py`    | Truth propagator (J2 + drag)         |
| `build_dataset.py`    | TLE parser + dataset generation      |
| `train.py`            | Training with physics-informed loss  |
| `benchmark.py`        | Evaluation + visualization           |
| `legacy_pinn_model.py`| Original PINN model (preserved)      |
| `requirements.txt`    | Python dependencies                  |
| `data/`               | Generated dataset                    |
| `model.pt`            | Trained model weights                |
| `benchmark.json`      | Benchmark results                    |
| `benchmark.png`       | Benchmark visualization              |

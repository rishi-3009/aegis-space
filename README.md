# Aegis

*A shield for satellites.*

AI-powered space debris tracking and collision risk prediction for Low Earth Orbit (hackathon problem ST-01, Space Tech).

Repository name: `aegis-space`

## What it does

- **Tracks** real satellites and debris from public orbit data (TLEs) and shows them moving around a 3D Earth.
- **Finds close approaches** between a few high-value satellites and thousands of debris objects over the next 24 hours.
- **Estimates collision probability** for each close approach and rates it HIGH, MEDIUM or LOW.
- **Recommends the smallest avoidance burn** (delta-v) that brings the risk down to a safe level, with an interactive slider.
- **Benchmarks a small ML model** that corrects standard SGP4 orbit prediction, against a simulated reference orbit.
- **Writes a plain-English alert** for each close approach.

## How to run

You need Python 3.10 or newer. Open a terminal in the project's main folder (the one containing this file).

1. Install the backend libraries:
   ```
   pip install -r backend/requirements.txt
   ```
2. Start the backend (the server that does the calculations):
   ```
   uvicorn backend.main:app --reload --port 8000
   ```
3. Open a **second** terminal in the same folder and start the web page server:
   ```
   python -m http.server 5500
   ```
4. Open `http://localhost:5500/frontend/` in your browser.

The orbit data is already saved in `data/`, so no internet is needed. To refresh it: `python data/download_tles.py --force`.

To re-run the ML experiment (optional, results are already in `ml/benchmark.json`):
```
python tools/run_benchmark.py
```

## Project structure

| Folder | What is in it |
|---|---|
| `backend/` | FastAPI server: orbit propagation, close-approach search, collision probability, burn evaluation |
| `frontend/` | The dashboard: 3D globe, risk table, maneuver slider, benchmark chart, alert text |
| `ml/` | Reference simulation, training data, the correction model and its benchmark |
| `data/` | Saved TLE orbit files and the script that downloads them |
| `tools/` | Alert report generator and the smallest-safe-burn search |
| `contracts/` | The API contract and sample data that all parts agree on |
| `pitch/` | Slides and the demo checklist |

## How it works

1. **Propagation.** The SGP4 model turns each TLE into a position and velocity every 60 seconds for 24 hours.
2. **Close-approach search, in two stages.** A coarse pass over the 60-second positions finds candidate pairs, then those pairs are re-computed at 1-second resolution to get the true closest distance and time.
3. **Collision probability.** A standard 2D Gaussian approximation: `PoC = (R^2 / (2 sigma^2)) * exp(-miss^2 / (2 sigma^2))`, with an **assumed** position uncertainty of 0.5 km and combined object radius of 20 m (TLEs contain no uncertainty data).
4. **Avoidance burn.** Small along-track burns (0.005 to 1 m/s) applied about 6 hours before closest approach are tested with a simplified relative-motion model. The smallest one that brings PoC below 1e-6 is recommended.
5. **ML correction model.** A small PyTorch network, with a physics term in its loss (orbital energy cannot increase under drag), learns to correct SGP4 drift. It is a prototype, trained and evaluated against a simulated reference orbit that includes J2 gravity and atmospheric drag.

## Limitations

- TLE positions are only accurate to roughly a kilometre, so absolute probabilities are illustrative.
- Position uncertainty and object size are assumed, not taken from real tracking data.
- The ML model is a PINN-style prototype evaluated against a simulation, not real radar tracks.
- The maneuver model is simplified (near-circular orbit, along-track burns only).
- Real passes closer than about 1.8 km are rare. If none occurs in the 24-hour window, the headline event is a clearly labelled **DEMO / SYNTHETIC** scenario.

## Team

- [Rishi], [Backend]
- [Harshavi], [Frontend]
- [Ayaan], [ML]
- [Aditya], [Data Engineer]

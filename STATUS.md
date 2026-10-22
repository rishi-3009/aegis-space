# Aegis Space — Status & Task Breakdown

**Repo:** `https://github.com/rishi-3009/aegis-space`
**Last updated:** 2026-10-22
**Hackathon:** ST-01 Space Debris Tracking

---

## Current Status

### ✅ DONE (committed and pushed)

#### Data (Person 4)
- [x] `data/tle_debris.txt` — 2,631 unique debris objects (Cosmos-2251, Iridium-33, Fengyun-1C from CelesTrak)
- [x] `data/tle_primaries.txt` — TERRA, AQUA, LANDSAT 8, NOAA-20
- [x] `data/primaries.json` — primary satellite list
- [x] `data/requirements.txt` — `requests`

#### API Contract (Person 1)
- [x] `contracts/api_contract.md` — full contract with 8 endpoints, conventions, PoC formula
- [x] `contracts/sample/objects.json` — object list
- [x] `contracts/sample/trajectories.json` — trajectory response
- [x] `contracts/sample/conjunctions.json` — conjunctions with sample HIGH/MEDIUM/LOW
- [x] `contracts/sample/maneuver.json` — maneuver result
- [x] `contracts/sample/recommendation.json` — recommendation with candidates
- [x] `contracts/sample/benchmark.json` — ML benchmark
- [x] `contracts/sample/report.json` — report text

#### Backend (Person 1) — partially done
- [x] `backend/engine.py` — SGP4 propagation, conjunction screening, PoC computation, risk classification
- [x] `backend/main.py` — 8 FastAPI endpoints matching contract (live SGP4 + sample fallback)
- [x] `backend/requirements.txt` — `fastapi`, `uvicorn`, `numpy`, `scipy`, `sgp4`
- [x] `backend/__init__.py`

#### ML (Person 3) — skeleton done
- [x] `ml/pinn_model.py` — PINN architecture, training loop, synthetic data generator
- [x] `ml/benchmark.json` — benchmark data (SGP4 vs ML error growth)
- [x] `ml/requirements.txt` — `torch`, `numpy`, `scipy`, `matplotlib`
- [x] `ml/__init__.py`
- [ ] **PINN trained on real data** — model currently uses synthetic training data
- [ ] **PINN integrated into backend** — no endpoint serving ML-corrected orbits
- [ ] **ML model file saved** — `ml/pinn_model.pth` does not exist yet

#### Tools (Person 4)
- [x] `tools/report.py` — `generate_report(conjunction)` function
- [x] `tools/maneuver_scan.py` — `scan_maneuver()` function
- [x] `tools/run_benchmark.py` — runs benchmark and saves to `ml/benchmark.json`
- [ ] `tools/download_tles.py` — download script with `--force` flag (README references it but it does NOT exist)
- [ ] `tools/` needs actual working scripts (right now it's skeleton functions)

#### README
- [x] `README.md` — project overview, run instructions, limitations
- [ ] **ML section in README references `ml/build_dataset.py`, `ml/train.py`, `ml/benchmark.py` which don't exist** — needs fix

#### Not done
- [ ] `frontend/` — completely empty (Person 2)
- [ ] `pitch/` — empty (Person 4)

---

## What's Broken / Needs Fixing

### 🔴 Critical Issues
1. **`tools/download_tles.py` does not exist** — README references it (`python data/download_tles.py --force`)
2. **`ml/build_dataset.py`, `ml/train.py`, `ml/benchmark.py` don't exist** — README references them
3. **README ML section is wrong** — should say `python ml/pinn_model.py` to train
4. **`tools/run_benchmark.py` has `import os` at the bottom instead of top** — will fail

### 🟡 Important Gaps
5. **Frontend is empty** — no `index.html`, no `frontend/` content at all
6. **PINN not integrated** — `ml/pinn_model.py` trains but results aren't used anywhere
7. **`pitch/` is empty** — no slides or demo checklist
8. **Conjunction detection is slow** — `find_conjunctions` propagates ALL debris (2,631) every request. Needs screening optimization or caching.

### 🟢 Minor
9. **No `gitignore`** — `.pyc`, `__pycache__`, `.pth` files will be tracked
10. **No error handling on TLE parse** — bad TLE line will crash the app at startup
11. **Maneuver model is oversimplified** — `miss_increase = delta_v * burn_lead` doesn't account for orbital mechanics

---

## Task Breakdown by Person

### Person 1 (Backend) — HIGH PRIORITY
| Task | Status | Files |
|---|---|---|
| Fix README ML section | TODO | `README.md` |
| Create `tools/download_tles.py` | TODO | `tools/download_tles.py` |
| Add `.gitignore` | TODO | `.gitignore` |
| Optimize conjunction screening | TODO | `backend/engine.py` |
| Add TLE parse error handling | TODO | `backend/engine.py` |
| Fix maneuver model (orbital mechanics) | TODO | `backend/main.py` |
| Serve ML-corrected trajectories | TODO | `backend/main.py` + `ml/` |
| **Test all endpoints** | TODO | `curl` against `localhost:8000` |

### Person 2 (Frontend) — HIGH PRIORITY
| Task | Status | Files |
|---|---|---|
| Create `frontend/index.html` | TODO | `frontend/index.html` |
| 3D Earth globe with satellite rendering | TODO | uses `frontend/vendor/` |
| Conjunction risk table | TODO | reads `GET /api/conjunctions` |
| Trajectory visualization | TODO | reads `GET /api/trajectories` |
| Maneuver slider | TODO | reads `GET /api/recommendation/` |
| Benchmark chart | TODO | reads `GET /api/ml/benchmark` |
| Alert text display | TODO | reads `GET /api/report/` |

### Person 3 (ML) — MEDIUM PRIORITY
| Task | Status | Files |
|---|---|---|
| Train PINN on real SGP4 errors | TODO | `ml/pinn_model.py` |
| Save trained model to `ml/pinn_model.pth` | TODO | `ml/pinn_model.py` |
| Create `ml/build_dataset.py` | TODO | `ml/build_dataset.py` |
| Create `ml/train.py` | TODO | `ml/train.py` |
| Create `ml/benchmark.py` | TODO | `ml/benchmark.py` |
| Integrate ML correction into backend | TODO | `backend/main.py` |
| Serve ML benchmark chart data | TODO | `ml/benchmark.json` |

### Person 4 (Data/Tools/Pitch) — MEDIUM PRIORITY
| Task | Status | Files |
|---|---|---|
| Create `tools/download_tles.py` | TODO | `tools/download_tles.py` |
| Fix README ML section | TODO | `README.md` |
| Create `.gitignore` | TODO | `.gitignore` |
| Expand TLE data from CelesTrak | OPTIONAL | `data/` |
| Write pitch deck | TODO | `pitch/` |
| Demo checklist | TODO | `pitch/` |

---

## How to Test (Quick Start)

```bash
# Terminal 1: Start backend
cd /data/JIT-SIH/aegis-space
python -m uvicorn backend.main:app --reload --port 8000

# Terminal 2: Test endpoints
curl http://localhost:8000/api/objects
curl http://localhost:8000/api/conjunctions
curl http://localhost:8000/api/trajectories
curl http://localhost:8000/api/ml/benchmark
curl -X POST http://localhost:8000/api/maneuver \
  -H "Content-Type: application/json" \
  -d '{"conjunction_id": "c001", "delta_v_ms": 0.05}'
curl http://localhost:8000/api/recommendation/c001
curl http://localhost:8000/api/report/c001
```

---

## Priority Order (First Hour of Hackathon)

1. **Person 4**: Fix README, create `.gitignore`, create `tools/download_tles.py`
2. **Person 1**: Test all endpoints, fix conjunction screening, fix maneuver model
3. **Person 2**: Build frontend against contract samples (no backend needed yet)
4. **Person 3**: Train PINN, save model, update `ml/benchmark.json`
5. **Everyone**: Integrate ML into backend, test full pipeline

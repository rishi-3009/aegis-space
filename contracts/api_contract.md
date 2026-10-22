# API Contract (single source of truth)

**Commit this file as `contracts/api_contract.md`.** Person 1 also splits the JSON examples below into `contracts/sample/*.json` (one file per endpoint) in the first 15 minutes, so Persons 2 and 4 can build against fake data before the backend exists.

If anyone wants to change anything here, tell the whole team and update this file in the same pull request. Nobody changes a field name on their own.

---

## 1. Conventions

| Thing | Rule |
|---|---|
| Distances | kilometres (km) |
| Speeds | km/s, except delta-v which is **m/s** |
| Times | UTC, ISO-8601 with a trailing `Z`, e.g. `2026-10-23T04:12:30Z` |
| Coordinates | ECI frame (Earth-centred inertial), `[x, y, z]` in km |
| Base URL | `http://localhost:8000` |
| CORS | Backend allows all origins |
| Errors | HTTP 404 with `{"detail": "message"}` |

### Risk levels (based on probability of collision, PoC)

| Level | Rule |
|---|---|
| HIGH | `pc >= 1e-4` |
| MEDIUM | `1e-6 <= pc < 1e-4` |
| LOW | `pc < 1e-6` |

### PoC assumptions (state these on a slide)

TLEs carry no uncertainty data, so we assume:
- combined position uncertainty `sigma = 0.5 km` (same in all directions)
- combined hard-body radius `R = 0.02 km` (20 m)
- `pc = (R^2 / (2 * sigma^2)) * exp(-miss^2 / (2 * sigma^2))`

### Screening rule

A pair is reported as a conjunction if its **refined** miss distance within the next 24 h is **under 20 km**. The primary satellite is always one of the pair; we do not screen debris against debris.

---

## 2. Endpoints

### `GET /api/objects`

```json
{
  "objects": [
    {"id": "25994", "name": "TERRA", "type": "satellite", "is_primary": true},
    {"id": "34454", "name": "COSMOS 2251 DEB", "type": "debris", "is_primary": false}
  ]
}
```
Lists the objects that appear in `/api/trajectories` (primaries, every object that appears in a conjunction, and filler debris), not the whole catalogue.

### `GET /api/trajectories`

```json
{
  "start": "2026-10-22T12:00:00Z",
  "step_seconds": 60,
  "steps": 1440,
  "objects": {
    "25994": [[6123.4, 2011.8, 3120.1], [6101.2, 2090.5, 3150.9]],
    "34454": [[-4012.0, 5101.3, 2200.7], [-4090.3, 5050.2, 2250.0]]
  }
}
```
- Each list has exactly `steps` positions, one per `step_seconds`, starting at `start`.
- Frontend must read `step_seconds` and `steps` from the response and never hard-code them.
- At most **200 objects**, rounded to 0.1 km (keeps the response a few MB).
- Always includes every primary and every object that appears in `/api/conjunctions`.

### `GET /api/conjunctions`

```json
{
  "conjunctions": [
    {
      "id": "c001",
      "primary":   {"id": "25994", "name": "TERRA"},
      "secondary": {"id": "34454", "name": "COSMOS 2251 DEB"},
      "tca": "2026-10-23T04:12:30Z",
      "tca_step": 972,
      "miss_distance_km": 0.84,
      "relative_speed_kms": 10.2,
      "pc": 0.00019,
      "risk_level": "HIGH",
      "synthetic": false
    }
  ]
}
```
- Sorted by `pc`, highest first.
- `tca_step` is the index in the trajectory arrays closest to the time of closest approach (TCA).
- `synthetic` is `true` only for a clearly labelled demo scenario (see the Person 1 brief, Task 2).

### `POST /api/maneuver`

Request:
```json
{"conjunction_id": "c001", "delta_v_ms": 0.05}
```
Response:
```json
{
  "conjunction_id": "c001",
  "delta_v_ms": 0.05,
  "direction": "prograde",
  "burn_lead_hours": 6,
  "new_miss_distance_km": 2.7,
  "new_pc": 3.7e-10,
  "new_risk_level": "LOW"
}
```
- The burn is applied to the **primary** satellite, `burn_lead_hours` before TCA.
- `direction` is whichever of prograde (+) or retrograde (-) gives the larger miss distance.
- Unknown id gives a 404.

### `GET /api/recommendation/{conjunction_id}`

```json
{
  "conjunction_id": "c001",
  "recommended_delta_v_ms": 0.05,
  "direction": "prograde",
  "new_miss_distance_km": 2.7,
  "new_pc": 3.7e-10,
  "new_risk_level": "LOW",
  "candidates": [
    {"delta_v_ms": 0.01, "new_miss_distance_km": 1.5, "new_pc": 8.9e-6, "new_risk_level": "MEDIUM"},
    {"delta_v_ms": 0.05, "new_miss_distance_km": 2.7, "new_pc": 3.7e-10, "new_risk_level": "LOW"}
  ]
}
```
- `recommended_delta_v_ms` is the **smallest** tested burn that brings `pc` below `1e-6`. It is `null` if none of the candidates works.

### `GET /api/ml/benchmark`

```json
{
  "hours": [1, 6, 12, 24, 48],
  "sgp4_error_km": [0.2, 0.9, 2.1, 5.0, 12.4],
  "ml_error_km": [0.1, 0.5, 1.1, 2.4, 6.0],
  "n_test_objects": 40,
  "note": "Evaluated against a simulated reference orbit, not real radar tracks."
}
```
Backend simply serves the file `ml/benchmark.json`. If the file does not exist yet, it serves the sample.

### `GET /api/report/{conjunction_id}`

```json
{
  "conjunction_id": "c001",
  "text": "COLLISION RISK ALERT (HIGH)\n..."
}
```
Text is produced by `tools/report.py` (`generate_report`).

---

## 3. Shared files and who produces them

| File | Producer | Used by |
|---|---|---|
| `data/tle_primaries.txt` | Person 4 | Person 1, Person 3 |
| `data/tle_debris.txt` | Person 4 | Person 1, Person 3 |
| `data/primaries.json` | Person 4 | Person 1 |
| `ml/benchmark.json` | Person 3 | Person 1 (served), Person 2 (chart) |
| `tools/report.py` | Person 4 | Person 1 (imports it) |
| `tools/maneuver_scan.py` | Person 4 | Person 1 (imports it) |
| `contracts/sample/*.json` | Person 1 | Person 2, Person 4 |

**TLE file format** (3 lines per object: name, line 1, line 2):
```
TERRA
1 25994U 99068A   26295.12345678  .00000123  00000-0  12345-4 0  9991
2 25994  98.2000 123.4567 0001234  90.0000 270.0000 14.57123456123456
```

**`data/primaries.json`:**
```json
[
  {"id": "25994", "name": "TERRA"},
  {"id": "27424", "name": "AQUA"}
]
```

---

## 4. How to run

From the **repo root**:

```
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```
In a second terminal, also from the repo root:
```
python -m http.server 5500
```
Then open `http://localhost:5500/frontend/`.

Backend code imports the other folders as packages from the repo root (`from tools.report import generate_report`), which is why both commands run from the root.

---

## 5. Folder ownership

| Folder / file | Owner |
|---|---|
| `backend/` | Person 1 |
| `frontend/` | Person 2 |
| `ml/` | Person 3 |
| `data/`, `tools/`, `pitch/`, `README.md` | Person 4 |
| `contracts/` | Person 1 writes it, everyone reviews |

Never edit another person's folder. Ask them.

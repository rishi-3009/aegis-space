# Aegis: Space Debris Tracking and Collision Risk (ST-01)

DRAFT. Check every number against the live dashboard before presenting.

---

## 1. The problem
- Over 35,000 tracked objects orbit Earth. One collision can create thousands of fragments.
- Operators need to know which close approaches matter in the next 24 hours, and how much fuel avoiding them costs.

## 2. What Aegis does
- 3D globe of satellites and debris, moving on real orbit data (TLEs, propagated with SGP4).
- Finds close approaches between 4 high-value satellites and about 2,600 debris objects.
- Gives a collision probability (PoC) and a HIGH / MEDIUM / LOW rating for each.
- Recommends the smallest along-track burn that brings the risk below the safe threshold.
- Writes a plain-English alert for each event.

## 3. How the risk is calculated
- Coarse screen on a 60 s grid, then 1 s refinement around each close approach.
- PoC = (R^2 / 2 sigma^2) * exp(-miss^2 / 2 sigma^2)
- Assumed: sigma = 0.5 km, hard-body radius R = 20 m. TLEs carry no uncertainty data, so these are assumptions, not measured values.
- Risk levels: HIGH if PoC >= 1e-4, MEDIUM if >= 1e-6, otherwise LOW.

## 4. Results
- Real close approaches in the next 24 h are rare and far apart: the closest real pairs in the current run miss by 9 to 19 km.
- Those real events are LOW risk.
- The HIGH event on the dashboard is a labelled DEMO / SYNTHETIC scenario. Say so out loud.

## 5. ML correction model (prototype)
- PINN-style correction model, trained and evaluated against a simulated reference orbit (J2 and drag on top of two-body motion).
- Benchmark: SGP4 error vs ML-corrected error over 1 to 48 hours, from ml/benchmark.json.
- This is not a validated full PINN, and it has not been tested against real tracking data.

## 6. Maneuver recommendation
- Along-track burns applied 6 hours before closest approach, using the Clohessy-Wiltshire equations.
- Simplified model: circular-orbit assumption, closest-approach time assumed unchanged.
- For the demo event, the recommended burn is 0.05 m/s.

## 7. Limitations (say these out loud)
- TLE accuracy is about a kilometre, so absolute PoC values are illustrative.
- PoC uses an assumed uncertainty and hard-body radius, not real covariance data.
- The ML model is a prototype evaluated against a simulated truth, not real radar tracks.
- Manoeuvres are simplified to along-track burns.
- The HIGH-risk headline event is synthetic and labelled as such everywhere.

## 8. Next steps
- Real covariance data and real space-weather inputs.
- Validation against historical conjunction events.
- A full PINN with a proper orbital dynamics residual.

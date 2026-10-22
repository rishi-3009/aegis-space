# Demo checklist

## Before the demo
- [ ] `python -m http.server 5500` running from the repo root
- [ ] `uvicorn backend.main:app --port 8000` running, and "Application startup complete" shown
- [ ] Open `http://localhost:5500/frontend/`, check the globe, table and benchmark chart load
- [ ] Click the top row: the DEMO / SYNTHETIC tag and "SYNTHETIC DEMO EVENT" line show in the alert
- [ ] Drag the burn slider and "Apply recommended burn": miss distance and risk update
- [ ] Backup demo video recorded (see the plan's timeline)

## Demo order (about 3 minutes)
1. Problem (20 s): over 35,000 tracked objects; one collision creates thousands more.
2. Globe (30 s): satellites and debris moving on real orbit data.
3. Detection (40 s): click the top event. Say it is a labelled demo scenario, because real passes this close are rare.
4. ML (40 s): benchmark chart. Say it is evaluated against a simulated reference.
5. Maneuver (40 s): drag the slider. Quote the recommended burn from the dashboard, not from memory.
6. Report (20 s): show the generated alert.
7. Close (10 s): state the limitations from slides.md.

## If something breaks
- Backend will not start: use the backup video.
- Dashboard shows "Could not reach" errors: check the backend window is still running on port 8000.
- Globe is blank: check `frontend/vendor/` contains three.module.js and OrbitControls.js.

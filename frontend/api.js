import { API_BASE, USE_SAMPLES, SAMPLE_BASE } from "./config.js";

const ENDPOINTS = {
  objects: "/api/objects",
  trajectories: "/api/trajectories",
  conjunctions: "/api/conjunctions",
  benchmark: "/api/ml/benchmark",
  report: "/api/report/",
  recommendation: "/api/recommendation/",
  maneuver: "/api/maneuver",
};

async function fetchJSON(url, options) {
  let res;
  try {
    res = await fetch(url, options);
  } catch (err) {
    if (USE_SAMPLES) {
      throw new Error(`Sample file missing: ${url}`);
    }
    throw new Error(
      `Backend not reachable at ${API_BASE}. Start it from the repo root with: ` +
        "uvicorn backend.main:app --reload --port 8000"
    );
  }
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      detail = (await res.json()).detail || detail;
    } catch (err) {
      // response had no JSON body, keep the HTTP status
    }
    throw new Error(detail);
  }
  return res.json();
}

// name: "objects", "trajectories", "conjunctions", "benchmark", "report", "recommendation"
// id: conjunction id, only needed for "report" and "recommendation"
export function getJSON(name, id = "") {
  if (USE_SAMPLES) {
    return fetchJSON(SAMPLE_BASE + name + ".json");
  }
  return fetchJSON(API_BASE + ENDPOINTS[name] + id);
}

// body: {conjunction_id, delta_v_ms}
export function postManeuver(body) {
  if (USE_SAMPLES) {
    return fetchJSON(SAMPLE_BASE + "maneuver.json");
  }
  return fetchJSON(API_BASE + ENDPOINTS.maneuver, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

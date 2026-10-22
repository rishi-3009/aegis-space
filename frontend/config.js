// true: read the sample JSON files in SAMPLE_BASE, false: call the real backend
export const USE_SAMPLES = false;
// Local runs call the backend on port 8000. On a hosted domain the API sits on the same domain.
export const API_BASE = location.hostname === "localhost" ? "http://localhost:8000" : "";
export const SAMPLE_BASE = "/contracts/sample/";

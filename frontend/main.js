import { createGlobe } from "./globe.js";
import { getJSON } from "./api.js";
import { USE_SAMPLES } from "./config.js";
import { renderConjunctionTable, renderEvent } from "./ui.js";

const statusEl = document.getElementById("status");
const playBtn = document.getElementById("play");
const scrubber = document.getElementById("scrubber");
const clockEl = document.getElementById("clock");
const speedButtons = document.querySelectorAll("[data-speed]");
const tableEl = document.getElementById("conj-table");
const eventEl = document.getElementById("event-panel");

const globe = createGlobe(document.getElementById("globe"));

// Simulation time in seconds from the start of the 24 h window
let simSec = 0;
let totalSec = 0;
let speed = 60;
let playing = true;
let loaded = false;
let setActiveRow = () => {};

function setSpeed(value) {
  speed = value;
  speedButtons.forEach((btn) => btn.classList.toggle("active", Number(btn.dataset.speed) === value));
}

function utcString(ms) {
  return new Date(ms).toISOString().replace(/\.\d{3}Z$/, "Z");
}

function selectConjunction(conj) {
  // Jump to the time of closest approach, then show the pair
  simSec = conj.tca_step * globe.stepSeconds;
  // Move the objects to the new time first, so the camera aims at where they are now
  globe.setTime(simSec / globe.stepSeconds);
  globe.focus(conj.primary.id, conj.secondary.id);
  setActiveRow(conj.id);
  renderEvent(eventEl, conj);
}

async function init() {
  statusEl.textContent = "Loading data...";
  try {
    const [objectsResp, traj, conjResp] = await Promise.all([
      getJSON("objects"),
      getJSON("trajectories"),
      getJSON("conjunctions"),
    ]);
    // Every track must have one position per step, or the animation breaks
    for (const [id, track] of Object.entries(traj.objects)) {
      if (track.length !== traj.steps) {
        throw new Error(`object ${id} has ${track.length} positions, expected ${traj.steps}`);
      }
    }
    globe.load(objectsResp, traj);
    // Read the window size from the response, never hard-code it
    totalSec = (traj.steps - 1) * traj.step_seconds;
    scrubber.max = totalSec;
    setActiveRow = renderConjunctionTable(tableEl, conjResp.conjunctions, selectConjunction);
    loaded = true;
    statusEl.textContent = USE_SAMPLES ? "DEMO DATA (sample files)" : "Live backend";
  } catch (err) {
    statusEl.textContent = "Could not load data: " + err.message;
  }
}

playBtn.addEventListener("click", () => {
  playing = !playing;
  playBtn.textContent = playing ? "Pause" : "Play";
});

speedButtons.forEach((btn) => {
  btn.addEventListener("click", () => setSpeed(Number(btn.dataset.speed)));
});

scrubber.addEventListener("input", () => {
  simSec = Number(scrubber.value);
});

window.addEventListener("resize", () => globe.resize());

let last = performance.now();
function frame(now) {
  const dt = (now - last) / 1000;
  last = now;

  if (loaded) {
    if (playing) {
      simSec += dt * speed;
      if (simSec > totalSec) simSec -= totalSec;
    }
    globe.setTime(simSec / globe.stepSeconds);
    scrubber.value = simSec;
    clockEl.textContent = utcString(globe.startMs + simSec * 1000);
  }

  globe.render();
  requestAnimationFrame(frame);
}

setSpeed(speed);
globe.resize();
init();
requestAnimationFrame(frame);

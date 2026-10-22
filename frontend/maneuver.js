import { getJSON, postManeuver } from "./api.js";
import { badge, formatPc } from "./ui.js";

// Wait this long after the last slider move before asking the backend
const DEBOUNCE_MS = 250;

// Burn slider, before/after comparison and "Apply recommended burn".
// Returns setConjunction(conj) to switch the panel to another event.
export function createManeuverPanel(container) {
  container.innerHTML = `
    <div class="burn">
      <div class="burn-head">
        <span>Maneuver burn</span>
        <strong id="dv-value">0.00 m/s</strong>
      </div>
      <input id="dv" class="burn-slider" type="range" min="0" max="1" step="0.01" value="0">
      <table class="burn-compare">
        <thead>
          <tr><th></th><th>Now</th><th>After burn</th></tr>
        </thead>
        <tbody>
          <tr><td>Miss distance</td><td id="old-miss"></td><td id="new-miss"></td></tr>
          <tr><td>PoC</td><td id="old-pc"></td><td id="new-pc"></td></tr>
          <tr><td>Risk</td><td id="old-risk"></td><td id="new-risk"></td></tr>
        </tbody>
      </table>
      <div class="burn-actions">
        <button id="apply-rec" class="btn primary">Apply recommended burn</button>
      </div>
      <p id="burn-msg" class="burn-msg"></p>
    </div>`;

  const slider = container.querySelector("#dv");
  const dvValue = container.querySelector("#dv-value");
  const msgEl = container.querySelector("#burn-msg");
  const oldMiss = container.querySelector("#old-miss");
  const oldPc = container.querySelector("#old-pc");
  const oldRisk = container.querySelector("#old-risk");
  const newMiss = container.querySelector("#new-miss");
  const newPc = container.querySelector("#new-pc");
  const newRisk = container.querySelector("#new-risk");

  let conj = null;
  let timer = null;
  // Each request gets a number, so an old answer never overwrites a newer one
  let seq = 0;

  function setDv(value) {
    slider.value = value;
    dvValue.textContent = `${Number(value).toFixed(2)} m/s`;
  }

  function setMsg(text, isError = false) {
    msgEl.textContent = text;
    msgEl.classList.toggle("error", isError);
  }

  // result is a maneuver or recommendation response; null shows the original values
  function renderCompare(result) {
    oldMiss.textContent = `${conj.miss_distance_km.toFixed(2)} km`;
    oldPc.textContent = formatPc(conj.pc);
    oldRisk.innerHTML = badge(conj.risk_level);

    if (!result) {
      newMiss.textContent = oldMiss.textContent;
      newPc.textContent = oldPc.textContent;
      newRisk.innerHTML = oldRisk.innerHTML;
      return;
    }
    newMiss.textContent = `${result.new_miss_distance_km.toFixed(2)} km`;
    newPc.textContent = formatPc(result.new_pc);
    newRisk.innerHTML = badge(result.new_risk_level);
  }

  async function calculateBurn(dv) {
    const mine = ++seq;
    setMsg("Calculating...");
    try {
      const res = await postManeuver({ conjunction_id: conj.id, delta_v_ms: dv });
      if (mine !== seq) return;
      renderCompare(res);
      // Shows the burn the backend actually calculated, which can differ from the slider
      setMsg(`${res.delta_v_ms.toFixed(2)} m/s ${res.direction}, ${res.burn_lead_hours} h before TCA`);
    } catch (err) {
      if (mine === seq) setMsg("Could not calculate burn: " + err.message, true);
    }
  }

  slider.addEventListener("input", () => {
    setDv(slider.value);
    clearTimeout(timer);
    timer = setTimeout(() => {
      if (!conj) return;
      const dv = Number(slider.value);
      if (dv === 0) {
        seq++;
        renderCompare(null);
        setMsg("");
      } else {
        calculateBurn(dv);
      }
    }, DEBOUNCE_MS);
  });

  container.querySelector("#apply-rec").addEventListener("click", async () => {
    if (!conj) return;
    const mine = ++seq;
    clearTimeout(timer);
    setMsg("Looking up recommended burn...");
    try {
      const rec = await getJSON("recommendation", conj.id);
      if (mine !== seq) return;
      if (rec.recommended_delta_v_ms === null) {
        setDv(0);
        renderCompare(null);
        setMsg("No tested burn is safe.", true);
        return;
      }
      setDv(rec.recommended_delta_v_ms);
      renderCompare(rec);
      setMsg(`Recommended: ${rec.recommended_delta_v_ms.toFixed(2)} m/s ${rec.direction}`);
    } catch (err) {
      if (mine === seq) setMsg("Could not load recommendation: " + err.message, true);
    }
  });

  return {
    setConjunction(next) {
      conj = next;
      clearTimeout(timer);
      seq++;
      setDv(0);
      renderCompare(null);
      setMsg("");
    },
  };
}

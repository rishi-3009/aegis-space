// Escape text from the API before putting it into HTML
function esc(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function badge(level) {
  return `<span class="badge ${esc(level)}">${esc(level)}</span>`;
}

function demoTag(conj) {
  return conj.synthetic ? ' <span class="tag">DEMO / SYNTHETIC</span>' : "";
}

export function formatPc(pc) {
  return pc.toExponential(1);
}

function formatTca(tca) {
  return tca.replace("T", " ").replace("Z", "");
}

// Builds the conjunction table, sorted by PoC (highest first).
// onSelect(conj) runs when a row is clicked. Returns setActive(id) to highlight a row.
export function renderConjunctionTable(container, conjunctions, onSelect) {
  const sorted = [...conjunctions].sort((a, b) => b.pc - a.pc);

  const rows = sorted
    .map(
      (c) => `
      <tr data-id="${esc(c.id)}">
        <td>${esc(c.primary.name)}</td>
        <td>${esc(c.secondary.name)}${demoTag(c)}</td>
        <td>${esc(formatTca(c.tca))}</td>
        <td class="num">${c.miss_distance_km.toFixed(2)}</td>
        <td class="num">${formatPc(c.pc)}</td>
        <td>${badge(c.risk_level)}</td>
      </tr>`
    )
    .join("");

  container.innerHTML = `
    <table class="conj-table">
      <thead>
        <tr>
          <th>Primary</th>
          <th>Secondary</th>
          <th>TCA (UTC)</th>
          <th class="num">Miss (km)</th>
          <th class="num">PoC</th>
          <th>Risk</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;

  const byId = new Map(sorted.map((c) => [c.id, c]));
  const rowEls = container.querySelectorAll("tbody tr");

  rowEls.forEach((row) => {
    row.addEventListener("click", () => onSelect(byId.get(row.dataset.id)));
  });

  return function setActive(id) {
    rowEls.forEach((row) => row.classList.toggle("active", row.dataset.id === id));
  };
}

// Shows the details of one conjunction in the event panel
export function renderEvent(container, conj) {
  container.innerHTML = `
    <div class="event-title">
      ${esc(conj.primary.name)} vs ${esc(conj.secondary.name)} ${badge(conj.risk_level)}${demoTag(conj)}
    </div>
    <dl class="event-grid">
      <dt>TCA (UTC)</dt><dd>${esc(formatTca(conj.tca))}</dd>
      <dt>Miss distance</dt><dd>${conj.miss_distance_km.toFixed(2)} km</dd>
      <dt>Relative speed</dt><dd>${conj.relative_speed_kms.toFixed(1)} km/s</dd>
      <dt>PoC</dt><dd>${formatPc(conj.pc)}</dd>
    </dl>`;
}

// Copies the alert text to the clipboard and confirms on the button
export function setupCopy(button, textEl) {
  const label = button.textContent;
  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(textEl.textContent);
      button.textContent = "Copied";
    } catch (err) {
      button.textContent = "Copy failed";
    }
    setTimeout(() => (button.textContent = label), 1500);
  });
}

// Chart.js is loaded as a global by vendor/chart.umd.min.js
const TEXT = "#cfe0f5";
const GRID = "#1d2d48";

// Builds the SGP4 vs ML error chart. show(bench) draws it from /api/ml/benchmark.
export function createBenchmarkChart(canvas, noteEl) {
  let chart = null;

  return {
    show(bench) {
      const data = {
        labels: bench.hours.map((h) => `${h} h`),
        datasets: [
          {
            label: "SGP4",
            data: bench.sgp4_error_km,
            borderColor: "#ff8a5b",
            backgroundColor: "#ff8a5b",
            tension: 0.2,
          },
          {
            label: "ML-corrected",
            data: bench.ml_error_km,
            borderColor: "#33e0ff",
            backgroundColor: "#33e0ff",
            tension: 0.2,
          },
        ],
      };

      const options = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: TEXT, font: { size: 14 } } } },
        scales: {
          x: {
            title: { display: true, text: "hours ahead", color: TEXT },
            ticks: { color: TEXT },
            grid: { color: GRID },
          },
          y: {
            title: { display: true, text: "position error (km)", color: TEXT },
            ticks: { color: TEXT },
            grid: { color: GRID },
          },
        },
      };

      if (chart) chart.destroy();
      chart = new Chart(canvas, { type: "line", data, options });
      noteEl.textContent = bench.note;
    },

    fail(message) {
      noteEl.textContent = message;
    },
  };
}

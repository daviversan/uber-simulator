// Painel Analytics: números calculados no Postgres (com cache de 5 s no servidor).
import { api, startPolling } from "./api.js";

const POLL_MS = 5000; // igual ao TTL do cache: pedir mais rápido só bateria no cache

export function setupAnalyticsPanel() {
  let chart = null;

  async function refreshSummary() {
    const data = await api.getAnalyticsSummary();
    document.getElementById("analytics-active").textContent = data.active_drivers;
  }

  async function refreshByCity() {
    const rows = await api.getAnalyticsByCity();
    document.querySelector("#analytics-by-city tbody").innerHTML = rows
      .map((row) => `<tr><td>${row.city_name}</td><td>${row.driver_count}</td></tr>`)
      .join("");
  }

  async function refreshChart() {
    const points = await api.getAnalyticsTimeseries("points", "30s");
    const labels = points.map((p) => new Date(p.timestamp).toLocaleTimeString());
    const values = points.map((p) => p.value);

    if (chart) {
      chart.data.labels = labels;
      chart.data.datasets[0].data = values;
      chart.update();
      return;
    }
    chart = new Chart(document.getElementById("analytics-chart"), {
      type: "line",
      data: {
        labels,
        datasets: [{
          label: "posições / 30s",
          data: values,
          borderColor: "#4da3ff",
          backgroundColor: "rgba(77, 163, 255, 0.15)",
          tension: 0.25,
          fill: true,
        }],
      },
      options: {
        animation: false,
        scales: { y: { beginAtZero: true } },
        plugins: { legend: { display: false } },
      },
    });
  }

  startPolling(() => Promise.all([refreshSummary(), refreshByCity(), refreshChart()]), POLL_MS);
}

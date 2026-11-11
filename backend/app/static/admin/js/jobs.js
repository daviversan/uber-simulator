// Painel Jobs: lista os jobs com a última execução e permite rodar na hora.
import { api, startPolling } from "./api.js";

function formatLastRun(run) {
  if (!run) return "nunca executado";
  const mark = run.status === "success" ? "✓" : "✗";
  return `${mark} ${new Date(run.started_at).toLocaleString()} — ${run.detail ?? ""}`;
}

export function setupJobsPanel() {
  const listEl = document.getElementById("jobs-list");

  async function refresh() {
    const jobs = await api.getJobs();
    listEl.innerHTML = "";
    for (const job of jobs) {
      const row = document.createElement("div");
      row.className = "job-row";
      row.innerHTML = `
        <div class="job-info">
          <strong>${job.name}</strong>
          <span class="placeholder">${job.description}</span>
          <span class="job-last-run">${formatLastRun(job.last_run)}</span>
        </div>
        <button>Run now</button>`;
      const button = row.querySelector("button");
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          await api.runJob(job.name);
          await refresh();
        } catch (err) {
          console.warn("job falhou:", err.message);
          button.disabled = false;
        }
      });
      listEl.appendChild(row);
    }
  }

  startPolling(refresh, 3000);
}

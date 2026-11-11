// Painel Simulação: cada controle vira um comando enviado ao simulador. O
// efeito é confirmado lendo o estado do simulador (polling), não pela
// resposta do comando.
import { api, startPolling } from "./api.js";

const $ = (id) => document.getElementById(id);

function onSubmit(formId, handler) {
  $(formId).addEventListener("submit", (event) => {
    event.preventDefault();
    handler();
  });
}

export function setupSimPanel() {
  const citySelect = $("sim-spawn-city");
  api
    .getCities()
    .then((cities) => cities.forEach((c) => citySelect.add(new Option(c.name, c.city_id))))
    .catch((err) => console.warn("cidades indisponíveis:", err.message));

  $("sim-start").addEventListener("click", () => api.sendCommand({ type: "start" }));
  $("sim-pause").addEventListener("click", () => api.sendCommand({ type: "pause" }));
  $("sim-reset").addEventListener("click", () => api.sendCommand({ type: "reset" }));

  onSubmit("sim-spawn-form", () =>
    api.sendCommand({ type: "spawn", city: citySelect.value, count: Number($("sim-spawn-count").value) }),
  );

  onSubmit("sim-despawn-form", () => {
    const driverId = $("sim-despawn-id").value.trim();
    if (!driverId) return;
    api.sendCommand({ type: "despawn", driver_id: driverId });
    $("sim-despawn-id").value = "";
  });

  $("sim-rate").addEventListener("change", (event) => {
    const multiplier = Number(event.target.value);
    $("sim-rate-value").textContent = `${multiplier.toFixed(1)}x`;
    api.sendCommand({ type: "set_rate", multiplier });
  });

  startPolling(async () => {
    const state = await api.getSimulationState();
    $("sim-state-status").textContent = state.status ?? "—";
    $("sim-state-count").textContent = state.driver_count ?? "—";
    $("sim-state-rate").textContent = state.rate_multiplier ? `${state.rate_multiplier}x` : "—";
  }, 2000);
}

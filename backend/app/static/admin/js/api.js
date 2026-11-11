// A conexão única do admin com o servidor. Tudo passa por este socket: o
// stream da frota (main.js) e os pedidos/respostas dos painéis (`api`).
import { connect } from "../../shared/connection.js";

const conn = connect(document.getElementById("status-instance"));
export const socket = conn.socket;
const rpc = conn.rpc;

// O admin entra uma vez; todo pedido espera esta Promise. Como o servidor
// processa as mensagens de um socket em ordem, um pedido enviado depois do
// join já encontra o join concluído.
export const ready = socket.connected().then(() => socket.send({ type: "join", role: "admin" }));

async function call(op, payload) {
  await ready;
  return rpc.request(op, payload);
}

export const api = {
  getCities: () => call("cities.list"),
  getDriverHistory: (driverId) => call("drivers.history", { driver_id: driverId }),

  getSimulationState: () => call("simulation.state"),
  // A resposta é "aceito", não "executado": o efeito aparece em getSimulationState().
  sendCommand: (cmd) =>
    call("simulation.command", cmd).catch((err) => console.warn("comando recusado:", err.message)),

  getAnalyticsSummary: () => call("analytics.summary"),
  getAnalyticsByCity: () => call("analytics.by_city"),
  getAnalyticsTimeseries: (metric, bucket) => call("analytics.timeseries", { metric, bucket }),

  getJobs: () => call("jobs.list"),
  runJob: (name) => call("jobs.run", { name }),
};

// Executa `fn` agora e a cada `intervalMs`. Uma falha só é registrada: o
// próximo ciclo tenta de novo.
export function startPolling(fn, intervalMs) {
  const run = () => fn().catch((err) => console.warn("polling falhou:", err.message));
  run();
  setInterval(run, intervalMs);
}

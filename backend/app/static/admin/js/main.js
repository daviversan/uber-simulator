// Tela do admin: mapa da frota em tempo real + painéis (Simulação, Analytics, Jobs).
import { api, ready, socket } from "./api.js";
import { setupAnalyticsPanel } from "./analytics.js";
import { createFleet } from "./fleet.js";
import { setupJobsPanel } from "./jobs.js";
import { createMap } from "./map.js";
import { setupSimPanel } from "./sim.js";

const statusDrivers = document.getElementById("status-drivers");

function setupTabs() {
  const buttons = document.querySelectorAll(".tab-btn");
  for (const btn of buttons) {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  }
}

async function startFleet(fleet, map) {
  const updateCount = () => (statusDrivers.textContent = `${fleet.size()} motoristas`);

  // As mensagens só atualizam o estado (fleet). Quem desenha é o render loop
  // abaixo, no ritmo da tela: chegar 1.000 mensagens por segundo não gera
  // 1.000 redesenhos.
  socket.onMessage((msg) => {
    switch (msg.type) {
      case "snapshot": // estado inicial; vem logo após o join, antes dos eventos
        fleet.load(msg.drivers);
        updateCount();
        break;
      case "position":
        fleet.apply(msg);
        map.appendTrail(msg.driver_id, msg.latitude, msg.longitude);
        updateCount();
        break;
      case "driver_removed":
        fleet.remove(msg.driver_id);
        updateCount();
        break;
      case "error":
        console.warn("erro do servidor:", msg.code, msg.message);
        break;
    }
  });
  await ready;

  // Informa ao servidor a área visível; ele só envia posições dentro dela.
  // Reenviado a cada movimento/zoom do mapa.
  const sendViewport = () => socket.send({ type: "subscribe", bbox: map.leaflet.getBounds().toBBoxString() });
  map.leaflet.on("moveend", sendViewport);
  sendViewport();

  // Clique num motorista: mostra a trilha. As posições ao vivo já começam a
  // estendê-la; o histórico do banco entra à frente quando chegar.
  map.onMarkerClick(async (driverId) => {
    map.startTrail(driverId);
    try {
      map.prependTrail(driverId, await api.getDriverHistory(driverId));
    } catch (err) {
      console.warn("histórico indisponível:", err.message);
    }
  });

  // Render loop: redesenha a cada frame da tela (~60 fps).
  const frame = () => {
    map.render(fleet.all());
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}

setupTabs();
setupSimPanel();
setupAnalyticsPanel();
setupJobsPanel();
startFleet(createFleet(), createMap());

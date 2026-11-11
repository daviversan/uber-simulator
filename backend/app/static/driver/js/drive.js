// Tela de direção: mapa centrado no motorista, movimento manual ou automático e
// envio da posição.
//
// O app é a FONTE da própria posição: o marcador se move na hora e a posição é
// enviada em seguida (publisher.js), sem esperar confirmação do servidor. É o
// oposto do admin, que só espelha o que o servidor manda.
import { createBaseMap } from "../../shared/basemap.js";
import { metersPerPixel, moveByMeters } from "../../shared/geo.js";
import { createAutoDrive } from "./autodrive.js";
import { createKeyboardControls } from "./controls.js";
import { createPublisher } from "./publisher.js";
import { saveLastPosition } from "./session.js";

const TICK_MS = 50; // passo do laço de movimento (20 Hz)
const KEY_SPEED_PX_PER_S = 80; // velocidade do teclado, medida em PIXELS de tela
const SEND_EVERY_MS = 1000;

// `config` vem do servidor no `joined`: { min_move_m, heartbeat_ms }.
export function startDriving({ socket, driverId, start, instance, config }) {
  document.getElementById("join-screen").hidden = true;
  // O mapa só pode ser criado com o contêiner VISÍVEL: o Leaflet mede o tamanho
  // do elemento na criação, e um elemento `hidden` tem tamanho zero.
  document.getElementById("drive-screen").hidden = false;

  const map = createBaseMap("map", {
    center: [start.lat, start.lon],
    zoom: 16,
    keyboard: false, // as setas são do motorista, não para o Leaflet mover o mapa
  });

  const marker = L.marker([start.lat, start.lon], {
    draggable: true,
    icon: L.divIcon({ className: "me-marker", html: "<span></span>", iconSize: [22, 22] }),
  }).addTo(map);

  const coordsEl = document.getElementById("hud-coords");
  const modeBtn = document.getElementById("mode-toggle");
  const helpEl = document.getElementById("hud-help");
  document.getElementById("hud-id").textContent = driverId;
  document.getElementById("hud-instance").textContent = instance ? `via ${instance}` : "";

  const publisher = createPublisher(
    (msg) => {
      if (!socket.isOpen()) return; // o status "desconectado" já avisa o usuário
      socket.send({ type: "position", ...msg });
      saveLastPosition(msg);
    },
    { minIntervalMs: SEND_EVERY_MS, minMoveM: config.min_move_m, heartbeatMs: config.heartbeat_ms },
  );
  publisher.seed(start); // o join já registrou o ponto de partida

  let pos = { lat: start.lat, lon: start.lon };
  let mode = "manual";
  const auto = createAutoDrive();
  const keys = createKeyboardControls();

  // Único ponto por onde a posição muda. Teclado, arrasto e rota automática
  // passam todos por aqui — e é aqui que mora "o que acontece quando o motorista
  // se move" (desenhar, mostrar, publicar), em um lugar só.
  function setPosition(next, { fromDrag = false } = {}) {
    pos = next;
    if (!fromDrag) marker.setLatLng([pos.lat, pos.lon]); // durante o arrasto o Leaflet já move o marcador
    coordsEl.textContent = `${pos.lat.toFixed(5)}, ${pos.lon.toFixed(5)}`;
    publisher.update(pos);
    if (!map.getBounds().contains([pos.lat, pos.lon])) map.panTo([pos.lat, pos.lon]);
  }

  marker.on("drag", (e) => {
    const ll = map.wrapLatLng(e.latlng); // dar a volta no mundo pode passar de ±180
    setPosition({ lat: ll.lat, lon: ll.lng }, { fromDrag: true });
  });

  function setMode(next) {
    mode = next;
    if (mode === "auto") {
      auto.reset();
      marker.dragging.disable(); // arrastar no auto brigaria com o piloto automático
      modeBtn.textContent = "Modo: Auto — clique para assumir";
      helpEl.textContent = "O motorista anda sozinho e faz paradas.";
    } else {
      marker.dragging.enable();
      modeBtn.textContent = "Modo: Manual — clique para o piloto automático";
      helpEl.textContent = "Setas ou WASD para andar; ou arraste o marcador.";
    }
  }
  modeBtn.addEventListener("click", () => setMode(mode === "manual" ? "auto" : "manual"));
  setMode("manual");
  // Só preenche o HUD: o `join` já registrou esta posição no servidor, mandar de
  // novo seria uma linha duplicada em `positions`.
  coordsEl.textContent = `${pos.lat.toFixed(5)}, ${pos.lon.toFixed(5)}`;

  // Laço de movimento com RELÓGIO (delta time): a distância andada depende do
  // tempo que passou de verdade, não de quantas vezes o laço rodou. Por isso o
  // motorista anda na mesma velocidade mesmo se o navegador atrasar um passo.
  // setInterval e não requestAnimationFrame: a aba em segundo plano pausa o
  // rAF por completo, e um motorista "congela" ao trocar de aba; o setInterval
  // continua (mais devagar, ~1 Hz) e o delta time compensa o tempo perdido.
  let last = performance.now();
  setInterval(() => {
    const now = performance.now();
    const dt = (now - last) / 1000;
    last = now;

    if (mode === "auto") {
      const next = auto.step(pos, dt);
      if (next !== pos) setPosition(next);
      return;
    }
    const v = keys.velocity();
    if (v.north === 0 && v.east === 0) return;
    const meters = KEY_SPEED_PX_PER_S * metersPerPixel(pos.lat, map.getZoom()) * dt;
    setPosition(moveByMeters(pos, v.north * meters, v.east * meters));
  }, TICK_MS);
}

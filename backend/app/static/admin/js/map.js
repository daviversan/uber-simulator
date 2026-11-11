// Mapa do admin (Leaflet): um marcador por motorista e a trilha do selecionado.
//
// - Canvas: todos os marcadores são desenhados num único <canvas>, em vez de
//   um elemento HTML por marcador. Aguenta milhares de motoristas.
// - Interpolação: as posições chegam a cada ~1 s. A cada frame, o marcador é
//   desenhado no ponto intermediário entre a posição anterior e a atual, então
//   ele desliza em vez de pular.
import { createBaseMap } from "../../shared/basemap.js";

const TICK_MS = 1000; // intervalo típico entre duas posições

// `source` vem do servidor: "app" = motorista humano (laranja, maior); "sim" = bot (azul).
const STYLES = {
  app: { radius: 8, color: "#ff8a00", weight: 3, fillColor: "#ffb347", fillOpacity: 0.9 },
  sim: { radius: 5 },
};

function interpolate(entry, now) {
  const t = Math.min((now - entry.updatedAt) / TICK_MS, 1);
  const { prev, curr } = entry;
  return [
    prev.latitude + (curr.latitude - prev.latitude) * t,
    prev.longitude + (curr.longitude - prev.longitude) * t,
  ];
}

export function createMap() {
  const map = createBaseMap("map", { center: [20, 0], zoom: 2, preferCanvas: true });
  const markers = new Map(); // driver_id -> L.CircleMarker
  let onMarkerClick = () => {};
  let trail = null; // { driverId, latlngs, layer }: só uma trilha por vez

  function clearTrail() {
    if (trail) map.removeLayer(trail.layer);
    trail = null;
  }

  return {
    leaflet: map,

    // Sincroniza os marcadores com a frota: remove os que saíram, move os que
    // existem e cria os novos.
    render(drivers) {
      const now = performance.now();
      for (const [driverId, marker] of markers) {
        if (drivers.has(driverId)) continue;
        map.removeLayer(marker);
        markers.delete(driverId);
        if (trail?.driverId === driverId) clearTrail();
      }
      for (const [driverId, entry] of drivers) {
        const latlng = interpolate(entry, now);
        const marker = markers.get(driverId);
        if (marker) {
          marker.setLatLng(latlng);
          continue;
        }
        const isApp = entry.curr.source === "app";
        const created = L.circleMarker(latlng, isApp ? STYLES.app : STYLES.sim).addTo(map);
        created.bindTooltip(isApp ? `${driverId} (app)` : driverId);
        created.on("click", () => onMarkerClick(driverId));
        markers.set(driverId, created);
      }
    },

    onMarkerClick(fn) {
      onMarkerClick = fn;
    },

    // Começa uma trilha vazia para o motorista (substitui a anterior).
    startTrail(driverId) {
      clearTrail();
      const layer = L.polyline([], { color: "#4da3ff", weight: 3, opacity: 0.8 }).addTo(map);
      trail = { driverId, latlngs: [], layer };
    },

    // Posição ao vivo: estende a trilha, se for do motorista selecionado.
    appendTrail(driverId, latitude, longitude) {
      if (trail?.driverId !== driverId) return;
      trail.latlngs.push([latitude, longitude]);
      trail.layer.setLatLngs(trail.latlngs);
    },

    // Histórico do banco: entra ANTES dos pontos ao vivo. Se o usuário já
    // clicou em outro motorista, a resposta antiga é ignorada.
    prependTrail(driverId, points) {
      if (trail?.driverId !== driverId || !points.length) return;
      trail.latlngs = [...points.map((p) => [p.latitude, p.longitude]), ...trail.latlngs];
      trail.layer.setLatLngs(trail.latlngs);
      map.fitBounds(trail.layer.getBounds(), { maxZoom: 14 });
    },
  };
}

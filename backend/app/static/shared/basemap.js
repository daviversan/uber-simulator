// Mapa-base usado pelas duas telas: um Leaflet com os tiles do OpenStreetMap.
// `L` é o global do Leaflet (carregado por <script> no HTML de cada app).
export function createBaseMap(elementId, { center, zoom, ...leafletOptions }) {
  const map = L.map(elementId, leafletOptions).setView(center, zoom);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 19,
  }).addTo(map);
  return map;
}

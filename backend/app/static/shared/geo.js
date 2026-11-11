// Matemática geográfica pura (sem DOM, sem rede): dá para testar em Node.
// Posição = { lat, lon } em graus decimais.

const EARTH_RADIUS_M = 6371008.8; // raio MÉDIO: o certo para distâncias (haversine)
// O Web Mercator (os tiles do mapa) é definido sobre outra esfera, a do eixo
// equatorial do WGS84. Misturar os dois raios dá um erro de ~0,1% — pequeno, mas
// é erro: cada conversão usa o raio da referência a que pertence.
const WEB_MERCATOR_RADIUS_M = 6378137;
const toRad = (deg) => (deg * Math.PI) / 180;
const toDeg = (rad) => (rad * 180) / Math.PI;

// Distância em metros sobre a superfície da esfera (fórmula de haversine).
export function haversineMeters(a, b) {
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)));
}

// Filtro de movimento: vale enviar esta posição? Sim se saiu do lugar
// (>= minMoveM do ÚLTIMO ENVIADO — não do último lido, senão uma deriva lenta de
// 1 m por vez nunca passaria do limiar) ou se o heartbeat venceu (prova de vida).
// Pura: o tempo entra como parâmetro, então testa-se sem relógio.
export function shouldSend(lastSent, pos, nowMs, { minMoveM, heartbeatMs }) {
  if (!lastSent) return true;
  if (haversineMeters(lastSent.pos, pos) >= minMoveM) return true;
  return nowMs - lastSent.at >= heartbeatMs;
}

// Normaliza longitude para [-180, 180): andar para leste a partir de 179.9 dá
// -179.9, não 180.1 (que o servidor rejeitaria, o limite é ±180).
function wrapLon(lon) {
  return ((((lon + 180) % 360) + 360) % 360) - 180;
}

// Desloca uma posição por (norte, leste) em metros. Aproximação de terra plana
// local: boa para passos de metros a poucos km, que é o único uso aqui. Um grau
// de longitude encolhe com cos(lat), por isso a divisão.
export function moveByMeters(pos, northM, eastM) {
  const cosLat = Math.max(Math.cos(toRad(pos.lat)), 1e-6); // evita divisão por ~0 nos polos
  const lat = pos.lat + toDeg(northM / EARTH_RADIUS_M);
  const lon = pos.lon + toDeg(eastM / (EARTH_RADIUS_M * cosLat));
  return { lat: Math.max(-90, Math.min(90, lat)), lon: wrapLon(lon) };
}

// Anda `meters` em linha reta rumo a `target`. Devolve { pos, arrived }: se o
// passo é maior que a distância que falta, pousa EXATAMENTE no alvo em vez de
// passar direto e ficar oscilando em volta dele.
export function moveToward(pos, target, meters) {
  const dist = haversineMeters(pos, target);
  if (dist <= meters) return { pos: { ...target }, arrived: true };
  const f = meters / dist;
  const dLon = wrapLon(target.lon - pos.lon); // menor caminho, mesmo cruzando ±180
  return {
    pos: { lat: pos.lat + (target.lat - pos.lat) * f, lon: wrapLon(pos.lon + dLon * f) },
    arrived: false,
  };
}

// Metros que um pixel de tela representa no zoom (Web Mercator, tiles de 256px)
// na latitude dada. É o que torna o passo do teclado "proporcional ao zoom": com
// o mapa aberto, 1 passo cobre mais chão; com zoom de rua, menos.
export function metersPerPixel(lat, zoom) {
  return (2 * Math.PI * WEB_MERCATOR_RADIUS_M * Math.cos(toRad(lat))) / (256 * 2 ** zoom);
}

// Decide QUANDO enviar a posição do motorista. Duas regras independentes:
//
//  A. LIMITE DE TAXA (throttle com borda final), `minIntervalMs`:
//     1. no máximo 1 envio por janela;
//     2. dentro da janela só a MAIS RECENTE importa (coalescência);
//     3. a última nunca se perde: fica agendada para o fim da janela.
//
//  B. FILTRO DE MOVIMENTO + HEARTBEAT, `minMoveM` / `heartbeatMs`:
//     decide SE vale enviar. Parado (ou balançando abaixo de minMoveM) não envia;
//     mas a cada `heartbeatMs` reenvia a posição ATUAL como prova de vida — sem
//     isso o job cleanup_stale_drivers removeria do mapa quem está parado no sinal.
//
// A responde "com que frequência"; B, "se vale a pena".
import { shouldSend } from "../../shared/geo.js";

export function createPublisher(
  send,
  { minIntervalMs = 1000, minMoveM = 0, heartbeatMs = Infinity, clock = () => performance.now() } = {},
) {
  const rule = { minMoveM, heartbeatMs };
  let lastSent = null; // { pos, at } — a referência do filtro
  let timer = null;
  let beat = null;
  let latest = null; // posição mais recente ainda não decidida
  let current = null; // posição atual do motorista (o heartbeat reenvia ESTA)

  function emit(pos) {
    lastSent = { pos, at: clock() };
    latest = null;
    // `ts` = quando a leitura foi enviada; é o que o servidor grava como
    // timestamp e o job de limpeza compara com o relógio.
    send({ lat: pos.lat, lon: pos.lon, ts: new Date().toISOString() });
    armHeartbeat();
  }

  // Um único timer de heartbeat, sempre reagendado a partir do último envio:
  // se o motorista se mexe, o heartbeat é adiado; se para, ele dispara.
  function armHeartbeat() {
    clearTimeout(beat);
    if (!Number.isFinite(heartbeatMs)) return;
    beat = setTimeout(() => {
      if (current) emit(current);
    }, heartbeatMs);
  }

  function flush() {
    timer = null;
    if (!latest) return;
    if (shouldSend(lastSent, latest, clock(), rule)) emit(latest);
    else latest = null; // dentro da zona morta: descarta, o heartbeat cobre
  }

  return {
    update(pos) {
      current = { lat: pos.lat, lon: pos.lon };
      latest = current;
      if (timer !== null) return; // já há envio agendado; ele levará `latest`
      const wait = (lastSent?.at ?? -Infinity) + minIntervalMs - clock();
      if (wait <= 0) flush();
      else timer = setTimeout(flush, wait);
    },

    // Marca a posição inicial como já enviada (o `join` a registrou): inicia o
    // filtro e o heartbeat sem mandar uma linha duplicada.
    seed(pos) {
      current = { lat: pos.lat, lon: pos.lon };
      lastSent = { pos: current, at: clock() };
      armHeartbeat();
    },
  };
}

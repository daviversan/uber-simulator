// Modo "Auto": o motorista anda sozinho. Modelo "random waypoint": escolhe um
// ponto aleatório a algumas centenas de metros, vai até lá em linha reta, para
// um instante, escolhe outro.
//
// Por que NÃO seguir uma rota fixa do catálogo de cidades (como o simulador
// faz): o usuário digita qualquer coordenada na entrada. Uma rota fixa
// teletransportaria o motorista do ponto escolhido para a rota da cidade. Aqui
// a caminhada nasce da posição ATUAL, em qualquer lugar do planeta.
//
// As paradas são de propósito: dão um motorista que fica parado de verdade, o
// caso que o filtro de movimento mínimo precisa para ser testado.
//
// `rng` é injetado (default Math.random) pelo mesmo motivo de `geo.js` ser puro:
// dá para testar com um gerador previsível, sem depender de sorte.
import { moveByMeters, moveToward } from "../../shared/geo.js";

export function createAutoDrive({
  rng = Math.random,
  speedMps = 10, // ~36 km/h
  legMeters = [300, 1200],
  pauseSeconds = [2, 6],
} = {}) {
  let target = null;
  let pauseLeft = 0;

  const between = ([lo, hi]) => lo + rng() * (hi - lo);

  function pickTarget(from) {
    const bearing = rng() * 2 * Math.PI;
    const dist = between(legMeters);
    return moveByMeters(from, dist * Math.cos(bearing), dist * Math.sin(bearing));
  }

  return {
    // Avança `dtSeconds` e devolve a nova posição. Parado, devolve o MESMO objeto
    // recebido: quem chama detecta "não mudou" com `next !== pos`, sem comparar
    // coordenada por coordenada.
    step(pos, dtSeconds) {
      if (pauseLeft > 0) {
        pauseLeft -= dtSeconds;
        return pos;
      }
      if (!target) target = pickTarget(pos);
      const { pos: next, arrived } = moveToward(pos, target, speedMps * dtSeconds);
      if (arrived) {
        target = null;
        pauseLeft = between(pauseSeconds);
      }
      return next;
    },

    // Ao voltar do manual para o auto: descarta o alvo antigo, que pode estar
    // longe de onde o usuário deixou o marcador.
    reset() {
      target = null;
      pauseLeft = 0;
    },
  };
}

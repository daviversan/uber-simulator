// Entrada de teclado como ESTADO, não como evento.
//
// O jeito ingênuo é mover o motorista dentro do `keydown`. Dá dois problemas: o
// auto-repeat do sistema operacional tem um atraso inicial (~500ms parado antes
// de repetir) e uma taxa que varia entre máquinas, então o movimento fica
// engasgado e depende do teclado de cada pessoa; e duas teclas ao mesmo tempo
// (diagonal) não combinam bem.
//
// Aqui o teclado só diz QUAIS teclas estão pressionadas agora. Quem move é um
// laço com relógio (ver drive.js), que lê `velocity()` a cada passo.
const DIRECTIONS = {
  ArrowUp: [1, 0], KeyW: [1, 0],
  ArrowDown: [-1, 0], KeyS: [-1, 0],
  ArrowRight: [0, 1], KeyD: [0, 1],
  ArrowLeft: [0, -1], KeyA: [0, -1],
};

export function createKeyboardControls(target = window) {
  const pressed = new Set();

  // `event.code` é a tecla física (KeyW), não o caractere: WASD continua nas
  // mesmas posições em teclado AZERTY ou outros layouts.
  const onKeyDown = (e) => {
    if (!(e.code in DIRECTIONS)) return;
    // Não rouba as setas de quem está digitando em um campo.
    if (e.target.matches?.("input, textarea, select")) return;
    e.preventDefault(); // evita rolar a página
    pressed.add(e.code);
  };
  const onKeyUp = (e) => pressed.delete(e.code);
  // Sem isto, soltar a tecla DEPOIS de trocar de janela nunca dispara `keyup`
  // para nós, e o motorista ficaria andando sozinho ("tecla presa").
  const onBlur = () => pressed.clear();

  target.addEventListener("keydown", onKeyDown);
  target.addEventListener("keyup", onKeyUp);
  window.addEventListener("blur", onBlur);

  return {
    // Vetor de direção com comprimento <= 1: na diagonal normaliza, para andar
    // em diagonal não ser ~41% mais rápido que em linha reta.
    velocity() {
      let north = 0;
      let east = 0;
      for (const code of pressed) {
        north += DIRECTIONS[code][0];
        east += DIRECTIONS[code][1];
      }
      const len = Math.hypot(north, east);
      return len > 1 ? { north: north / len, east: east / len } : { north, east };
    },
  };
}

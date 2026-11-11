// Conexão com o servidor, igual nas duas telas: abre o WebSocket, cria o rpc
// e mostra em `statusEl` a instância que atendeu (ou que a conexão caiu).
import { createRpc } from "./rpc.js";
import { WebSocketClient } from "./socket.js";

export function connect(statusEl) {
  const socket = new WebSocketClient("/ws");
  const conn = { socket, rpc: createRpc(socket), instance: "" };

  socket.onMessage((msg) => {
    if (msg.type !== "handshake") return;
    conn.instance = msg.instance;
    statusEl.textContent = `● conectado a ${msg.instance}`;
  });
  socket.onClose(() => (statusEl.textContent = "● desconectado — recarregue a página"));

  return conn;
}

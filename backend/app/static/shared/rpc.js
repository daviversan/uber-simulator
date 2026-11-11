// Pedido/resposta sobre o WebSocket. Sem HTTP não existe "a resposta" de uma
// chamada: o cliente manda { type: "request", id, op, payload } e o servidor
// responde com { type: "response", id, ok, data | error }. Aqui o `id` é o que
// casa uma coisa com a outra e transforma isso numa Promise.
//
// Recebe qualquer objeto com send(msg), onMessage(handler) e onClose(handler) —
// o WebSocketClient de socket.js, ou um fake nos testes.

export class RpcError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "RpcError";
    this.code = code;
  }
}

export function createRpc(socket, { timeoutMs = 10000 } = {}) {
  const pending = new Map(); // id -> { resolve, reject, timer }
  let nextId = 1;

  function settle(id) {
    const entry = pending.get(id);
    if (entry) {
      clearTimeout(entry.timer);
      pending.delete(id);
    }
    return entry;
  }

  socket.onMessage((msg) => {
    if (msg.type !== "response") return;
    // Sem entry = o pedido já estourou o timeout (ou o id é de outro cliente):
    // descartar em silêncio é o certo, a Promise já foi rejeitada.
    const entry = settle(msg.id);
    if (!entry) return;
    if (msg.ok) entry.resolve(msg.data);
    else entry.reject(new RpcError(msg.error.code, msg.error.message));
  });

  // Socket caiu: nenhuma resposta vai chegar, então não deixa ninguém esperando
  // o timeout inteiro.
  socket.onClose(() => {
    for (const id of [...pending.keys()]) {
      settle(id).reject(new RpcError("closed", "conexão fechada antes da resposta"));
    }
  });

  return {
    request(op, payload = {}) {
      const id = String(nextId++);
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          pending.delete(id);
          reject(new RpcError("timeout", `sem resposta para ${op} em ${timeoutMs}ms`));
        }, timeoutMs);
        pending.set(id, { resolve, reject, timer });
        try {
          socket.send({ type: "request", id, op, payload });
        } catch (err) {
          settle(id);
          reject(err);
        }
      });
    },
  };
}

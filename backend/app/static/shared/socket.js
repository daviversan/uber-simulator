// Cliente WebSocket fino: conecta, envia/recebe JSON e permite vários ouvintes.
// Não reconecta sozinho: se a conexão cair, a página mostra "recarregue".

export class WebSocketClient {
  constructor(path) {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    this.socket = new WebSocket(`${protocol}//${location.host}${path}`);
    this._openPromise = new Promise((resolve) => {
      this.socket.addEventListener("open", () => resolve(), { once: true });
    });
    this._handlers = new Set();
    this.socket.addEventListener("message", (event) => {
      const msg = JSON.parse(event.data);
      this._handlers.forEach((handler) => handler(msg));
    });
  }

  connected() {
    return this._openPromise;
  }

  isOpen() {
    return this.socket.readyState === WebSocket.OPEN;
  }

  send(msg) {
    this.socket.send(JSON.stringify(msg));
  }

  // Vários ouvintes ao mesmo tempo (ex.: main.js trata posições e rpc.js trata
  // respostas). Devolve a função que remove o ouvinte.
  onMessage(handler) {
    this._handlers.add(handler);
    return () => this._handlers.delete(handler);
  }

  onClose(handler) {
    this.socket.addEventListener("close", handler);
  }
}

// Identidade do motorista, persistência entre recarregamentos e o handshake de
// entrada com o servidor.

const ID_KEY = "driver:id";
const POS_KEY = "driver:lastPosition";

// sessionStorage pode lançar (modo privado, cookies bloqueados). Sem ele o app
// funciona igual, só não lembra o motorista ao recarregar — por isso o
// try/catch: uma conveniência não pode derrubar o app.
function read(key) {
  try { return sessionStorage.getItem(key); } catch { return null; }
}
function write(key, value) {
  try { sessionStorage.setItem(key, value); } catch { /* sem persistência: tudo bem */ }
}

// sessionStorage (e não localStorage) de propósito: vale por ABA. Duas abas =
// dois motoristas distintos, o que é ótimo para testar vários ao mesmo tempo.
// Recarregar a aba mantém o id, então reentrar é o MESMO motorista, não um
// fantasma novo a cada F5. (localStorage faria todas as abas serem a mesma
// pessoa, brigando pelo mesmo driver_id.)
export function loadDriverId() {
  let id = read(ID_KEY);
  if (!id) {
    // getRandomValues funciona em qualquer contexto; crypto.randomUUID() só
    // existe em contexto seguro (https/localhost) e quebraria abrindo o app por
    // um IP da rede local.
    const bytes = crypto.getRandomValues(new Uint8Array(4));
    id = "app_" + [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
    write(ID_KEY, id);
  }
  return id;
}

export function saveLastPosition(pos) {
  write(POS_KEY, JSON.stringify({ lat: pos.lat, lon: pos.lon }));
}

export function loadLastPosition() {
  try {
    const p = JSON.parse(read(POS_KEY));
    return Number.isFinite(p?.lat) && Number.isFinite(p?.lon) ? p : null;
  } catch {
    return null;
  }
}

// Envia `join` e espera a resposta: `joined` (deu certo, traz `config` do servidor)
// ou `error` (recusado).
// Resolve/rejeita uma vez só e sempre remove o próprio listener — sem isso cada
// tentativa de entrada deixaria um handler órfão escutando o socket.
export function joinAsDriver(socket, driverId, pos, timeoutMs = 5000) {
  return new Promise((resolve, reject) => {
    let off = () => {};
    const timer = setTimeout(() => {
      off();
      reject(new Error("o servidor não respondeu ao join"));
    }, timeoutMs);
    off = socket.onMessage((msg) => {
      if (msg.type !== "joined" && msg.type !== "error") return;
      clearTimeout(timer);
      off();
      if (msg.type === "joined") resolve(msg.config ?? {});
      else reject(new Error(msg.message));
    });
    socket.send({ type: "join", role: "driver", driver_id: driverId, lat: pos.lat, lon: pos.lon });
  });
}

import { connect } from "../../shared/connection.js";
import { startDriving } from "./drive.js";
import { setupJoinScreen } from "./join.js";
import { joinAsDriver, loadDriverId, loadLastPosition } from "./session.js";

const conn = connect(document.getElementById("conn-status"));
const { socket, rpc } = conn;
const driverId = loadDriverId();

setupJoinScreen({
  driverId,
  initial: loadLastPosition(), // recarregar a aba reabre o formulário já preenchido
  // `cities.list` é a única op que um socket ainda sem join pode chamar (rpc.py).
  loadCities: async () => {
    await socket.connected();
    return rpc.request("cities.list");
  },
  onSubmit: async (pos) => {
    await socket.connected();
    const config = await joinAsDriver(socket, driverId, pos);
    startDriving({ socket, driverId, start: pos, instance: conn.instance, config });
  },
});

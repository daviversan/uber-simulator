// Cópia local da frota: Map<driver_id, { prev, curr, updatedAt }>.
// O dono do dado é o Redis; o navegador só espelha o que o servidor manda.
// Guardar a posição anterior (prev) permite ao map.js animar o movimento.

export function createFleet() {
  const drivers = new Map();

  // Idempotente: aplicar a mesma posição duas vezes não duplica nada.
  function upsert(data) {
    const existing = drivers.get(data.driver_id);
    drivers.set(data.driver_id, {
      prev: existing ? existing.curr : data,
      curr: data,
      updatedAt: performance.now(),
    });
  }

  return {
    load: (snapshot) => snapshot.forEach(upsert),
    apply: upsert,
    remove: (driverId) => drivers.delete(driverId),
    all: () => drivers,
    size: () => drivers.size,
  };
}

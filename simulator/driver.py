"""Um bot: percorre a rota da sua cidade em loop e envia a posição a cada tick."""
import asyncio
from dataclasses import dataclass

from cities import CITIES

ROUTE_STEPS = 60


def interpolate_route(start: tuple[float, float], end: tuple[float, float], steps: int) -> list[tuple[float, float]]:
    """`steps` pontos de start até end e o caminho de volta: um circuito fechado."""
    (lat0, lon0), (lat1, lon1) = start, end
    forward = [(lat0 + (lat1 - lat0) * i / steps, lon0 + (lon1 - lon0) * i / steps) for i in range(steps + 1)]
    return forward + forward[-2:0:-1]  # volta, sem repetir as pontas


# Uma rota por cidade.
ROUTES: dict[str, list[tuple[float, float]]] = {
    city_id: interpolate_route(city["start"], city["end"], ROUTE_STEPS) for city_id, city in CITIES.items()
}


@dataclass
class Driver:
    driver_id: str
    city_id: str
    offset: int  # ponto de partida na rota, para os bots não andarem todos juntos


async def run_driver(link, driver: Driver, sim) -> None:
    """Roda até a task ser cancelada (despawn/reset).

    `link` é o TelemetryLink e `sim` a Simulation (simulator.py). Ler
    sim.rate_multiplier a cada volta faz o controle de velocidade do painel
    valer já no próximo tick.
    """
    route = ROUTES[driver.city_id]
    idx = driver.offset % len(route)
    while True:
        await sim.running_event.wait()  # pausado: dorme aqui sem gastar CPU
        idx = (idx + 1) % len(route)
        lat, lon = route[idx]
        await link.send_position(driver.driver_id, lat, lon)
        await asyncio.sleep(sim.tick_seconds / sim.rate_multiplier)

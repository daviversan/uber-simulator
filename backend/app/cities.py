"""Cidades conhecidas e seus centros.

O simulador tem a própria lista (simulator/cities.py, com pontos de rota):
são imagens Docker separadas e uma não importa código da outra.
"""

CITIES: dict[str, dict] = {
    "sao_paulo": {"name": "São Paulo", "center": (-23.5937, -46.6565)},
    "new_york": {"name": "New York", "center": (40.7321, -73.9912)},
    "london": {"name": "London", "center": (51.5031, -0.1000)},
    "tokyo": {"name": "Tokyo", "center": (35.6591, 139.7230)},
    "lagos": {"name": "Lagos", "center": (6.4624, 3.4711)},
    "sydney": {"name": "Sydney", "center": (-33.8738, 151.2448)},
}


def nearest_city(lat: float, lon: float) -> str:
    """Cidade cujo centro está mais perto de (lat, lon).

    Usa distância simples em graus, não haversine: as cidades estão a milhares
    de km umas das outras, então a aproximação sempre escolhe a mesma cidade.
    """
    return min(
        CITIES,
        key=lambda city_id: (lat - CITIES[city_id]["center"][0]) ** 2
        + (lon - CITIES[city_id]["center"][1]) ** 2,
    )

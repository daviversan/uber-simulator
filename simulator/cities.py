"""Cidades do simulador: cada uma tem dois pontos (start/end) entre os quais os bots vão e voltam.

O backend tem a própria lista (backend/app/cities.py), só com os centros.
"""

CITIES: dict[str, dict] = {
    "sao_paulo": {
        "name": "São Paulo",
        "start": (-23.5613, -46.6565),  # Av. Paulista
        "end": (-23.6261, -46.6564),  # Aeroporto de Congonhas
    },
    "new_york": {
        "name": "New York",
        "start": (40.7580, -73.9855),  # Times Square
        "end": (40.7061, -73.9969),  # Brooklyn Bridge
    },
    "london": {
        "name": "London",
        "start": (51.5007, -0.1246),  # Big Ben
        "end": (51.5055, -0.0754),  # Tower Bridge
    },
    "tokyo": {
        "name": "Tokyo",
        "start": (35.6595, 139.7005),  # Shibuya
        "end": (35.6586, 139.7454),  # Tokyo Tower
    },
    "lagos": {
        "name": "Lagos",
        "start": (6.4550, 3.3841),  # Lagos Island
        "end": (6.4698, 3.5581),  # Lekki
    },
    "sydney": {
        "name": "Sydney",
        "start": (-33.8568, 151.2153),  # Opera House
        "end": (-33.8908, 151.2743),  # Bondi Beach
    },
}

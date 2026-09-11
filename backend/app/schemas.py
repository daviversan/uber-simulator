from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field

class TelemetryInput(BaseModel):
    driver_id: str = Field(..., description="Identificador único do motorista")

    latitude: float = Field(
        ...,
        ge = -90.0,
        le = 90.0,
        description = "Latitude em graus decimais",
        examples = [-23.55052],
    )

    longitude: float = Field(
        ...,
        ge = -180.0,
        le = 180.0,
        description="Longitude em graus decimais",
        examples=[-46.633308],
    )

    speed: float = Field(
        ..., ge = 0.0, description="Velocidade instantânea em km/h"
    )

    timestamp: datetime = Field(
        default_factory = lambda: datetime.now(timezone.utc), description = "Data e hora da leitura"
    )

    model_config = ConfigDict(
        str_strip_whitespace = True,
        json_schema_extra = {
            "example": {
                "driver_id": "driver_01",
                "latitude": -23.55052,
                "longitude": -46.633308,
                "speed": 42.5,
                "timestamp": "2026-09-11T16:00:00Z",
            }
        },
    )

class TelemetryResponse(BaseModel):
    status: str
    processed_at: datetime

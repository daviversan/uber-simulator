"""Formatos de dados validados pelo pydantic.

As mensagens do WebSocket e os comandos do simulador são "uniões discriminadas":
o campo `type` diz qual modelo usar. O pydantic lê `type` e valida direto contra
o modelo certo, e qualquer mensagem malformada é rejeitada antes de ter efeito.
"""
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

Lat = Annotated[float, Field(ge=-90.0, le=90.0)]
Lon = Annotated[float, Field(ge=-180.0, le=180.0)]


class TelemetryInput(BaseModel):
    """Uma posição pronta para ser gravada (ver ingest.py)."""

    driver_id: str
    latitude: Lat
    longitude: Lon
    # "app" = motorista humano (/driver); "sim" = bot do simulador.
    # Definido pelo servidor conforme o tipo de socket, nunca pelo cliente.
    source: Literal["app", "sim"]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --- Mensagens que um cliente pode mandar pelo WebSocket ---------------------

class _ClientMessage(BaseModel):
    # extra="forbid": campo desconhecido = mensagem rejeitada. Por exemplo, um
    # `position` com "driver_id" não passa: o id do motorista vem só do `join`.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class JoinMessage(_ClientMessage):
    """Primeira mensagem de todo cliente: diz quem ele é."""

    type: Literal["join"]
    role: Literal["admin", "driver", "sim"]
    driver_id: str | None = Field(default=None, min_length=1, max_length=64)
    lat: Lat | None = None
    lon: Lon | None = None

    @model_validator(mode="after")
    def _only_driver_has_position(self) -> "JoinMessage":
        fields = (self.driver_id, self.lat, self.lon)
        if self.role == "driver" and None in fields:
            raise ValueError("role=driver exige driver_id, lat e lon")
        if self.role != "driver" and fields != (None, None, None):
            raise ValueError(f"role={self.role} não aceita driver_id, lat nem lon")
        return self


class PositionMessage(_ClientMessage):
    """Posição do motorista do app. O driver_id é o do `join` deste socket."""

    type: Literal["position"]
    lat: Lat
    lon: Lon
    ts: datetime | None = None  # quando o GPS leu; padrão = agora


class SimPositionMessage(_ClientMessage):
    """Posição de UM bot. O simulador usa um só socket para todos os bots, por isso o driver_id vai na mensagem."""

    type: Literal["sim_position"]
    driver_id: str = Field(min_length=1, max_length=64)
    lat: Lat
    lon: Lon
    ts: datetime | None = None


class SubscribeMessage(_ClientMessage):
    """Admin informa a área visível do mapa; só recebe posições dentro dela."""

    type: Literal["subscribe"]
    bbox: str  # "west,south,east,north"


class RequestMessage(_ClientMessage):
    """Pedido com resposta: o servidor responde com o mesmo `id` (ver rpc.py)."""

    type: Literal["request"]
    id: str = Field(min_length=1, max_length=64)
    op: str = Field(min_length=1, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)


ClientMessage = Annotated[
    Union[JoinMessage, PositionMessage, SimPositionMessage, SubscribeMessage, RequestMessage],
    Field(discriminator="type"),
]
client_message_adapter = TypeAdapter(ClientMessage)


# --- Comandos do painel Simulação (repassados ao simulador via Redis) --------

class StartCommand(BaseModel):
    type: Literal["start"]


class PauseCommand(BaseModel):
    type: Literal["pause"]


class ResetCommand(BaseModel):
    type: Literal["reset"]


class SpawnCommand(BaseModel):
    type: Literal["spawn"]
    city: str
    count: int = Field(gt=0)


class DespawnCommand(BaseModel):
    type: Literal["despawn"]
    driver_id: str


class SetRateCommand(BaseModel):
    type: Literal["set_rate"]
    multiplier: float = Field(gt=0)


SimCommand = Annotated[
    Union[StartCommand, PauseCommand, ResetCommand, SpawnCommand, DespawnCommand, SetRateCommand],
    Field(discriminator="type"),
]
sim_command_adapter = TypeAdapter(SimCommand)

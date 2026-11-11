"""Configuração lida de variáveis de ambiente (ex.: MIN_MOVE_M=10 vira settings.min_move_m)."""
from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379/0"
    database_url: str = "postgresql+asyncpg://uber:uber@postgres:5432/uber"

    # Filtro de movimento: deslocamentos menores que isto são ruído de GPS.
    min_move_m: float = 10.0
    # Parado, o motorista reenvia a posição a cada heartbeat_s para provar que está vivo.
    heartbeat_s: float = 30.0
    # Sem notícias há stale_after_s, o job de limpeza tira o motorista do mapa.
    stale_after_s: float = 300.0

    @model_validator(mode="after")
    def _heartbeat_well_below_stale(self) -> "Settings":
        # Folga para perder até 3 heartbeats seguidos sem o motorista sumir do mapa.
        if self.heartbeat_s * 3 > self.stale_after_s:
            raise ValueError("heartbeat_s deve ser <= stale_after_s / 3")
        return self


settings = Settings()

"""Tabelas do Postgres (SQLAlchemy). As migrations em alembic/versions criam o mesmo schema."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Driver(Base):
    """Uma linha por motorista. `last_seen` é atualizado a cada mensagem."""

    __tablename__ = "drivers"

    driver_id: Mapped[str] = mapped_column(String, primary_key=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Position(Base):
    """Histórico de posições. Só recebe INSERT: nunca é alterado nem apagado."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    driver_id: Mapped[str] = mapped_column(String, ForeignKey("drivers.driver_id"))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    # recorded_at = quando o GPS leu; ingested_at = quando o servidor recebeu.
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Acelera a consulta mais comum: "posições do motorista X, por data".
    __table_args__ = (Index("idx_positions_driver_time", "driver_id", recorded_at.desc()),)


class JobRun(Base):
    """Uma linha por execução de job (painel Jobs do admin)."""

    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String)  # "success" | "error"
    detail: Mapped[str | None] = mapped_column(String)

    # Acelera "última execução de cada job".
    __table_args__ = (Index("idx_job_runs_name_started", "job_name", started_at.desc()),)

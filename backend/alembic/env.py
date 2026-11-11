"""Executado pelo comando `alembic upgrade head` (serviço `migrate` do compose)."""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.models import Base
from app.settings import settings

fileConfig(context.config.config_file_name)

# Usado pelo `alembic revision --autogenerate`: compara os models com o banco.
target_metadata = Base.metadata


def run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def main() -> None:
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as connection:
        await connection.run_sync(run_migrations)
    await engine.dispose()


asyncio.run(main())

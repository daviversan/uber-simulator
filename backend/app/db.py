"""Conexão com o Postgres. Uso: `async with async_session() as session: ...`"""
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.settings import settings

# Cada instância da API tem seu próprio pool de conexões.
# 4 instâncias × (5 + 5) = até 40 conexões, abaixo do limite padrão de 100 do Postgres.
engine = create_async_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,  # testa a conexão antes de usar e descarta as que morreram
)

async_session = async_sessionmaker(engine, expire_on_commit=False)

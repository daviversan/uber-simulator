"""Jobs de manutenção, disparados pelo botão "Run now" do painel Jobs.

O job roda dentro da própria instância da API que recebeu o pedido. Cada
execução vira uma linha em job_runs, que o painel lista.
"""
from datetime import datetime, timedelta, timezone

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import store
from app.events import publish_removed
from app.models import JobRun
from app.settings import settings


async def cleanup_stale_drivers(r: redis.Redis) -> str:
    """Tira do mapa (Redis) quem não manda posição há mais de stale_after_s."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.stale_after_s)
    stale_ids = [
        driver_id
        for driver_id, payload in (await store.get_all(r)).items()
        if datetime.fromisoformat(payload["timestamp"]) < cutoff
    ]
    for driver_id in stale_ids:
        await store.remove(r, driver_id)
        await publish_removed(r, driver_id)  # o admin apaga o marcador na hora

    if not stale_ids:
        return "nenhum motorista inativo"
    return f"{len(stale_ids)} motorista(s) removido(s): {', '.join(stale_ids)}"


# Nome do job -> (descrição, função).
JOBS = {
    "cleanup_stale_drivers": ("Remove do mapa motoristas sem posição recente", cleanup_stale_drivers),
}


async def list_jobs(session: AsyncSession) -> list[dict]:
    result = []
    for name, (description, _) in JOBS.items():
        last = (
            await session.execute(
                select(JobRun).where(JobRun.job_name == name).order_by(JobRun.started_at.desc()).limit(1)
            )
        ).scalar_one_or_none()
        result.append({
            "name": name,
            "description": description,
            "last_run": last and {
                "started_at": last.started_at.isoformat(),
                "status": last.status,
                "detail": last.detail,
            },
        })
    return result


async def run_job(session: AsyncSession, r: redis.Redis, name: str) -> dict:
    """Executa o job e registra o resultado. Lança KeyError se o job não existe."""
    _, fn = JOBS[name]
    started_at = datetime.now(timezone.utc)
    try:
        detail, status = await fn(r), "success"
    except Exception as exc:
        detail, status = str(exc), "error"

    session.add(JobRun(
        job_name=name,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        status=status,
        detail=detail,
    ))
    await session.commit()
    return {"job_name": name, "status": status, "detail": detail}

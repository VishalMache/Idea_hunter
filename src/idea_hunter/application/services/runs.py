"""Resumable run and step lifecycle management."""

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from idea_hunter.db.models import PipelineRun, RunStep


DEFAULT_STEPS = (
    "collect",
    "normalize_dedupe",
    "triage",
    "embed",
    "cluster",
    "spend_gate",
    "extract",
    "research",
    "score",
)


async def create_run(
    session: AsyncSession,
    *,
    idempotency_key: str,
    kind: str = "full",
    config: dict | None = None,
    budget_usd: float = 2.0,
    steps: Iterable[str] = DEFAULT_STEPS,
) -> PipelineRun:
    """Create a run once; repeated requests with the same key are safe."""
    existing = await session.scalar(
        select(PipelineRun).where(PipelineRun.idempotency_key == idempotency_key)
    )
    if existing:
        return existing

    run = PipelineRun(
        kind=kind,
        idempotency_key=idempotency_key,
        config_json=config or {},
        budget_usd=budget_usd,
        status="pending",
    )
    session.add(run)
    await session.flush()
    session.add_all([RunStep(run_id=run.id, step_key=step, sequence=index) for index, step in enumerate(steps)])
    await session.flush()
    return run


async def cancel_run(session: AsyncSession, run: PipelineRun) -> PipelineRun:
    if run.status in {"completed", "failed", "cancelled"}:
        return run
    run.status = "cancelled"
    run.finished_at = datetime.now(timezone.utc)
    for step in run.steps:
        if step.status in {"pending", "retrying"}:
            step.status = "cancelled"
            step.finished_at = run.finished_at
    return run


async def retry_step(session: AsyncSession, step: RunStep) -> RunStep:
    if step.run.status == "cancelled":
        raise ValueError("Cannot retry a step from a cancelled run.")
    step.status = "pending"
    step.error = None
    step.next_attempt_at = None
    step.finished_at = None
    if step.run.status in {"failed", "completed"}:
        step.run.status = "pending"
        step.run.finished_at = None
    return step

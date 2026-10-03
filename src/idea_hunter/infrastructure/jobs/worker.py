"""Minimal database-backed worker for persisted pipeline steps.

The worker deliberately keeps handlers injectable. This lets the existing CLI
remain usable while steps are moved one at a time into application services.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from idea_hunter.config import settings
from idea_hunter.db.models import PipelineRun, RunStep
from idea_hunter.db.session import session_scope


StepHandler = Callable[[PipelineRun, RunStep], Awaitable[dict | None]]


class PipelineWorker:
    def __init__(self, handlers: dict[str, StepHandler] | None = None, max_attempts: int = 3):
        self.handlers = handlers or {}
        self.max_attempts = max_attempts

    async def process_one(self) -> bool:
        async with session_scope() as session:
            now = datetime.now(timezone.utc)
            step = await session.scalar(
                select(RunStep)
                .join(PipelineRun)
                .where(
                    PipelineRun.status.in_(("pending", "running")),
                    RunStep.status.in_(("pending", "retrying")),
                    (RunStep.next_attempt_at.is_(None) | (RunStep.next_attempt_at <= now)),
                )
                .order_by(RunStep.id)
                .options(selectinload(RunStep.run))
                .with_for_update(skip_locked=True)
            )
            if not step:
                return False
            run = step.run
            prior_step = await session.scalar(
                select(RunStep.id).where(
                    RunStep.run_id == run.id,
                    RunStep.sequence < step.sequence,
                    RunStep.status != "completed",
                )
            )
            if prior_step:
                return False
            if run.total_cost_usd >= run.budget_usd:
                step.status = "blocked"
                step.error = "Per-run budget exceeded."
                run.status = "failed"
                run.error = step.error
                run.finished_at = now
                return True

            handler = self.handlers.get(step.step_key)
            if not handler:
                step.status = "blocked"
                step.error = f"No worker handler registered for '{step.step_key}'."
                return True

            run.status = "running"
            run.started_at = run.started_at or now
            step.status = "running"
            step.started_at = now
            step.attempt_count += 1
            try:
                output = await handler(run, step)
                step.output_json = output or {}
                step.status = "completed"
                step.finished_at = datetime.now(timezone.utc)
                pending = await session.scalar(
                    select(RunStep.id).where(RunStep.run_id == run.id, RunStep.status.in_(("pending", "retrying", "running")))
                )
                if not pending:
                    run.status = "completed"
                    run.finished_at = step.finished_at
            except Exception as error:  # handler errors are durable and retryable
                step.error = str(error)[:4000]
                if step.attempt_count >= self.max_attempts:
                    step.status = "failed"
                    step.finished_at = datetime.now(timezone.utc)
                    run.status = "failed"
                    run.error = step.error
                    run.finished_at = step.finished_at
                else:
                    step.status = "retrying"
                    step.next_attempt_at = now + timedelta(seconds=2 ** step.attempt_count)
            return True

    async def run_forever(self):
        while True:
            worked = await self.process_one()
            if not worked:
                await asyncio.sleep(settings.worker_poll_seconds)


async def main():
    await PipelineWorker().run_forever()


if __name__ == "__main__":
    asyncio.run(main())

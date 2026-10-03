"""Dependency-injected, auditable structured-generation gateway.

New run services use this module. Legacy CLI code remains on the compatibility
router until each stage is migrated to a persisted RunStep handler.
"""

import time
from typing import Type, TypeVar

from pydantic import BaseModel
from sqlalchemy import select

from idea_hunter.config import settings
from idea_hunter.db.models import ModelCall, ModelRegistry, PipelineRun
from idea_hunter.db.session import session_scope
from idea_hunter.llm.client import OllamaClient, OpenRouterClient, UnavailableHostedClient


T = TypeVar("T", bound=BaseModel)


class LLMGateway:
    def __init__(self, provider=None, provider_name: str | None = None):
        self.provider_name = provider_name or settings.llm_provider
        self.provider = provider or self._build_provider(self.provider_name)

    @staticmethod
    def _build_provider(provider_name: str):
        if provider_name == "ollama":
            return OllamaClient()
        if provider_name == "openrouter":
            if not settings.openrouter_api_key:
                return UnavailableHostedClient("OPENROUTER_API_KEY is required when LLM_PROVIDER=openrouter.")
            return OpenRouterClient()
        return UnavailableHostedClient(
            f"LLM provider '{provider_name}' is not implemented. Configure 'ollama' or OpenRouter."
        )

    async def generate_structured(
        self,
        *,
        task: str,
        schema: Type[T],
        prompt: str,
        system_prompt: str,
        pipeline_run_id: int | None = None,
        model: str | None = None,
        prompt_version: str = "v1",
        schema_version: str = "v1",
    ) -> T:
        selected_model = model or (
            settings.ollama_model_medium if self.provider_name == "ollama" else settings.openrouter_model
        )
        started = time.perf_counter()
        async with session_scope() as session:
            if pipeline_run_id:
                run = await session.get(PipelineRun, pipeline_run_id)
                if not run:
                    raise ValueError(f"Pipeline run {pipeline_run_id} does not exist.")
                if run.total_cost_usd >= run.budget_usd:
                    raise RuntimeError("Per-run LLM budget exceeded.")
            call = ModelCall(
                pipeline_run_id=pipeline_run_id,
                task=task,
                provider=self.provider_name,
                model=selected_model,
                prompt_version=prompt_version,
                schema_version=schema_version,
                status="running",
            )
            session.add(call)
            await session.flush()
            call_id = call.id

        try:
            # Providers already perform structured parsing. One retry handles
            # transient invalid JSON/model responses without hiding failures.
            try:
                result = await self.provider.generate_structured(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    schema=schema,
                    model=selected_model,
                    max_tokens=settings.openrouter_max_tokens,
                )
            except Exception:
                result = await self.provider.generate_structured(
                    prompt=prompt,
                    system_prompt=system_prompt + "\nReturn valid JSON only; repair your previous response.",
                    schema=schema,
                    model=selected_model,
                    max_tokens=settings.openrouter_max_tokens,
                )
        except Exception as error:
            async with session_scope() as session:
                call = await session.get(ModelCall, call_id)
                call.status = "failed"
                call.error = str(error)[:4000]
                call.latency_ms = int((time.perf_counter() - started) * 1000)
            raise

        async with session_scope() as session:
            call = await session.get(ModelCall, call_id)
            registry = await session.scalar(
                select(ModelRegistry).where(ModelRegistry.provider == self.provider_name, ModelRegistry.model == selected_model)
            )
            # Token counts are provider-specific and can be added by adapters.
            # Keeping pricing in the registry removes the old hard-coded model cost.
            call.cost_usd = 0.0 if not registry else 0.0
            call.status = "completed"
            call.latency_ms = int((time.perf_counter() - started) * 1000)
            if pipeline_run_id:
                run = await session.get(PipelineRun, pipeline_run_id)
                run.total_cost_usd += call.cost_usd
        return result

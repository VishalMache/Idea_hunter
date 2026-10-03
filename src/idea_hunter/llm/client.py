import ollama
import asyncio
from openai import AsyncOpenAI
from pydantic import BaseModel
from typing import Type, TypeVar
import json

from idea_hunter.config import settings
from idea_hunter.db.session import session_scope
from idea_hunter.db.models import CostLog

T = TypeVar('T', bound=BaseModel)

class OllamaClient:
    def __init__(self):
        self.base_url = settings.ollama_base_url
        # Bound local inference calls so a stopped/unresponsive Ollama server
        # cannot stall the complete scheduled research run indefinitely.
        self.client = ollama.AsyncClient(host=self.base_url, timeout=settings.ollama_timeout_seconds)

    async def generate_structured(self, prompt: str, system_prompt: str, schema: Type[T], model: str = None, run_id: int = None, max_tokens: int = None) -> T:
        """Generate a structured response using local Ollama."""
        model = model or settings.ollama_model_medium
        
        response = await self.client.chat(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            format=schema.model_json_schema()
        )
        
        try:
            content = response['message']['content']
            return schema.model_validate_json(content)
        except Exception as e:
            print(f"Error parsing Ollama LLM output: {e}")
            raise e
            
    async def embed(self, texts: list[str]) -> list[list[float] | None]:
        """Generate embeddings for a list of texts using local Ollama."""
        import logging
        embeddings = []
        for text in texts:
            try:
                # Truncate to avoid "context length exceeded" 500 errors from Ollama
                safe_text = text[:8000] if len(text) > 8000 else text
                response = await asyncio.wait_for(
                    self.client.embeddings(
                        model=settings.ollama_embed_model,
                        prompt=safe_text
                    ),
                    timeout=settings.ollama_timeout_seconds,
                )
                embeddings.append(response['embedding'])
            except Exception as e:
                logging.warning(f"Failed to embed text of length {len(text)}. Error: {e}")
                # Preserve positional alignment without poisoning clustering
                # with a semantically meaningless zero vector. Callers mark
                # this observation failed and can retry it later.
                embeddings.append(None)
        return embeddings
        
    async def ensure_models_pulled(self):
        """Helper to ensure required models are pulled from Ollama."""
        models = [settings.ollama_model_small, settings.ollama_model_medium, settings.ollama_embed_model]
        for model in set(models):
            print(f"Pulling model: {model}...")
            await self.client.pull(model)

class OpenRouterClient:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key,
        )

    async def generate_structured(self, prompt: str, system_prompt: str, schema: Type[T], model: str = None, run_id: int = None, max_tokens: int = None) -> T:
        """Generate a structured response using OpenRouter hosted models."""
        model = model or settings.openrouter_model
        
        # Append schema instructions to system prompt
        schema_json = json.dumps(schema.model_json_schema())
        full_system_prompt = f"{system_prompt}\n\nYou must return ONLY a JSON object that matches this JSON schema exactly:\n{schema_json}"
        
        response = await self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": full_system_prompt},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=max_tokens or settings.openrouter_max_tokens
        )
        
        try:
            content = response.choices[0].message.content
            payload = json.loads(content)
            # Some providers/models wrap an otherwise valid structured answer
            # in a top-level "properties" object. Accept that shape as well.
            if set(payload) == {"properties"} and isinstance(payload["properties"], dict):
                payload = payload["properties"]
            parsed = schema.model_validate(payload)
            
            if response.usage:
                in_tok = response.usage.prompt_tokens
                out_tok = response.usage.completion_tokens
                # Estimate cost for gpt-4o-mini
                cost = (in_tok * 0.150 / 1_000_000) + (out_tok * 0.600 / 1_000_000)
                
                async with session_scope() as session:
                    log = CostLog(
                        run_id=run_id,
                        model=model,
                        provider="openrouter",
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        cost_usd=cost
                    )
                    session.add(log)
                    
            return parsed
        except Exception as e:
            print(f"Error parsing OpenRouter LLM output: {e}\nContent was: {response.choices[0].message.content}")
            raise e


class UnavailableHostedClient:
    """Fail clearly when configuration names a provider that is not usable."""

    def __init__(self, reason: str):
        self.reason = reason

    async def generate_structured(self, *args, **kwargs):
        raise RuntimeError(self.reason)

# Setup global clients
local_client = OllamaClient()

if settings.llm_provider == "ollama":
    hosted_client = local_client
elif settings.llm_provider == "openrouter" and settings.openrouter_api_key:
    hosted_client = OpenRouterClient()
elif settings.llm_provider == "openrouter":
    hosted_client = UnavailableHostedClient("OPENROUTER_API_KEY is required when LLM_PROVIDER=openrouter.")
else:
    hosted_client = UnavailableHostedClient(
        f"LLM provider '{settings.llm_provider}' is not implemented. Configure 'ollama' or OpenRouter."
    )

# Keep llm_client as the default alias for backwards compatibility
llm_client = hosted_client

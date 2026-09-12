import ollama
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
        self.client = ollama.AsyncClient(host=self.base_url)

    async def generate_structured(self, prompt: str, system_prompt: str, schema: Type[T], model: str = None, run_id: int = None) -> T:
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
            
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts using local Ollama."""
        embeddings = []
        for text in texts:
            response = await self.client.embeddings(
                model=settings.ollama_embed_model,
                prompt=text
            )
            embeddings.append(response['embedding'])
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

    async def generate_structured(self, prompt: str, system_prompt: str, schema: Type[T], model: str = None, run_id: int = None) -> T:
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
            response_format={"type": "json_object"}
        )
        
        try:
            content = response.choices[0].message.content
            parsed = schema.model_validate_json(content)
            
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

# Setup global clients
local_client = OllamaClient()

if settings.llm_provider == "openrouter" and settings.openrouter_api_key:
    hosted_client = OpenRouterClient()
else:
    hosted_client = local_client

# Keep llm_client as the default alias for backwards compatibility
llm_client = hosted_client

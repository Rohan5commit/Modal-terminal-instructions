import asyncio
import time
from dataclasses import dataclass
from typing import Any

import google.generativeai as genai
from anthropic import AsyncAnthropic
from groq import AsyncGroq
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from together import AsyncTogether


@dataclass(slots=True)
class LLMResponse:
    content: str
    model: str
    tokens_used: dict[str, int]
    response_time_ms: int
    error: str | None = None


class UnifiedLLMClient:
    """Unified async interface across multiple LLM providers."""

    def __init__(self, config: dict[str, str]):
        self.openai_key = config.get("OPENAI_API_KEY", "")
        self.anthropic_key = config.get("ANTHROPIC_API_KEY", "")
        self.google_key = config.get("GOOGLE_API_KEY", "")
        self.groq_key = config.get("GROQ_API_KEY", "")
        self.together_key = config.get("TOGETHER_API_KEY", "")

        self.openai_client = AsyncOpenAI(api_key=self.openai_key) if self.openai_key else None
        self.anthropic_client = AsyncAnthropic(api_key=self.anthropic_key) if self.anthropic_key else None
        self.groq_client = AsyncGroq(api_key=self.groq_key) if self.groq_key else None
        self.together_client = AsyncTogether(api_key=self.together_key) if self.together_key else None

        if self.google_key:
            genai.configure(api_key=self.google_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def call_openai(self, prompt: str, model: str, temperature: float, max_tokens: int) -> LLMResponse:
        if not self.openai_client:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        started = time.perf_counter()
        response = await self.openai_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        usage = response.usage
        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=model,
            tokens_used={
                "prompt": int(usage.prompt_tokens if usage else 0),
                "completion": int(usage.completion_tokens if usage else 0),
                "total": int(usage.total_tokens if usage else 0),
            },
            response_time_ms=elapsed_ms,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def call_anthropic(self, prompt: str, model: str, temperature: float, max_tokens: int) -> LLMResponse:
        if not self.anthropic_client:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")

        started = time.perf_counter()
        response = await self.anthropic_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        content = ""
        if response.content:
            first = response.content[0]
            content = getattr(first, "text", "") or ""

        in_tokens = int(getattr(response.usage, "input_tokens", 0))
        out_tokens = int(getattr(response.usage, "output_tokens", 0))
        return LLMResponse(
            content=content,
            model=model,
            tokens_used={"prompt": in_tokens, "completion": out_tokens, "total": in_tokens + out_tokens},
            response_time_ms=elapsed_ms,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def call_google(self, prompt: str, model: str, temperature: float, max_tokens: int) -> LLMResponse:
        if not self.google_key:
            raise RuntimeError("GOOGLE_API_KEY is not configured")

        started = time.perf_counter()
        model_obj = genai.GenerativeModel(model)
        response = await asyncio.to_thread(
            model_obj.generate_content,
            prompt,
            generation_config=genai.GenerationConfig(temperature=temperature, max_output_tokens=max_tokens),
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = int(getattr(usage, "prompt_token_count", 0)) if usage else 0
        completion_tokens = int(getattr(usage, "candidates_token_count", 0)) if usage else 0
        total_tokens = int(getattr(usage, "total_token_count", prompt_tokens + completion_tokens)) if usage else 0

        return LLMResponse(
            content=getattr(response, "text", "") or "",
            model=model,
            tokens_used={"prompt": prompt_tokens, "completion": completion_tokens, "total": total_tokens},
            response_time_ms=elapsed_ms,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def call_groq(self, prompt: str, model: str, temperature: float, max_tokens: int) -> LLMResponse:
        if not self.groq_client:
            raise RuntimeError("GROQ_API_KEY is not configured")

        started = time.perf_counter()
        response = await self.groq_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        usage = response.usage
        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=model,
            tokens_used={
                "prompt": int(usage.prompt_tokens if usage else 0),
                "completion": int(usage.completion_tokens if usage else 0),
                "total": int(usage.total_tokens if usage else 0),
            },
            response_time_ms=elapsed_ms,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def call_together(self, prompt: str, model: str, temperature: float, max_tokens: int) -> LLMResponse:
        if not self.together_client:
            raise RuntimeError("TOGETHER_API_KEY is not configured")

        started = time.perf_counter()
        response = await self.together_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        usage: Any = response.usage
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0)) if usage else 0
        completion_tokens = int(getattr(usage, "completion_tokens", 0)) if usage else 0

        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=model,
            tokens_used={
                "prompt": prompt_tokens,
                "completion": completion_tokens,
                "total": prompt_tokens + completion_tokens,
            },
            response_time_ms=elapsed_ms,
        )

    async def call_model(
        self,
        provider: str,
        prompt: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        provider_key = provider.lower()
        if provider_key == "openai":
            return await self.call_openai(prompt, model, temperature, max_tokens)
        if provider_key == "anthropic":
            return await self.call_anthropic(prompt, model, temperature, max_tokens)
        if provider_key == "google":
            return await self.call_google(prompt, model, temperature, max_tokens)
        if provider_key == "groq":
            return await self.call_groq(prompt, model, temperature, max_tokens)
        if provider_key == "together":
            return await self.call_together(prompt, model, temperature, max_tokens)
        raise ValueError(f"Unsupported provider: {provider}")


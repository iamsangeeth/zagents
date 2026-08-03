"""Ollama and Pydantic AI integration."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from openai import OpenAI
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.output import NativeOutput
from pydantic_ai.providers.ollama import OllamaProvider

from ..config import OllamaSettings, settings


def build_ollama_model(config: OllamaSettings | None = None) -> OllamaModel:
    """Build Pydantic AI model backed by local Ollama."""
    config = config or settings.ollama
    provider = OllamaProvider(
        base_url=config.base_url,
        api_key=config.api_key,
    )
    return OllamaModel(config.model, provider=provider)


def build_agent(
    output_type: type[BaseModel],
    *,
    name: str,
    system_prompt: str,
    retries: int = 2,
    max_tokens: int = 1024,
    config: OllamaSettings | None = None,
) -> Agent[Any, Any]:
    """Build typed Pydantic AI agent with bounded Ollama output budget."""
    if max_tokens <= 0:
        raise ValueError("max_tokens must be greater than zero")
    return Agent(
        build_ollama_model(config),
        name=name,
        output_type=NativeOutput(output_type),
        system_prompt=system_prompt,
        model_settings={
            "max_tokens": max_tokens,
            "thinking": False,
            "openai_reasoning_effort": "none",
        },
        retries=retries,
    )


class OllamaClient:
    """OpenAI-compatible Ollama client for embeddings and health checks."""

    def __init__(self, config: OllamaSettings | None = None) -> None:
        self.config = config or settings.ollama
        self._openai = OpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            timeout=self.config.timeout_seconds,
        )

    def health(self) -> list[str]:
        """Return model IDs exposed by Ollama OpenAI-compatible endpoint."""
        return [model.id for model in self._openai.models.list().data]

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Create embeddings using configured Ollama embedding model."""
        if not texts:
            return []
        response = self._openai.embeddings.create(
            model=self.config.embedding_model,
            input=list(texts),
        )
        return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]

    def agent(
        self,
        output_type: type[BaseModel],
        *,
        name: str,
        system_prompt: str,
        retries: int = 2,
        max_tokens: int = 1024,
    ) -> Agent[Any, Any]:
        """Build typed Pydantic AI agent using this client's settings."""
        return build_agent(
            output_type,
            name=name,
            system_prompt=system_prompt,
            retries=retries,
            max_tokens=max_tokens,
            config=self.config,
        )

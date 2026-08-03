"""Local service clients used by Pydantic AI agents."""

from .ollama import OllamaClient, build_agent, build_ollama_model
from .postgres import PostgresClient
from .qdrant import QdrantClient, QdrantError

__all__ = [
    "OllamaClient",
    "PostgresClient",
    "QdrantClient",
    "QdrantError",
    "build_agent",
    "build_ollama_model",
]

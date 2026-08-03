"""Application configuration for local Parikzan services.

Configuration loads process environment first, then missing values from the
project `.env` file. Existing names such as ``OPENAI_BASE_URL`` and ``MODEL``
remain supported for Ollama's OpenAI-compatible API.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse


_PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE entries without overriding process environment."""
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()

        key, separator, value = line.partition("=")
        if not separator:
            continue
        key = key.strip()
        if not key or key in os.environ:
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


def _env(*names: str, default: str | None = None) -> str | None:
    """Return first non-empty environment value from ``names``."""
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return default


def _env_bool(name: str, *, default: bool) -> bool:
    value = _env(name)
    if value is None:
        return default
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be boolean, got {value!r}")


def _env_int(*names: str, default: int) -> int:
    value = _env(*names)
    name = names[0]
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than zero, got {parsed}")
    return parsed


def _url(value: str, *, name: str, schemes: set[str]) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in schemes or not parsed.netloc:
        allowed = ", ".join(sorted(schemes))
        raise ValueError(f"{name} must be URL with scheme {allowed}, got {value!r}")
    return value.rstrip("/")


@dataclass(frozen=True, slots=True)
class OllamaSettings:
    """Ollama OpenAI-compatible API settings."""

    provider: str
    base_url: str
    model: str
    embedding_model: str
    api_key: str = field(repr=False)
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class PostgresSettings:
    """PostgreSQL connection settings."""

    url: str = field(repr=False)
    pool_size: int = 5
    max_overflow: int = 10
    timeout_seconds: int = 30


@dataclass(frozen=True, slots=True)
class QdrantSettings:
    """Qdrant API and collection settings."""

    url: str
    api_key: str | None = field(default=None, repr=False)
    quiz_collection: str = "parikzan_quiz_context"
    knowledge_collection: str = "parikzan_knowledge"
    content_collection: str = "parikzan_approved_content"
    timeout_seconds: int = 30


@dataclass(frozen=True, slots=True)
class N8nSettings:
    """n8n API and webhook settings."""

    base_url: str
    webhook_url: str
    api_key: str | None = field(default=None, repr=False)
    timeout_seconds: int = 30


@dataclass(frozen=True, slots=True)
class AppSettings:
    """General application settings."""

    environment: str
    debug: bool
    host: str
    port: int
    log_level: str
    output_dir: Path
    data_dir: Path
    knowledge_dir: Path
    prompts_dir: Path
    approval_required: bool


@dataclass(frozen=True, slots=True)
class Settings:
    """Complete Parikzan configuration."""

    app: AppSettings
    ollama: OllamaSettings
    postgres: PostgresSettings
    qdrant: QdrantSettings
    n8n: N8nSettings

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Settings":
        """Build validated settings from environment and optional `.env` file."""
        project_root = Path(
            _env("PARIKZAN_ROOT", default=str(_PACKAGE_ROOT))
        ).expanduser()
        _load_dotenv(env_file or project_root / ".env")

        ollama_base_url = _url(
            _env(
                "OLLAMA_BASE_URL",
                "OPENAI_BASE_URL",
                default="http://localhost:11434/v1",
            ),
            name="OLLAMA_BASE_URL",
            schemes={"http", "https"},
        )
        n8n_base_url = _url(
            _env("N8N_BASE_URL", "N8N_URL", default="http://localhost:5678"),
            name="N8N_BASE_URL",
            schemes={"http", "https"},
        )
        n8n_webhook_url = _url(
            _env("N8N_WEBHOOK_URL", default=f"{n8n_base_url}/webhook"),
            name="N8N_WEBHOOK_URL",
            schemes={"http", "https"},
        )

        app = AppSettings(
            environment=_env("APP_ENV", "ENVIRONMENT", default="development"),
            debug=_env_bool("DEBUG", default=True),
            host=_env("APP_HOST", "HOST", default="127.0.0.1"),
            port=_env_int("APP_PORT", "PORT", default=8000),
            log_level=_env("LOG_LEVEL", default="INFO").upper(),
            output_dir=Path(
                _env("OUTPUT_DIR", default=str(project_root / "output"))
            ).expanduser(),
            data_dir=Path(
                _env("DATA_DIR", default=str(project_root / "data"))
            ).expanduser(),
            knowledge_dir=Path(
                _env("KNOWLEDGE_DIR", default=str(project_root / "knowledge"))
            ).expanduser(),
            prompts_dir=Path(
                _env("PROMPTS_DIR", default=str(project_root / "prompts"))
            ).expanduser(),
            approval_required=_env_bool("APPROVAL_REQUIRED", default=True),
        )

        ollama = OllamaSettings(
            provider=_env("LLM_PROVIDER", default="ollama").lower(),
            base_url=ollama_base_url,
            model=_env("OLLAMA_MODEL", "MODEL", default="qwen3.5:9b"),
            embedding_model=_env(
                "OLLAMA_EMBEDDING_MODEL", default="nomic-embed-text"
            ),
            api_key=_env(
                "OLLAMA_API_KEY",
                "OPENAI_API_KEY",
                default="ollama",
            ),
            timeout_seconds=_env_int("OLLAMA_TIMEOUT_SECONDS", default=120),
        )

        postgres = PostgresSettings(
            url=_env(
                "DATABASE_URL",
                "POSTGRES_URL",
                default="postgresql+psycopg://postgres:password@localhost:5432/postgres",
            ),
            pool_size=_env_int("POSTGRES_POOL_SIZE", default=5),
            max_overflow=_env_int("POSTGRES_MAX_OVERFLOW", default=10),
            timeout_seconds=_env_int("POSTGRES_TIMEOUT_SECONDS", default=30),
        )
        parsed_database_url = urlparse(postgres.url)
        if parsed_database_url.scheme not in {
            "postgresql",
            "postgresql+psycopg",
            "postgres",
        } or not parsed_database_url.netloc:
            raise ValueError(
                "DATABASE_URL must be PostgreSQL URL, "
                f"got {postgres.url!r}"
            )

        qdrant = QdrantSettings(
            url=_url(
                _env("QDRANT_URL", default="http://127.0.0.1:6333"),
                name="QDRANT_URL",
                schemes={"http", "https"},
            ),
            api_key=_env("QDRANT_API_KEY"),
            quiz_collection=_env(
                "QDRANT_QUIZ_COLLECTION",
                default="parikzan_quiz_context",
            ),
            knowledge_collection=_env(
                "QDRANT_KNOWLEDGE_COLLECTION",
                default="parikzan_knowledge",
            ),
            content_collection=_env(
                "QDRANT_CONTENT_COLLECTION",
                default="parikzan_approved_content",
            ),
            timeout_seconds=_env_int("QDRANT_TIMEOUT_SECONDS", default=30),
        )

        n8n = N8nSettings(
            base_url=n8n_base_url,
            webhook_url=n8n_webhook_url,
            api_key=_env("N8N_API_KEY"),
            timeout_seconds=_env_int("N8N_TIMEOUT_SECONDS", default=30),
        )

        return cls(
            app=app,
            ollama=ollama,
            postgres=postgres,
            qdrant=qdrant,
            n8n=n8n,
        )

    @property
    def database_url(self) -> str:
        """Compatibility accessor for database clients."""
        return self.postgres.url

    @property
    def model(self) -> str:
        """Compatibility accessor for LLM clients."""
        return self.ollama.model


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return process-wide validated settings."""
    return Settings.from_env()


settings = get_settings()

__all__ = [
    "AppSettings",
    "N8nSettings",
    "OllamaSettings",
    "PostgresSettings",
    "QdrantSettings",
    "Settings",
    "get_settings",
    "settings",
]

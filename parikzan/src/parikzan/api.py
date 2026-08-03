"""FastAPI service exposing Pydantic AI stages to n8n."""

from __future__ import annotations

import logging
from typing import Any, Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .agent_runtime import BlogAgentRuntime
from .config import settings
from .contracts import BlogJobInput, BlogRuntimeContext


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    decision: Literal["approve", "reject"]
    reviewer: str = Field(min_length=1, max_length=320)
    feedback: str | None = Field(default=None, max_length=2000)


logger = logging.getLogger("parikzan.api")

app = FastAPI(
    title="Parikzan Pydantic AI Runtime",
    version="0.1.0",
    description="Typed Blogging Agent stages orchestrated by n8n.",
)
runtime = BlogAgentRuntime()


def _service_error(error: Exception) -> HTTPException:
    if isinstance(error, ValueError):
        logger.warning("bad request from agent workflow: %s", error)
        return HTTPException(status_code=400, detail=str(error))
    if isinstance(error, PermissionError):
        return HTTPException(status_code=403, detail=str(error))
    logger.error(
        "agent service failure: %s",
        error,
        exc_info=(type(error), error, error.__traceback__),
    )
    return HTTPException(
        status_code=502,
        detail=f"agent service failure: {type(error).__name__}",
    )


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "parikzan-pydantic-ai-runtime",
        "status": "ok",
        "health": "/health",
        "docs": "/docs",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "parikzan-pydantic-ai-runtime",
        "model": settings.ollama.model,
    }


@app.post("/v1/blog/jobs", response_model=BlogRuntimeContext)
def create_blog_job(request: BlogJobInput) -> BlogRuntimeContext:
    try:
        return runtime.create_job(request)
    except Exception as error:  # noqa: BLE001 - convert service errors to HTTP
        raise _service_error(error) from error


@app.post("/v1/blog/outline", response_model=BlogRuntimeContext)
def generate_outline(context: BlogRuntimeContext) -> BlogRuntimeContext:
    try:
        return runtime.outline(context)
    except Exception as error:  # noqa: BLE001 - convert service errors to HTTP
        raise _service_error(error) from error


@app.post("/v1/blog/draft", response_model=BlogRuntimeContext)
def generate_draft(context: BlogRuntimeContext) -> BlogRuntimeContext:
    try:
        return runtime.draft(context)
    except Exception as error:  # noqa: BLE001 - convert service errors to HTTP
        raise _service_error(error) from error


@app.post("/v1/blog/seo", response_model=BlogRuntimeContext)
def generate_seo(context: BlogRuntimeContext) -> BlogRuntimeContext:
    try:
        return runtime.seo(context)
    except Exception as error:  # noqa: BLE001 - convert service errors to HTTP
        raise _service_error(error) from error


@app.post("/v1/blog/validate", response_model=BlogRuntimeContext)
def validate_blog(context: BlogRuntimeContext) -> BlogRuntimeContext:
    try:
        return runtime.validate(context)
    except Exception as error:  # noqa: BLE001 - convert service errors to HTTP
        raise _service_error(error) from error


@app.post("/v1/blog/revise", response_model=BlogRuntimeContext)
def revise_blog(context: BlogRuntimeContext) -> BlogRuntimeContext:
    try:
        return runtime.revise(context)
    except Exception as error:  # noqa: BLE001 - convert service errors to HTTP
        raise _service_error(error) from error


@app.post("/v1/blog/approval/request")
def request_approval(context: BlogRuntimeContext) -> dict[str, Any]:
    try:
        return runtime.request_approval(context)
    except Exception as error:  # noqa: BLE001 - convert service errors to HTTP
        raise _service_error(error) from error


@app.post("/v1/blog/approval/decide")
def decide_approval(decision: ApprovalDecision) -> dict[str, Any]:
    try:
        return runtime.decide_approval(**decision.model_dump())
    except Exception as error:  # noqa: BLE001 - convert service errors to HTTP
        raise _service_error(error) from error


@app.post("/v1/blog/publish")
def publish_blog(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return runtime.publish(payload)
    except Exception as error:  # noqa: BLE001 - convert service errors to HTTP
        raise _service_error(error) from error


@app.post("/v1/blog/index")
def index_blog(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return runtime.index(payload)
    except Exception as error:  # noqa: BLE001 - convert service errors to HTTP
        raise _service_error(error) from error


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "parikzan.api:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=settings.app.debug,
    )

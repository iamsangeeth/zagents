#!/usr/bin/env python3
"""Run local Parikzan MVP smoke checks without generating content."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from parikzan.clients import OllamaClient, PostgresClient, QdrantClient, QdrantError, build_agent  # noqa: E402
from parikzan.config import settings  # noqa: E402


REQUIRED_TABLES = {
    "agent_events",
    "approvals",
    "content_artifacts",
    "content_job_sources",
    "content_jobs",
    "content_sources",
}


class SmokeOutput(BaseModel):
    ok: bool


def main() -> int:
    failures: list[str] = []

    def check(name: str, function, *, optional: bool = False) -> None:
        try:
            result = function()
        except Exception as error:  # noqa: BLE001 - smoke runner reports status
            if optional:
                print(f"[warn] {name}: unavailable ({type(error).__name__})")
            else:
                failures.append(name)
                print(f"[fail] {name}: {type(error).__name__}")
            return
        suffix = f" ({result})" if result is not None else ""
        print(f"[ok] {name}{suffix}")

    check("config", lambda: f"provider={settings.ollama.provider}")
    check(
        "PydanticAI agent construction",
        lambda: build_agent(
            SmokeOutput,
            name="mvp-smoke-agent",
            system_prompt="Return valid output.",
        ).name,
    )

    def postgres_check() -> str:
        row = PostgresClient().fetch_one("SELECT 1 AS ok")
        if row != {"ok": 1}:
            raise RuntimeError("SELECT 1 returned unexpected result")
        rows = PostgresClient().fetch_all(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = ANY(%s)
            """,
            (list(REQUIRED_TABLES),),
        )
        found = {row["table_name"] for row in rows}
        missing = REQUIRED_TABLES - found
        if missing:
            raise RuntimeError(f"missing tables: {sorted(missing)}")
        return f"{len(found)} schema tables"

    check("PostgreSQL", postgres_check)
    check("Ollama", lambda: f"{len(OllamaClient().health())} models visible")
    check("Qdrant", lambda: QdrantClient().health(), optional=True)

    def workflow_check() -> str:
        paths = [
            ROOT / "workflows" / "blogging_agent_v1.json",
            ROOT / "workflows" / "blogging_approval_v1.json",
        ]
        for path in paths:
            document = json.loads(path.read_text(encoding="utf-8"))
            if not document.get("nodes") or not document.get("connections"):
                raise RuntimeError(f"invalid workflow graph: {path.name}")
        return "2 workflow graphs"

    check("n8n workflow JSON", workflow_check)
    check(
        "prompt and knowledge files",
        lambda: "6 prompts + 4 knowledge files"
        if all(
            (ROOT / "prompts" / "blogging" / "v1" / name).is_file()
            for name in ("system.md", "outline.md", "draft.md", "seo.md", "validate.md", "revise.md")
        )
        and all(
            (ROOT / "knowledge" / name).is_file()
            for name in ("PRODUCT.md", "PRICING_FAQ.md", "API.md", "CONTENT_GUIDELINES.md")
        )
        else (_ for _ in ()).throw(FileNotFoundError("prompt or knowledge file missing")),
    )

    if failures:
        print(f"MVP smoke: FAILED ({', '.join(failures)})")
        return 1
    print("MVP smoke: PASS (Qdrant may remain warning-only until service is healthy)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

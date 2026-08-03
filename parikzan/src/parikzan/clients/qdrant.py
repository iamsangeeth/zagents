"""Minimal Qdrant REST client with no SDK coupling."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from ..config import QdrantSettings, settings


class QdrantError(RuntimeError):
    """Qdrant request failure."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class QdrantClient:
    """Synchronous Qdrant REST client for retrieval and indexing tools."""

    def __init__(self, config: QdrantSettings | None = None) -> None:
        self.config = config or settings.qdrant

    def _request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.config.api_key:
            headers["api-key"] = self.config.api_key

        request = Request(
            f"{self.config.url}/{path.lstrip('/')}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                response_body = response.read()
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise QdrantError(
                f"Qdrant {method} {path} failed: {detail}",
                status_code=error.code,
            ) from error
        except URLError as error:
            raise QdrantError(f"Qdrant {method} {path} unreachable: {error.reason}") from error
        except OSError as error:
            raise QdrantError(f"Qdrant {method} {path} transport failure: {error}") from error

        if not response_body:
            return {}
        decoded = json.loads(response_body)
        if not isinstance(decoded, dict):
            raise QdrantError(f"Qdrant returned unexpected response for {path}")
        return decoded

    def health(self) -> dict[str, Any]:
        """Return Qdrant root health response."""
        return self._request("GET", "/")

    def collection_exists(self, collection: str) -> bool:
        """Return whether collection exists."""
        path = f"/collections/{quote(collection, safe='')}"
        try:
            self._request("GET", path)
        except QdrantError as error:
            if error.status_code == 404:
                return False
            raise
        return True

    def ensure_collection(
        self,
        collection: str,
        *,
        vector_size: int,
        distance: str = "Cosine",
    ) -> bool:
        """Create collection when missing; return true when created."""
        if self.collection_exists(collection):
            return False
        path = f"/collections/{quote(collection, safe='')}"
        self._request(
            "PUT",
            path,
            {"vectors": {"size": vector_size, "distance": distance}},
        )
        return True

    def upsert_points(
        self,
        collection: str,
        points: Sequence[Mapping[str, Any]],
        *,
        wait: bool = True,
    ) -> dict[str, Any]:
        """Upsert vectors and payloads into collection."""
        path = f"/collections/{quote(collection, safe='')}/points?wait={str(wait).lower()}"
        return self._request("PUT", path, {"points": list(points)})

    def query(
        self,
        collection: str,
        vector: Sequence[float],
        *,
        limit: int = 5,
        score_threshold: float | None = None,
        query_filter: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return nearest points from Qdrant query endpoint."""
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        payload: dict[str, Any] = {
            "query": list(vector),
            "limit": limit,
            "with_payload": True,
        }
        if score_threshold is not None:
            payload["score_threshold"] = score_threshold
        if query_filter is not None:
            payload["filter"] = dict(query_filter)

        path = f"/collections/{quote(collection, safe='')}/points/query"
        response = self._request("POST", path, payload)
        result = response.get("result", [])
        if isinstance(result, dict):
            result = result.get("points", [])
        return list(result)

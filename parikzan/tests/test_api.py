from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from parikzan.api import app


class ApiTests(unittest.TestCase):
    def test_health(self) -> None:
        response = TestClient(app).get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_n8n_routes_exist(self) -> None:
        routes = {route.path for route in app.routes}
        expected = {
            "/v1/blog/jobs",
            "/v1/blog/outline",
            "/v1/blog/draft",
            "/v1/blog/seo",
            "/v1/blog/validate",
            "/v1/blog/revise",
            "/v1/blog/approval/request",
            "/v1/blog/approval/decide",
            "/v1/blog/publish",
            "/v1/blog/index",
        }
        self.assertTrue(expected.issubset(routes))


if __name__ == "__main__":
    unittest.main()

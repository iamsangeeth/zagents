from __future__ import annotations

import unittest
from uuid import uuid4

from parikzan.observability import MetricsRecorder


class FakeDatabase:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def record_event(self, **kwargs):
        self.events.append(kwargs)
        return uuid4()

    def job_metrics(self, job_id):
        return {"event_count": len(self.events), "job_id": job_id}


class ObservabilityTests(unittest.TestCase):
    def test_event_redacts_secret_and_bounds_text(self) -> None:
        database = FakeDatabase()
        recorder = MetricsRecorder(database)
        job_id = uuid4()
        recorder.event(
            job_id=job_id,
            event_type="model_call",
            payload={
                "api_key": "do-not-store",
                "prompt": "x" * 1200,
            },
        )
        payload = database.events[0]["payload"]
        self.assertEqual(payload["api_key"], "[REDACTED]")
        self.assertEqual(len(payload["prompt"]), 1001)

    def test_observe_step_records_success_and_error(self) -> None:
        database = FakeDatabase()
        recorder = MetricsRecorder(database)
        job_id = uuid4()
        with recorder.observe_step(job_id=job_id, step="outline"):
            pass
        with self.assertRaises(RuntimeError):
            with recorder.observe_step(job_id=job_id, step="draft"):
                raise RuntimeError("expected")
        self.assertEqual(
            [event["event_type"] for event in database.events],
            ["step_completed", "error"],
        )
        self.assertEqual(database.events[1]["payload"]["error_type"], "RuntimeError")


if __name__ == "__main__":
    unittest.main()

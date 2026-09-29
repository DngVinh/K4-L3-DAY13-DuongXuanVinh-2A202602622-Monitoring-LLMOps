from __future__ import annotations

import asyncio
import json

import httpx

from app import logging_config
from app.main import app
from app.pii import hash_user_id


def test_request_ids_and_user_context_do_not_leak(monkeypatch, tmp_path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    async def requests():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            first = await client.post(
                "/chat", headers={"x-request-id": "lab-01"},
                json={"user_id": "student-a", "session_id": "s-a", "feature": "qa", "message": "Explain traces"},
            )
            second = await client.post(
                "/chat", headers={"x-request-id": "student@example.org"},
                json={"user_id": "student-b", "session_id": "s-b", "feature": "qa", "message": "Explain logs"},
            )
            return first, second

    first, second = asyncio.run(requests())
    assert first.headers["x-request-id"] == "lab-01"
    assert second.headers["x-request-id"].startswith("req-")
    assert len(second.headers["x-request-id"]) == 12
    assert float(first.headers["x-response-time-ms"]) > 0

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    received = [record for record in records if record["event"] == "request_received"]
    assert [(record["correlation_id"], record["user_id_hash"]) for record in received] == [
        ("lab-01", hash_user_id("student-a")),
        (second.headers["x-request-id"], hash_user_id("student-b")),
    ]
    assert "student@example.org" not in log_path.read_text(encoding="utf-8")

from __future__ import annotations

from contextlib import contextmanager

from app import agent as agent_module


class ChildObservation:
    def __init__(self, name: str, kind: str, parent: str, initial: dict) -> None:
        self.name = name
        self.kind = kind
        self.parent = parent
        self.initial = initial
        self.updates: list[dict] = []

    def update(self, **kwargs) -> None:
        self.updates.append(kwargs)


class RecordingClient:
    def __init__(self) -> None:
        self.children: list[ChildObservation] = []
        self.active = "lab-agent-run"

    @contextmanager
    def start_as_current_observation(self, *, name, as_type, **kwargs):
        child = ChildObservation(name, as_type, self.active, kwargs)
        self.children.append(child)
        previous = self.active
        self.active = name
        try:
            yield child
        finally:
            self.active = previous

    def update_current_span(self, **kwargs):
        pass


def test_retrieval_and_generation_are_children_with_usage_and_no_raw_io(monkeypatch) -> None:
    client = RecordingClient()
    monkeypatch.setattr(agent_module, "get_langfuse_client", lambda: client)
    monkeypatch.setattr(agent_module, "tracing_enabled", lambda: True)
    monkeypatch.setattr(agent_module, "resolve_prompt", lambda *args, **kwargs: type(
        "Prompt", (), {
            "text": "safe prompt", "name": "day13-chat", "label": "production",
            "version": "1", "source": "langfuse", "fetch_error": None,
            "managed_prompt": None,
        }
    )())

    @contextmanager
    def attributes(**kwargs):
        yield

    monkeypatch.setattr(agent_module, "propagate_attributes", attributes)
    agent = agent_module.LabAgent()
    result = agent_module.LabAgent.run.__wrapped__(
        agent, user_id="student", feature="qa", session_id="demo",
        message="Explain traces", correlation_id="req-12345678",
    )

    assert [(child.name, child.kind, child.parent) for child in client.children] == [
        ("retrieval", "retriever", "lab-agent-run"),
        ("fake-llm", "generation", "lab-agent-run"),
    ]
    generation = client.children[1].updates[0]
    assert generation["usage_details"] == {
        "input": result.tokens_in, "output": result.tokens_out,
    }
    assert generation["cost_details"]["total"] == result.cost_usd
    assert all("input" not in child.initial and "output" not in child.initial for child in client.children)

"""End-to-end smoke test: the graph compiles and runs with stubbed AWS + LLM.

No AWS account and no ANTHROPIC_API_KEY required — the AWS adapter is a stub with
recorded-style responses, and the LLM factory returns deterministic objects. This
exercises the planner → fan-out → gather → code → critic → synthesizer wiring and
asserts a well-formed IncidentReport comes out.
"""

from __future__ import annotations

from copilot.deps import Deps
from copilot.graph import build_graph
from copilot.state import (
    Critique,
    IncidentReport,
    InvestigationThread,
    PlannerOutput,
)


class _FakeStructured:
    """Returned by FakeLLM.with_structured_output — yields a canned model instance."""

    def __init__(self, model_cls):
        self._model_cls = model_cls

    def invoke(self, _messages):
        if self._model_cls is PlannerOutput:
            return PlannerOutput(
                service="api-prod",
                window_minutes=20,
                threads=[
                    InvestigationThread(source="logs", rationale="pull errors", params={"log_group": "/ecs/api-prod"}),
                    InvestigationThread(source="metrics", rationale="check CPU"),
                    InvestigationThread(source="rag", rationale="match runbook"),
                ],
            )
        if self._model_cls is Critique:
            return Critique(primary_cause="N+1 query introduced in last deploy", confidence=0.91, notes="logs + metrics + deploy timeline agree")
        if self._model_cls is IncidentReport:
            return IncidentReport(
                root_cause="Inefficient DB query (N+1) introduced in the last deploy caused CPU exhaustion.",
                evidence_refs=["logs: repeated slow queries", "metrics: CPU peak 94%"],
                recommended_fix="Add .select_related() to the /users endpoint and scale ECS task count to 4.",
                confidence=0.91,
                commands_to_run=["aws ecs update-service --service api-prod --desired-count 4"],
            )
        raise AssertionError(f"unexpected structured model: {self._model_cls}")


class _Msg:
    def __init__(self, content: str):
        self.content = content


class _FakeLLM:
    def __init__(self, model: str):
        self.model = model

    def with_structured_output(self, model_cls):
        return _FakeStructured(model_cls)

    def invoke(self, _messages):
        return _Msg("Repeated database timeout signatures consistent with an N+1 query regression.")


def _fake_llm_factory(model="claude-opus-4-8", max_tokens=8000, thinking=False, timeout=120):
    return _FakeLLM(model)


class _StubAws:
    def logs_insights(self, log_group, window_minutes, **_):
        return [{"@message": "ERROR db query timeout after 5000ms"} for _ in range(12)]

    def metric_series(self, service, cluster, window_minutes, **_):
        return {"cpu": [70, 88, 94, 91], "mem": [60, 80, 87, 85]}

    def describe_service(self, service, cluster):
        return {"serviceName": service, "desiredCount": 2}


def test_graph_produces_report():
    deps = Deps(aws=_StubAws(), llm=_fake_llm_factory, allow_code_exec=False)
    graph = build_graph(deps)

    result = graph.invoke({"incident": "ECS service api-prod has been returning 503s for 20 minutes"})

    report = result["report"]
    assert isinstance(report, IncidentReport)
    assert report.confidence == 0.91
    assert "select_related" in report.recommended_fix
    # planner picked logs+metrics+rag; each should have appended evidence
    sources = {e.source for e in result["evidence"]}
    assert {"logs", "metrics", "rag"} <= sources

"""End-to-end smoke test: the graph compiles and runs with stubbed AWS + LLM.

No AWS account and no ANTHROPIC_API_KEY required — the AWS investigator is an
injected stub (so the MCP subprocess and a tool-using model are never touched), and
the LLM factory returns deterministic objects. This exercises the
planner → fan-out → gather → code → critic → synthesizer wiring and asserts a
well-formed IncidentReport comes out.
"""

from __future__ import annotations

import asyncio

from copilot.deps import Deps
from copilot.graph import build_graph
from copilot.state import (
    Critique,
    Evidence,
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
                    InvestigationThread(source="aws", rationale="inspect logs + metrics"),
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


async def _stub_investigate(state, deps):
    """Stand-in for the MCP-backed AWS agent — canned read-only findings."""
    return [
        Evidence(source="aws", summary="Repeated DB query timeouts in CloudWatch Logs.", severity="critical"),
        Evidence(source="aws", summary="ECS CPU: avg 88%, peak 94%.", severity="critical"),
    ]


def test_graph_produces_report():
    deps = Deps(llm=_fake_llm_factory, allow_code_exec=False, aws_investigator=_stub_investigate)
    graph = build_graph(deps)

    result = asyncio.run(
        graph.ainvoke({"incident": "ECS service api-prod has been returning 503s for 20 minutes"})
    )

    report = result["report"]
    assert isinstance(report, IncidentReport)
    assert report.confidence == 0.91
    assert "select_related" in report.recommended_fix
    # planner picked aws + rag; each should have appended evidence
    sources = {e.source for e in result["evidence"]}
    assert {"aws", "rag"} <= sources

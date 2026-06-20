"""CloudWatch Logs node — pull recent errors and summarize the signature."""

from __future__ import annotations

from ..deps import Deps
from ..llm import SONNET
from ..state import Evidence, State

LOGS_SYS = """You analyze raw CloudWatch error log lines for an incident.
Identify the dominant recurring error signature(s) and state, in 2-3 sentences,
what they suggest about the failure (e.g. DB timeouts, OOM, upstream 5xx). Be
concrete; do not speculate beyond the lines provided."""


def _log_group_for(state: State) -> str | None:
    for t in state.get("threads", []):
        if t.source == "logs" and t.params.get("log_group"):
            return t.params["log_group"]
    svc = state.get("service")
    return f"/ecs/{svc}" if svc else None


def make_logs_node(deps: Deps):
    def run(state: State) -> dict:
        log_group = _log_group_for(state)
        if not log_group:
            return {"evidence": [Evidence(source="logs", summary="No log group resolved.", severity="info")]}

        try:
            rows = deps.aws.logs_insights(log_group, state.get("window_minutes", 30))
        except Exception as e:  # noqa: BLE001 - surface as evidence, never crash the run
            return {"evidence": [Evidence(source="logs", summary=f"Logs query failed: {e}", severity="warning")]}

        if not rows:
            return {"evidence": [Evidence(source="logs", summary="No matching error logs in window.", severity="info")]}

        messages = "\n".join(r.get("@message", "") for r in rows[:80])
        llm = deps.llm(SONNET, max_tokens=1200)
        summary = llm.invoke([("system", LOGS_SYS), ("human", messages)]).content
        return {
            "evidence": [
                Evidence(
                    source="logs",
                    summary=str(summary),
                    detail=f"{len(rows)} matching lines from {log_group}",
                    severity="critical",
                )
            ]
        }

    return run

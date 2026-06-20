"""Planner node — decomposes the incident into investigation threads.

Opus, structured output. The system prompt is the large stable prefix (good for
prompt caching); the volatile incident text is the human turn after it.
"""

from __future__ import annotations

from ..deps import Deps
from ..llm import OPUS
from ..state import PlannerOutput, State

PLANNER_SYS = """You are the lead incident planner for an AWS DevOps copilot.

Given a one-line incident description, decide which evidence sources to investigate
and produce 2-5 concrete investigation threads. Available sources:
  - logs:    CloudWatch Logs Insights over the service's log group.
  - metrics: CloudWatch metrics (CPU, memory, request count, 5xx).
  - github:  diff of the most recent deploy against the previous one.
  - rag:     retrieve matching runbooks for the symptom.

Extract the service name and a lookback window in minutes from the description
(default 30 minutes if unstated). For each thread, give a short rationale and any
useful params (e.g. {"log_group": "/ecs/api-prod"}, {"metrics": ["CPUUtilization"]}).
Prefer logs + metrics for latency/error incidents; add github when a recent deploy
is plausibly involved; always include rag.
"""


def make_planner(deps: Deps):
    def plan(state: State) -> dict:
        llm = deps.llm(OPUS, max_tokens=4000).with_structured_output(PlannerOutput)
        out: PlannerOutput = llm.invoke(
            [("system", PLANNER_SYS), ("human", state["incident"])]
        )
        return {
            "service": out.service,
            "window_minutes": out.window_minutes,
            "threads": out.threads,
        }

    return plan

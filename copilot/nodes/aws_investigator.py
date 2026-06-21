"""AWS investigator node — a read-only, tool-using agent over the live AWS API.

Replaces the old fixed logs + metrics boto3 calls. The agent is handed the incident
and the AWS API MCP tools (read-only) and decides which AWS calls to make —
CloudWatch logs/metrics, ECS, ELB, RDS, whatever the symptom warrants — then
returns concrete findings as ``Evidence``. Any failure (no creds, the MCP server
won't start, a local model that can't drive the tools) surfaces as a warning
``Evidence`` rather than crashing the run.

The real work lives in ``_default_investigate``; ``Deps.aws_investigator`` can
override it so tests run without launching the MCP subprocess or a tool-using LLM.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..deps import Deps
from ..llm import OPUS
from ..state import Evidence, State

INVESTIGATOR_SYS = """You are an AWS incident investigator with READ-ONLY access to \
the live AWS account through the `call_aws` tool, which runs AWS CLI commands. \
Investigate the incident and gather concrete evidence.

Look at whatever is relevant: CloudWatch Logs for error/timeout signatures, \
CloudWatch metrics for CPU/memory/5xx, ECS service and task health and events, \
load balancer target health, RDS status, recent changes. Run as many read-only \
commands as you need; prefer specific queries over broad listings. Every operation \
is read-only — never attempt to change anything.

When you have enough signal, stop and report your findings as a list of distinct, \
concrete observations, each with a severity (info / warning / critical)."""


class Finding(BaseModel):
    summary: str = Field(description="One concrete observation, stated plainly.")
    severity: Literal["info", "warning", "critical"] = "info"
    detail: str = ""


class AwsFindings(BaseModel):
    findings: list[Finding] = Field(default_factory=list)


def _prompt(state: State) -> str:
    parts = [f"Incident: {state['incident']}"]
    if state.get("service"):
        parts.append(f"Service: {state['service']}")
    parts.append(f"Lookback window: {state.get('window_minutes', 30)} minutes")
    return "\n".join(parts)


async def _default_investigate(state: State, deps: Deps) -> list[Evidence]:
    """Real path: drive the read-only AWS API MCP tools with a ReAct agent."""
    from langgraph.prebuilt import create_react_agent

    from ..aws.mcp import tools_session

    async with tools_session(region=deps.aws_region, profile=deps.aws_profile) as tools:
        llm = deps.llm(OPUS, max_tokens=4000)
        agent = create_react_agent(llm, tools, prompt=INVESTIGATOR_SYS, response_format=AwsFindings)
        result = await agent.ainvoke(
            {"messages": [("human", _prompt(state))]},
            config={"recursion_limit": 24},
        )

    structured = result.get("structured_response")
    if isinstance(structured, AwsFindings) and structured.findings:
        return [
            Evidence(source="aws", summary=f.summary, detail=f.detail, severity=f.severity)
            for f in structured.findings
        ]

    # No structured output (e.g. a weaker local model) — wrap the final message.
    messages = result.get("messages") or []
    text = getattr(messages[-1], "content", "") if messages else ""
    return [Evidence(source="aws", summary=str(text) or "No AWS findings.", severity="info")]


def make_aws_investigator(deps: Deps):
    investigate = deps.aws_investigator or _default_investigate

    async def run(state: State) -> dict:
        try:
            evidence = await investigate(state, deps)
        except Exception as e:  # noqa: BLE001 - surface as evidence, never crash the run
            return {
                "evidence": [
                    Evidence(source="aws", summary=f"AWS investigation failed: {e}", severity="warning")
                ]
            }
        return {"evidence": evidence or [Evidence(source="aws", summary="No AWS findings.", severity="info")]}

    return run

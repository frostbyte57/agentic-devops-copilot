"""Shared graph state and the Pydantic models that flow through it.

The `State` TypedDict is what LangGraph threads node-to-node. `evidence` uses an
additive reducer so the parallel specialist branches can each append findings
without clobbering one another.
"""

from __future__ import annotations

import operator
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field
from typing_extensions import TypedDict

Source = Literal["aws", "github", "rag"]


class InvestigationThread(BaseModel):
    """One line of inquiry the planner wants pursued."""

    source: Source
    rationale: str = Field(description="Why this source is worth querying for this incident.")
    params: dict = Field(default_factory=dict, description="Source-specific query params.")


class PlannerOutput(BaseModel):
    """Structured planner result: the parsed incident plus the chosen threads."""

    service: Optional[str] = Field(default=None, description="The AWS/ECS service name in question.")
    window_minutes: int = Field(default=30, description="Lookback window for the investigation.")
    threads: list[InvestigationThread] = Field(default_factory=list)


class Evidence(BaseModel):
    """A single finding produced by a specialist node."""

    source: str
    summary: str
    detail: str = ""
    severity: Literal["info", "warning", "critical"] = "info"


class Hypothesis(BaseModel):
    statement: str
    supporting_evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class Critique(BaseModel):
    """The critic's challenge to the leading hypothesis."""

    primary_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str = ""


class IncidentReport(BaseModel):
    """The final synthesized answer rendered to the user."""

    root_cause: str
    evidence_refs: list[str] = Field(default_factory=list)
    recommended_fix: str
    confidence: float = Field(ge=0.0, le=1.0)
    commands_to_run: list[str] = Field(default_factory=list)


class State(TypedDict, total=False):
    incident: str
    service: Optional[str]
    window_minutes: int
    threads: list[InvestigationThread]
    evidence: Annotated[list[Evidence], operator.add]
    hypotheses: list[Hypothesis]
    critique: Optional[Critique]
    report: Optional[IncidentReport]

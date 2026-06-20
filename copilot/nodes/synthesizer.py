"""Synthesizer node — emit the final IncidentReport.

Opus, structured output. Consumes the evidence plus the critic's verdict and
produces the user-facing report: root cause, the evidence it rests on, a concrete
fix, a confidence (anchored to the critic's), and any commands to run.
"""

from __future__ import annotations

from ..deps import Deps
from ..llm import OPUS
from ..state import Critique, Evidence, IncidentReport, State

SYNTH_SYS = """You write the final incident report for an on-call engineer. Use the
evidence and the critic's verdict. State a single clear root cause, list the
specific evidence it rests on, give a concrete recommended fix, and include any
exact commands or code changes (e.g. add an index, '.select_related()', scale ECS
task count). Set confidence consistent with the critic. Be precise and actionable."""


def _fallback_report(evidence: list[Evidence], critique: Critique | None) -> IncidentReport:
    """Best-effort report from raw evidence when structured synthesis is unavailable.

    Local models without reliable tool-calling can fail ``with_structured_output``;
    rather than dropping the whole investigation, surface what we already gathered.
    """
    ranked = [e for e in evidence if e.severity == "critical"] + [
        e for e in evidence if e.severity == "warning"
    ]
    top = ranked or evidence
    root = (critique.primary_cause if critique else "") or (
        top[0].summary if top else "Insufficient evidence to determine a root cause."
    )
    return IncidentReport(
        root_cause=root,
        evidence_refs=[f"{e.source}: {e.summary}" for e in ranked][:6],
        recommended_fix=(
            critique.notes if critique and critique.notes else
            "Review the cited evidence below — the model could not produce a structured "
            "synthesis (try a model with reliable tool-calling, e.g. Anthropic)."
        ),
        confidence=critique.confidence if critique else (0.4 if top else 0.1),
        commands_to_run=[],
    )


def make_synthesizer(deps: Deps):
    def run(state: State) -> dict:
        evidence = state.get("evidence", [])
        critique = state.get("critique")
        context = "\n".join(f"[{e.source}/{e.severity}] {e.summary}" for e in evidence) or "(no evidence)"
        critic_text = (
            f"Primary cause: {critique.primary_cause} (confidence {critique.confidence:.2f})\n{critique.notes}"
            if critique
            else "(no critique)"
        )
        llm = deps.llm(OPUS, max_tokens=2500).with_structured_output(IncidentReport)
        try:
            report = llm.invoke(
                [
                    ("system", SYNTH_SYS),
                    ("human", f"Incident: {state['incident']}\n\nEvidence:\n{context}\n\nCritic:\n{critic_text}"),
                ]
            )
        except Exception:  # noqa: BLE001 — structured output can fail on local models
            report = None
        if not isinstance(report, IncidentReport):
            report = _fallback_report(evidence, critique)
        return {"report": report}

    return run

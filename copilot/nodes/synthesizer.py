"""Synthesizer node — emit the final IncidentReport.

Opus, structured output. Consumes the evidence plus the critic's verdict and
produces the user-facing report: root cause, the evidence it rests on, a concrete
fix, a confidence (anchored to the critic's), and any commands to run.
"""

from __future__ import annotations

from ..deps import Deps
from ..llm import OPUS
from ..state import IncidentReport, State

SYNTH_SYS = """You write the final incident report for an on-call engineer. Use the
evidence and the critic's verdict. State a single clear root cause, list the
specific evidence it rests on, give a concrete recommended fix, and include any
exact commands or code changes (e.g. add an index, '.select_related()', scale ECS
task count). Set confidence consistent with the critic. Be precise and actionable."""


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
        report: IncidentReport = llm.invoke(
            [
                ("system", SYNTH_SYS),
                ("human", f"Incident: {state['incident']}\n\nEvidence:\n{context}\n\nCritic:\n{critic_text}"),
            ]
        )
        return {"report": report}

    return run

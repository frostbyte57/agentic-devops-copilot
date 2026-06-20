"""Critic node — challenge the leading hypothesis and set a calibrated confidence.

Opus, structured output. Deliberately adversarial: it argues against the obvious
cause before settling on one, so the synthesizer doesn't anchor on the first
strong-sounding signal.
"""

from __future__ import annotations

from ..deps import Deps
from ..llm import OPUS
from ..state import Critique, State

CRITIC_SYS = """You are a skeptical incident reviewer. Given the collected evidence,
identify the single most likely primary root cause. First argue against the most
obvious explanation, then commit to the best-supported one. Assign a calibrated
confidence in [0,1]: high only when multiple independent sources agree and the
timeline lines up; lower when evidence is thin or circumstantial."""


def make_critic(deps: Deps):
    def run(state: State) -> dict:
        evidence = state.get("evidence", [])
        context = "\n".join(f"[{e.source}/{e.severity}] {e.summary}" for e in evidence) or "(no evidence)"
        llm = deps.llm(OPUS, max_tokens=2000).with_structured_output(Critique)
        try:
            critique = llm.invoke(
                [("system", CRITIC_SYS), ("human", f"Incident: {state['incident']}\n\nEvidence:\n{context}")]
            )
        except Exception:  # noqa: BLE001 — local models may not return valid structured output
            critique = None
        # The synthesizer handles a missing critique; don't let a bad parse kill the run.
        return {"critique": critique if isinstance(critique, Critique) else None}

    return run

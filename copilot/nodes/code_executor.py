"""Code-executor node — quantify a hypothesis with a tiny generated script.

The model is asked to emit a single self-contained Python script (no network, no
imports beyond the stdlib) that estimates something the evidence can't state
directly — e.g. query volume per request. We run it in the sandbox and feed stdout
back as evidence. Skipped entirely when ``deps.allow_code_exec`` is False or there
is no critical/warning evidence worth quantifying.
"""

from __future__ import annotations

import re

from ..deps import Deps
from ..llm import OPUS
from ..state import Evidence, State
from ..sandbox import run_script

CODE_SYS = """You write a SINGLE self-contained Python 3 script to quantify one
aspect of an incident (for example: estimate DB queries per request, or project
CPU headroom at a given task count). Rules:
- standard library only; NO network, NO file or environment access.
- print a concise numeric result with a one-line label to stdout.
- keep it short and deterministic.
Return ONLY the code, optionally in a ```python fenced block."""

_FENCE = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL)


def _extract_code(text: str) -> str:
    m = _FENCE.search(text)
    return (m.group(1) if m else text).strip()


def make_code_executor(deps: Deps):
    def run(state: State) -> dict:
        if not deps.allow_code_exec:
            return {}
        significant = [e for e in state.get("evidence", []) if e.severity in ("warning", "critical")]
        if not significant:
            return {}

        context = "\n".join(f"[{e.source}] {e.summary}" for e in significant)
        prompt = f"Incident: {state['incident']}\n\nEvidence:\n{context}\n\nWrite a script to quantify the most load-bearing hypothesis."
        code = _extract_code(str(deps.llm(OPUS, max_tokens=1500).invoke(
            [("system", CODE_SYS), ("human", prompt)]
        ).content))

        result = run_script(code)
        if result.ok and result.stdout.strip():
            return {"evidence": [Evidence(source="code", summary=result.stdout.strip(), detail="generated analysis script", severity="info")]}
        return {"evidence": [Evidence(source="code", summary="Analysis script produced no usable result.", detail=result.stderr, severity="info")]}

    return run

"""RAG node — retrieve runbook chunks matching the incident symptom.

v1 uses a dependency-free keyword/overlap retriever over the markdown runbooks so
the tool runs with no extra infra or an embeddings provider. The plan calls for
swapping this for a Chroma/FAISS vector store; the retrieval interface
(``retrieve(query) -> list[(title, text, score)]``) is what the synthesizer
consumes, so that upgrade is local to this file.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..deps import Deps
from ..state import Evidence, State

_WORD = re.compile(r"[a-z0-9]+")


def _runbooks_dir(deps: Deps) -> Path:
    if deps.runbooks_dir:
        return Path(deps.runbooks_dir)
    return Path(__file__).resolve().parent.parent / "runbooks"


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def _retrieve(query: str, directory: Path, k: int = 2) -> list[tuple[str, str, float]]:
    q = _tokens(query)
    if not q:
        return []
    scored: list[tuple[str, str, float]] = []
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        overlap = len(q & _tokens(text))
        if overlap:
            scored.append((path.stem, text, overlap / len(q)))
    scored.sort(key=lambda x: x[2], reverse=True)
    return scored[:k]


def make_rag_node(deps: Deps):
    def run(state: State) -> dict:
        directory = _runbooks_dir(deps)
        if not directory.is_dir():
            return {"evidence": [Evidence(source="rag", summary="No runbook corpus found.", severity="info")]}

        hits = _retrieve(state["incident"], directory)
        if not hits:
            return {"evidence": [Evidence(source="rag", summary="No matching runbook.", severity="info")]}

        ev = [
            Evidence(
                source="rag",
                summary=f"Runbook '{title}' (match {score:.0%})",
                detail=text[:1500],
                severity="info",
            )
            for title, text, score in hits
        ]
        return {"evidence": ev}

    return run

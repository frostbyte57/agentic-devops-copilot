"""Runtime dependencies injected into the graph.

Keeping the AWS layer and the LLM factory in a single ``Deps`` object (rather than
importing globals inside nodes) is what makes the graph testable: the smoke test
passes a stub ``aws`` adapter and a fake ``llm`` factory, and nothing in the node
code changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .llm import make_llm


@dataclass
class Deps:
    aws: Any
    """An AwsAdapters instance (or a stub exposing the same methods)."""

    llm: Callable[..., Any] = make_llm
    """LLM factory; signature matches ``llm.make_llm``."""

    allow_code_exec: bool = True
    """When False, the code-executor node is skipped entirely."""

    runbooks_dir: str | None = None
    """Override for the runbook corpus directory (defaults to the packaged one)."""

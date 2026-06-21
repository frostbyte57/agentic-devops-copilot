"""Runtime dependencies injected into the graph.

Keeping the AWS config and the LLM factory in a single ``Deps`` object (rather than
importing globals inside nodes) is what makes the graph testable: the smoke test
passes a fake ``llm`` factory and an ``aws_investigator`` override, and nothing in
the node code changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from .llm import make_llm


@dataclass
class Deps:
    llm: Callable[..., Any] = make_llm
    """LLM factory; signature matches ``llm.make_llm``."""

    allow_code_exec: bool = True
    """When False, the code-executor node is skipped entirely."""

    runbooks_dir: str | None = None
    """Override for the runbook corpus directory (defaults to the packaged one)."""

    github_token: str | None = None
    """GitHub token for the deploy-diff node (from the UI settings store)."""

    github_repo: str | None = None
    """``owner/repo`` for the deploy-diff node (from the UI settings store)."""

    aws_region: str | None = None
    """AWS region for the read-only MCP server (defaults to the UI settings store)."""

    aws_profile: str | None = None
    """AWS shared profile for the MCP server (CLI override; falls back to creds/chain)."""

    aws_investigator: Optional[Callable[..., Awaitable[list]]] = None
    """Override for the AWS investigation coroutine ``(state, deps) -> list[Evidence]``.

    Defaults to the real MCP-backed agent; tests inject a stub so they never launch
    the MCP subprocess or need a tool-using model."""

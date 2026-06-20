"""Provider registry — pick paid or local models with one env var.

The graph never names a concrete model. Nodes ask for a *tier*:

  - ``reasoning``  the slow/expensive thinker (planner, critic, synthesizer, code)
  - ``fast``       the high-volume specialist summarizers (logs, metrics, diff)

This module maps ``(provider, tier)`` to a real model id and the connection
details for that provider. Switch the whole copilot between Anthropic, OpenAI
and a laptop-local server by setting one variable::

    COPILOT_PROVIDER=anthropic   # paid, default — needs ANTHROPIC_API_KEY
    COPILOT_PROVIDER=openai      # paid           — needs OPENAI_API_KEY
    COPILOT_PROVIDER=local       # free, on-device — Ollama / LM Studio / vLLM

Every concrete model id is overridable from the environment, so you are never
stuck with the defaults baked in here.

Local models are reached through their OpenAI-compatible endpoint (Ollama, LM
Studio, vLLM and llama.cpp all expose one), so the same ``ChatOpenAI`` client
drives both ``openai`` and ``local`` — only the base URL and key change.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Tier names used throughout the graph.
REASONING = "reasoning"
FAST = "fast"

# (provider, tier) -> default model id. Each is overridable via env (see below).
_DEFAULT_MODELS: dict[str, dict[str, str]] = {
    "anthropic": {REASONING: "claude-opus-4-8", FAST: "claude-sonnet-4-6"},
    "openai": {REASONING: "gpt-4o", FAST: "gpt-4o-mini"},
    # Pick any model you have pulled locally, e.g. `ollama pull llama3.1`.
    "local": {REASONING: "llama3.1", FAST: "llama3.1"},
}

# Per-provider env var that overrides the model id for a tier.
_MODEL_ENV: dict[str, dict[str, str]] = {
    "anthropic": {REASONING: "COPILOT_ANTHROPIC_REASONING_MODEL", FAST: "COPILOT_ANTHROPIC_FAST_MODEL"},
    "openai": {REASONING: "COPILOT_OPENAI_REASONING_MODEL", FAST: "COPILOT_OPENAI_FAST_MODEL"},
    "local": {REASONING: "COPILOT_LOCAL_REASONING_MODEL", FAST: "COPILOT_LOCAL_FAST_MODEL"},
}

SUPPORTED = tuple(_DEFAULT_MODELS)


@dataclass(frozen=True)
class ProviderConfig:
    """Everything needed to build a chat client for the active provider."""

    name: str
    reasoning_model: str
    fast_model: str
    base_url: str | None = None
    api_key: str | None = None

    def model_for(self, tier: str) -> str:
        return self.reasoning_model if tier == REASONING else self.fast_model


def active_provider() -> str:
    """The provider selected via ``COPILOT_PROVIDER`` (default ``anthropic``)."""
    name = os.environ.get("COPILOT_PROVIDER", "anthropic").strip().lower()
    if name not in _DEFAULT_MODELS:
        raise ValueError(
            f"Unknown COPILOT_PROVIDER={name!r}. Choose one of: {', '.join(SUPPORTED)}."
        )
    return name


def _model(provider: str, tier: str) -> str:
    return os.environ.get(_MODEL_ENV[provider][tier], _DEFAULT_MODELS[provider][tier])


def resolve(provider: str | None = None) -> ProviderConfig:
    """Build the :class:`ProviderConfig` for ``provider`` (or the active one)."""
    name = (provider or active_provider()).strip().lower()
    if name not in _DEFAULT_MODELS:
        raise ValueError(
            f"Unknown provider {name!r}. Choose one of: {', '.join(SUPPORTED)}."
        )

    reasoning = _model(name, REASONING)
    fast = _model(name, FAST)

    if name == "local":
        # Ollama's OpenAI-compatible endpoint by default; LM Studio uses
        # http://localhost:1234/v1, vLLM http://localhost:8000/v1.
        base_url = os.environ.get("COPILOT_LOCAL_BASE_URL", "http://localhost:11434/v1")
        # Local servers ignore the key but the OpenAI client requires a non-empty one.
        api_key = os.environ.get("COPILOT_LOCAL_API_KEY", "not-needed")
    elif name == "openai":
        base_url = os.environ.get("OPENAI_BASE_URL")  # None => api.openai.com
        api_key = os.environ.get("OPENAI_API_KEY")
    else:  # anthropic — key is read from ANTHROPIC_API_KEY by the client itself
        base_url = None
        api_key = os.environ.get("ANTHROPIC_API_KEY")

    return ProviderConfig(
        name=name,
        reasoning_model=reasoning,
        fast_model=fast,
        base_url=base_url,
        api_key=api_key,
    )

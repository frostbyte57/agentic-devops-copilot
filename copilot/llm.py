"""Chat-model factory — one place to pick the model per role *and* provider.

Nodes ask for a *tier*, not a vendor model: ``OPUS`` for the reasoning-heavy
planner/critic/synthesizer, ``SONNET`` for the high-volume specialist
summarizers. These names are kept for readability, but they are really tier
markers (reasoning vs fast). The concrete model — and whether it is a paid API
or a model running on your laptop — is decided by ``COPILOT_PROVIDER`` and
resolved in :mod:`copilot.providers`.

    COPILOT_PROVIDER=anthropic   # paid  (ANTHROPIC_API_KEY)        — default
    COPILOT_PROVIDER=openai      # paid  (OPENAI_API_KEY)
    COPILOT_PROVIDER=local       # local (Ollama / LM Studio / vLLM)

Anthropic-only notes (claude-api guidance):
- Opus 4.8 uses *adaptive* thinking (``{"type": "adaptive"}``); the old
  ``budget_tokens`` form is removed and 400s. We only enable thinking on
  free-form reasoning nodes — structured-output nodes keep it off, since forcing
  a tool/JSON schema and extended thinking together is brittle. The flag is
  ignored for the OpenAI and local providers.
- Structured output comes from ``.with_structured_output(...)`` (tool-calling
  under the hood), which the OpenAI client supports too. Locally hosted models
  need tool-calling support for the structured nodes (planner/critic/
  synthesizer) — most recent instruct models (llama3.1, qwen2.5, mistral) have it.
"""

from __future__ import annotations

from typing import Any

from . import providers
from .providers import FAST, REASONING

# Tier markers. Kept named after the Anthropic tiers for readability; they map
# to ``reasoning`` / ``fast`` regardless of which provider is active.
OPUS = REASONING
SONNET = FAST
HAIKU = FAST

_TIERS = {REASONING, FAST}


def make_llm(
    model: str = OPUS,
    max_tokens: int = 8000,
    thinking: bool = False,
    timeout: int = 120,
) -> Any:
    """Build a chat client for a role, using the active provider.

    ``model`` is a tier marker (``OPUS``/``SONNET``/``HAIKU``, i.e. ``reasoning``
    or ``fast``). Set ``thinking=True`` only on free-form reasoning calls; it is
    honoured for Anthropic and ignored elsewhere.
    """
    tier = model if model in _TIERS else REASONING
    cfg = providers.resolve()
    model_id = cfg.model_for(tier)

    if cfg.name == "anthropic":
        from langchain_anthropic import ChatAnthropic

        kwargs: dict = {"model": model_id, "max_tokens": max_tokens, "timeout": timeout}
        if thinking:
            kwargs["thinking"] = {"type": "adaptive"}
        return ChatAnthropic(**kwargs)

    # openai + local both speak the OpenAI protocol.
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise ImportError(
            f"COPILOT_PROVIDER={cfg.name!r} needs langchain-openai. "
            f"Install it with:  pip install 'aws-devops-copilot[{cfg.name}]'"
        ) from exc

    kwargs = {"model": model_id, "max_tokens": max_tokens, "timeout": timeout}
    if cfg.base_url:
        kwargs["base_url"] = cfg.base_url
    if cfg.api_key:
        kwargs["api_key"] = cfg.api_key
    return ChatOpenAI(**kwargs)

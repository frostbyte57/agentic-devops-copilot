"""Chat-model factory — one place to build the chat client for the active provider.

The whole copilot runs on a single model. Nodes historically passed a tier marker
(``OPUS``/``SONNET``/``HAIKU``) as the first argument for readability; those are
now cosmetic aliases — every call resolves to the one model, provider, and key
chosen in the UI and read from :mod:`copilot.settings_store` via
``providers.resolve()`` (anthropic / openai / local). Nothing is read from the
environment.

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

# Cosmetic call-site markers — all map to the single active model. Kept so the
# node call sites (``deps.llm(OPUS, ...)``) read clearly and don't need editing.
OPUS = "opus"
SONNET = "sonnet"
HAIKU = "haiku"


def make_llm(
    model: str = OPUS,
    max_tokens: int = 8000,
    thinking: bool = False,
    timeout: int = 120,
) -> Any:
    """Build a chat client using the active provider's single model.

    ``model`` is an ignored cosmetic marker (``OPUS``/``SONNET``/``HAIKU``). Set
    ``thinking=True`` only on free-form reasoning calls; it is honoured for
    Anthropic and ignored elsewhere.
    """
    cfg = providers.resolve()
    model_id = cfg.model

    if cfg.name == "anthropic":
        from langchain_anthropic import ChatAnthropic

        kwargs: dict = {"model": model_id, "max_tokens": max_tokens, "timeout": timeout}
        if cfg.api_key:
            kwargs["api_key"] = cfg.api_key
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

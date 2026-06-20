"""Provider registry — resolve the active provider's model and connection details.

The whole copilot runs on a *single* model. The provider, the model override, and
the API keys all come from :mod:`copilot.settings_store` (the UI is the source of
truth) — nothing is read from the environment.

  - ``anthropic``  paid, default — needs the Anthropic key
  - ``openai``     paid           — needs the OpenAI key
  - ``local``      free, on-device — Ollama / LM Studio / vLLM

Local models are reached through their OpenAI-compatible endpoint (Ollama, LM
Studio, vLLM and llama.cpp all expose one), so the same ``ChatOpenAI`` client
drives both ``openai`` and ``local`` — only the base URL and key change.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import settings_store

# provider -> default model id. Overridable per provider from the settings store.
_DEFAULT_MODEL: dict[str, str] = {
    "anthropic": "claude-opus-4-8",
    "openai": "gpt-4o",
    # Pick any model you have pulled locally, e.g. `ollama pull llama3.1`.
    "local": "llama3.1",
}

DEFAULT_LOCAL_BASE_URL = "http://localhost:11434/v1"

SUPPORTED = tuple(_DEFAULT_MODEL)


@dataclass(frozen=True)
class ProviderConfig:
    """Everything needed to build a chat client for the active provider."""

    name: str
    model: str
    base_url: str | None = None
    api_key: str | None = None


def active_provider() -> str:
    """The provider selected in the settings store (default ``anthropic``)."""
    name = (settings_store.get().get("provider") or "anthropic").strip().lower()
    if name not in _DEFAULT_MODEL:
        raise ValueError(
            f"Unknown provider {name!r}. Choose one of: {', '.join(SUPPORTED)}."
        )
    return name


def catalog() -> list[dict]:
    """Describe every provider for the configuration UI.

    Returns the default model id and whether the provider needs an API key or a
    local server, so the frontend can render sensible fields.
    """
    meta = {
        "anthropic": {"label": "Anthropic", "kind": "paid", "needs_key": "ANTHROPIC_API_KEY"},
        "openai": {"label": "OpenAI", "kind": "paid", "needs_key": "OPENAI_API_KEY"},
        "local": {"label": "Local (Ollama / LM Studio)", "kind": "local", "needs_key": None},
    }
    out = []
    for name in SUPPORTED:
        out.append(
            {
                "id": name,
                "label": meta[name]["label"],
                "kind": meta[name]["kind"],
                "needs_key": meta[name]["needs_key"],
                "default_model": _DEFAULT_MODEL[name],
            }
        )
    return out


def resolve(provider: str | None = None) -> ProviderConfig:
    """Build the :class:`ProviderConfig` for ``provider`` (or the active one)."""
    name = (provider or active_provider()).strip().lower()
    if name not in _DEFAULT_MODEL:
        raise ValueError(
            f"Unknown provider {name!r}. Choose one of: {', '.join(SUPPORTED)}."
        )

    model = settings_store.model_for(name) or _DEFAULT_MODEL[name]

    if name == "local":
        # Ollama's OpenAI-compatible endpoint by default; LM Studio uses
        # http://localhost:1234/v1, vLLM http://localhost:8000/v1.
        base_url = settings_store.get().get("local_base_url") or DEFAULT_LOCAL_BASE_URL
        # Local servers ignore the key but the OpenAI client requires a non-empty one.
        api_key = settings_store.key("local") or "not-needed"
    elif name == "openai":
        base_url = None  # api.openai.com
        api_key = settings_store.key("openai")
    else:  # anthropic
        base_url = None
        api_key = settings_store.key("anthropic")

    return ProviderConfig(
        name=name,
        model=model,
        base_url=base_url,
        api_key=api_key,
    )

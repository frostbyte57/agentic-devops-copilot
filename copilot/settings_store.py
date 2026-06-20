"""Persistent settings — the single source of truth for runtime configuration.

The UI owns everything: provider, the per-provider model override, AWS region and
credentials, the GitHub token/repo, the code-executor toggle, and all API keys.
We persist it to a JSON file in the user config dir (not the repo) so values set
in the UI survive a restart. Nothing is read from or written to the process
environment — the rest of the app reads the config straight from here via
``get()`` (and the typed helpers ``key()`` / ``model_for()``).

Secrets are stored in plaintext in a ``0600`` file under ``~/.config`` —
acceptable for a local single-user tool.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_config: dict[str, Any] | None = None


def _path() -> Path:
    # Storage location only (not a config value); the test suite points this at a
    # temp file via COPILOT_SETTINGS_FILE.
    override = os.environ.get("COPILOT_SETTINGS_FILE")
    if override:
        return Path(override)
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "aws-devops-copilot" / "settings.json"


def _default() -> dict[str, Any]:
    return {
        "provider": "anthropic",
        "region": None,
        "local_base_url": None,
        "github_repo": None,
        "allow_code_exec": True,
        # per-provider model override: {provider: model_id}
        "models": {},
        # name -> secret: anthropic / openai / github / aws_access_key_id / aws_secret_access_key
        "keys": {},
    }


def load() -> dict[str, Any]:
    """Read persisted settings (merged over defaults) into the in-memory config."""
    global _config
    data = _default()
    path = _path()
    if path.exists():
        try:
            data.update(json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError):
            pass  # corrupt/unreadable file — fall back to defaults
    _config = data
    return _config


def get() -> dict[str, Any]:
    """The live config dict, loaded from disk on first access."""
    return _config if _config is not None else load()


def save(data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Persist the config to disk (and adopt ``data`` as the live config if given)."""
    global _config
    if data is not None:
        _config = data
    cfg = get()
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2))
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return cfg


def key(name: str) -> str | None:
    """A stored secret by name, or ``None`` if unset/blank."""
    return (get().get("keys") or {}).get(name) or None


def model_for(provider: str) -> str | None:
    """The model override for a provider (tolerates the legacy tier dict shape)."""
    value = (get().get("models") or {}).get(provider)
    if isinstance(value, dict):  # legacy {"reasoning": id, "fast": id}
        value = value.get("reasoning") or value.get("fast")
    return value or None

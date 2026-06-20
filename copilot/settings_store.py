"""Persistent settings for the web UI.

The UI is the source of truth for runtime configuration — provider, per-provider
model overrides, AWS region, the code-executor toggle, and **all API keys**. We
persist it to a JSON file in the user config dir (not the repo) so keys set in
the UI survive a restart, and mirror everything into ``os.environ`` on load so
the existing ``providers.resolve()`` / ``AwsAdapters.from_env()`` keep working
untouched.

Keys are stored in plaintext in a ``0600`` file under ``~/.config`` — acceptable
for a local single-user dev tool, the same trust level as a ``.env``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# provider/feature -> the env var the rest of the app already reads.
KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "github": "GITHUB_TOKEN",
}


def _path() -> Path:
    override = os.environ.get("COPILOT_SETTINGS_FILE")
    if override:
        return Path(override)
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "aws-devops-copilot" / "settings.json"


def _default() -> dict[str, Any]:
    return {
        "provider": os.environ.get("COPILOT_PROVIDER", "anthropic"),
        "region": os.environ.get("AWS_REGION"),
        "local_base_url": os.environ.get("COPILOT_LOCAL_BASE_URL"),
        "allow_code_exec": True,
        # per-provider model overrides: {provider: {"reasoning": id, "fast": id}}
        "models": {},
        # provider/feature -> api key
        "keys": {},
    }


def _model_env(provider: str, tier: str) -> str:
    return f"COPILOT_{provider.upper()}_{tier.upper()}_MODEL"


def load() -> dict[str, Any]:
    """Read persisted settings (merged over defaults) and apply them to env."""
    data = _default()
    path = _path()
    if path.exists():
        try:
            data.update(json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError):
            pass  # corrupt/unreadable file — fall back to defaults
    apply_to_env(data)
    return data


def save(data: dict[str, Any]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    try:
        path.chmod(0o600)
    except OSError:
        pass
    apply_to_env(data)


def apply_to_env(data: dict[str, Any]) -> None:
    """Mirror persisted settings into the process environment."""
    if data.get("provider"):
        os.environ["COPILOT_PROVIDER"] = data["provider"]
    if data.get("region"):
        os.environ["AWS_REGION"] = data["region"]
    if data.get("local_base_url"):
        os.environ["COPILOT_LOCAL_BASE_URL"] = data["local_base_url"]
    for provider, tiers in (data.get("models") or {}).items():
        for tier, model_id in (tiers or {}).items():
            if model_id:
                os.environ[_model_env(provider, tier)] = model_id
    for name, value in (data.get("keys") or {}).items():
        env = KEY_ENV.get(name)
        if env and value:
            os.environ[env] = value

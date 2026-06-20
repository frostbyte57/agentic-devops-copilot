"""HTTP backend for the web UI — wraps the LangGraph agent in a small API.

Endpoints
---------
GET  /api/providers   catalog of providers + default models (for the config UI)
GET  /api/models      models the active provider's stored key can reach
GET  /api/settings    the current runtime settings (secrets redacted)
PUT  /api/settings    update provider / model / region / credentials / toggles
POST /api/investigate stream the investigation as Server-Sent Events

The UI is the single source of truth: everything is read from
:mod:`copilot.settings_store`, nothing from the environment.

Run it with::

    uvicorn copilot.server:app --reload --port 8000
"""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import providers, settings_store
from .aws.adapters import AwsAdapters
from .deps import Deps
from .graph import build_graph
from .state import IncidentReport

app = FastAPI(title="AWS DevOps Copilot API")

# Load persisted UI settings into the in-memory config at startup.
_store = settings_store.load()

# Local dev: the Next.js app runs on a different origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_SOURCE_LABEL = {
    "planner": "Planner",
    "logs": "CloudWatch Logs",
    "metrics": "Metrics",
    "github": "GitHub Diff",
    "rag": "Runbooks (RAG)",
    "code": "Code Executor",
    "critic": "Critic",
    "synthesizer": "Synthesizer",
}

# ── runtime settings ─────────────────────────────────────────────────────────


class SettingsOut(BaseModel):
    provider: str
    model: str
    region: Optional[str] = None
    local_base_url: Optional[str] = None
    github_repo: Optional[str] = None
    allow_code_exec: bool = True
    # Which keys are stored — never the values themselves.
    has_anthropic_key: bool = False
    has_openai_key: bool = False
    has_github_token: bool = False
    has_aws_credentials: bool = False


class SettingsIn(BaseModel):
    provider: str
    model: str
    region: Optional[str] = None
    local_base_url: Optional[str] = None
    github_repo: Optional[str] = None
    allow_code_exec: bool = True
    # Write-only: blank/omitted means "keep what's already stored".
    anthropic_key: Optional[str] = None
    openai_key: Optional[str] = None
    github_token: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None


def _current_settings() -> SettingsOut:
    cfg = providers.resolve()
    keys = _store.get("keys") or {}
    return SettingsOut(
        provider=cfg.name,
        model=cfg.model,
        region=_store.get("region"),
        local_base_url=_store.get("local_base_url") if cfg.name == "local" else None,
        github_repo=_store.get("github_repo"),
        allow_code_exec=bool(_store.get("allow_code_exec", True)),
        has_anthropic_key=bool(keys.get("anthropic")),
        has_openai_key=bool(keys.get("openai")),
        has_github_token=bool(keys.get("github")),
        has_aws_credentials=bool(keys.get("aws_access_key_id")),
    )


# ── endpoints ────────────────────────────────────────────────────────────────


@app.get("/api/providers")
def get_providers() -> dict:
    return {"providers": providers.catalog()}


def _http_get_json(url: str, headers: dict[str, str], timeout: float = 8.0) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted hosts)
        return json.loads(resp.read().decode())


def _is_openai_chat_model(model_id: str) -> bool:
    """Keep chat/completion models; drop embeddings, audio, image, instruct, etc."""
    mid = model_id.lower()
    if not (mid.startswith("gpt-") or mid.startswith("chatgpt") or re.match(r"o\d", mid)):
        return False
    excluded = (
        "embedding", "whisper", "tts", "audio", "realtime", "transcribe",
        "search", "moderation", "image", "dall-e", "instruct",
    )
    return not any(token in mid for token in excluded)


def _fetch_models(provider: str) -> list[dict]:
    """Ask the provider which models the stored key can access."""
    if provider == "anthropic":
        key = settings_store.key("anthropic")
        if not key:
            return []
        data = _http_get_json(
            "https://api.anthropic.com/v1/models?limit=100",
            {"x-api-key": key, "anthropic-version": "2023-06-01"},
        )
        return [
            {"id": m["id"], "label": m.get("display_name") or m["id"]}
            for m in data.get("data", [])
        ]

    if provider == "openai":
        key = settings_store.key("openai")
        if not key:
            return []
        data = _http_get_json(
            "https://api.openai.com/v1/models", {"Authorization": f"Bearer {key}"}
        )
        ids = sorted(
            (m["id"] for m in data.get("data", []) if _is_openai_chat_model(m["id"])),
            reverse=True,
        )
        return [{"id": i, "label": i} for i in ids]

    if provider == "local":
        base = (_store.get("local_base_url") or providers.DEFAULT_LOCAL_BASE_URL).rstrip("/")
        key = settings_store.key("local") or "not-needed"
        data = _http_get_json(f"{base}/models", {"Authorization": f"Bearer {key}"})
        return [{"id": m["id"], "label": m["id"]} for m in data.get("data", [])]

    return []


@app.get("/api/models")
def list_models(provider: Optional[str] = None) -> dict:
    """List the models the active (or requested) provider's key can reach.

    Returns an empty list (with an ``error`` string) rather than a non-2xx so the
    UI can fall back to the current/default model without a hard failure.
    """
    name = provider or providers.active_provider()
    try:
        return {"provider": name, "models": _fetch_models(name)}
    except Exception as exc:  # offline / bad key / unreachable local server
        return {"provider": name, "models": [], "error": f"{type(exc).__name__}: {exc}"}


@app.get("/api/settings", response_model=SettingsOut)
def get_settings() -> SettingsOut:
    return _current_settings()


@app.put("/api/settings", response_model=SettingsOut)
def put_settings(s: SettingsIn) -> SettingsOut:
    _store["provider"] = s.provider
    _store["region"] = s.region or _store.get("region")
    _store["allow_code_exec"] = s.allow_code_exec
    _store["github_repo"] = s.github_repo or _store.get("github_repo")
    if s.provider == "local" and s.local_base_url:
        _store["local_base_url"] = s.local_base_url

    models = _store.setdefault("models", {})
    models[s.provider] = s.model

    # Only overwrite a key when a non-blank value is supplied.
    keys = _store.setdefault("keys", {})
    for name, value in (
        ("anthropic", s.anthropic_key),
        ("openai", s.openai_key),
        ("github", s.github_token),
        ("aws_access_key_id", s.aws_access_key_id),
        ("aws_secret_access_key", s.aws_secret_access_key),
    ):
        if value:
            keys[name] = value

    settings_store.save(_store)  # persists to disk
    return _current_settings()


class InvestigateRequest(BaseModel):
    incident: str


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/api/investigate")
def investigate(req: InvestigateRequest) -> StreamingResponse:
    """Stream node updates then the final report as SSE."""

    def gen():
        try:
            cfg = providers.resolve()
            yield _sse("meta", {"provider": cfg.name, "model": cfg.model})
            deps = Deps(
                aws=AwsAdapters.from_settings(),
                allow_code_exec=bool(_store.get("allow_code_exec", True)),
                github_token=settings_store.key("github"),
                github_repo=_store.get("github_repo"),
            )
            graph = build_graph(deps)

            final: dict = {}
            for update in graph.stream({"incident": req.incident}, stream_mode="updates"):
                for node, payload in update.items():
                    yield _sse(
                        "step",
                        {
                            "node": node,
                            "label": _SOURCE_LABEL.get(node, node),
                            "evidence": [
                                {"source": e.source, "summary": e.summary, "severity": e.severity}
                                for e in (payload.get("evidence") or [])
                            ],
                        },
                    )
                    final.update(payload)

            report = final.get("report")
            if isinstance(report, IncidentReport):
                yield _sse("report", report.model_dump())
            else:
                yield _sse("error", {"message": "No report was produced."})
        except Exception as exc:  # surface failures to the UI instead of a dead stream
            yield _sse("error", {"message": f"{type(exc).__name__}: {exc}"})
        finally:
            yield _sse("done", {})

    return StreamingResponse(gen(), media_type="text/event-stream")

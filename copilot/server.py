"""HTTP backend for the web UI — wraps the LangGraph agent in a small API.

Endpoints
---------
GET  /api/providers   catalog of providers + default models (for the config UI)
GET  /api/settings    the current runtime settings (secrets redacted)
PUT  /api/settings    update provider / models / region / agent toggles
POST /api/investigate stream the investigation as Server-Sent Events

Settings are held in-process and mirrored into ``os.environ`` so the existing
``providers.resolve()`` and ``AwsAdapters.from_env()`` pick them up unchanged —
the graph code stays oblivious to where its configuration came from.

Run it with::

    uvicorn copilot.server:app --reload --port 8000
"""

from __future__ import annotations

import json
import os
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

# Load persisted UI settings (incl. API keys) into the environment at startup.
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
    reasoning_model: str
    fast_model: str
    region: Optional[str] = None
    local_base_url: Optional[str] = None
    allow_code_exec: bool = True
    # Which keys are stored — never the values themselves.
    has_anthropic_key: bool = False
    has_openai_key: bool = False
    has_github_token: bool = False


class SettingsIn(BaseModel):
    provider: str
    reasoning_model: str
    fast_model: str
    region: Optional[str] = None
    local_base_url: Optional[str] = None
    allow_code_exec: bool = True
    # Write-only: blank/omitted means "keep what's already stored".
    anthropic_key: Optional[str] = None
    openai_key: Optional[str] = None
    github_token: Optional[str] = None


def _current_settings() -> SettingsOut:
    cfg = providers.resolve()
    keys = _store.get("keys") or {}
    return SettingsOut(
        provider=cfg.name,
        reasoning_model=cfg.reasoning_model,
        fast_model=cfg.fast_model,
        region=os.environ.get("AWS_REGION"),
        local_base_url=os.environ.get("COPILOT_LOCAL_BASE_URL") if cfg.name == "local" else None,
        allow_code_exec=bool(_store.get("allow_code_exec", True)),
        has_anthropic_key=bool(keys.get("anthropic") or os.environ.get("ANTHROPIC_API_KEY")),
        has_openai_key=bool(keys.get("openai") or os.environ.get("OPENAI_API_KEY")),
        has_github_token=bool(keys.get("github") or os.environ.get("GITHUB_TOKEN")),
    )


# ── endpoints ────────────────────────────────────────────────────────────────


@app.get("/api/providers")
def get_providers() -> dict:
    return {"providers": providers.catalog()}


@app.get("/api/settings", response_model=SettingsOut)
def get_settings() -> SettingsOut:
    return _current_settings()


@app.put("/api/settings", response_model=SettingsOut)
def put_settings(s: SettingsIn) -> SettingsOut:
    _store["provider"] = s.provider
    _store["region"] = s.region or _store.get("region")
    _store["allow_code_exec"] = s.allow_code_exec
    if s.provider == "local" and s.local_base_url:
        _store["local_base_url"] = s.local_base_url

    models = _store.setdefault("models", {})
    models[s.provider] = {"reasoning": s.reasoning_model, "fast": s.fast_model}

    # Only overwrite a key when a non-blank value is supplied.
    keys = _store.setdefault("keys", {})
    for name, value in (
        ("anthropic", s.anthropic_key),
        ("openai", s.openai_key),
        ("github", s.github_token),
    ):
        if value:
            keys[name] = value

    settings_store.save(_store)  # persists to disk + mirrors into env
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
            yield _sse("meta", {"provider": cfg.name, "reasoning_model": cfg.reasoning_model,
                                 "fast_model": cfg.fast_model})
            deps = Deps(
                aws=AwsAdapters.from_env(region=os.environ.get("AWS_REGION")),
                allow_code_exec=bool(_store.get("allow_code_exec", True)),
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

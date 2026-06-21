"""API smoke tests for the web backend — config endpoints + SSE shape.

No AWS or model keys required. The investigate stream is exercised only far
enough to assert it emits a ``meta`` frame and always terminates with ``done``
(the run itself fails gracefully without credentials, which is the contract).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from copilot import providers, server, settings_store
from copilot.server import app

client = TestClient(app)


def test_providers_catalog():
    body = client.get("/api/providers").json()
    ids = {p["id"] for p in body["providers"]}
    assert {"anthropic", "openai", "local"} <= ids


def test_settings_roundtrip():
    saved = client.put(
        "/api/settings",
        json={
            "provider": "anthropic",
            "model": "claude-opus-4-8",
            "region": "ap-southeast-2",
            "allow_code_exec": False,
            "has_api_key": False,
        },
    ).json()
    assert saved["provider"] == "anthropic"
    assert saved["region"] == "ap-southeast-2"
    assert saved["allow_code_exec"] is False
    # persisted in the settings store for the graph to resolve
    assert settings_store.get()["region"] == "ap-southeast-2"

    got = client.get("/api/settings").json()
    assert got["model"] == "claude-opus-4-8"
    # secrets are never returned
    assert "api_key" not in got or got.get("api_key") is None


def test_api_keys_persist_and_are_redacted():
    client.put(
        "/api/settings",
        json={
            "provider": "anthropic",
            "model": "claude-opus-4-8",
            "allow_code_exec": True,
            "anthropic_key": "sk-ant-SECRET",
            "openai_key": "sk-oai-SECRET",
            "github_token": "ghp_SECRET",
        },
    )
    got = client.get("/api/settings").json()
    # flags report presence...
    assert got["has_anthropic_key"] and got["has_openai_key"] and got["has_github_token"]
    # ...but the secret values are never returned.
    assert not any("SECRET" in str(v) for v in got.values())
    # stored for the agent to use, and threaded into the resolved provider config
    assert settings_store.key("github") == "ghp_SECRET"
    assert providers.resolve().api_key == "sk-ant-SECRET"

    # blank key on a later save keeps the stored value
    client.put(
        "/api/settings",
        json={
            "provider": "anthropic",
            "model": "claude-opus-4-8",
            "allow_code_exec": True,
        },
    )
    assert client.get("/api/settings").json()["has_anthropic_key"] is True


def test_aws_credentials_persist_and_are_redacted():
    client.put(
        "/api/settings",
        json={
            "provider": "anthropic",
            "model": "claude-opus-4-8",
            "allow_code_exec": True,
            "aws_access_key_id": "AKIA_SECRET",
            "aws_secret_access_key": "aws-secret-SECRET",
        },
    )
    got = client.get("/api/settings").json()
    # presence is reported...
    assert got["has_aws_credentials"] is True
    # ...but the secret values are never returned.
    assert not any("SECRET" in str(v) for v in got.values())
    # stored for the read-only AWS MCP server to pick up
    assert settings_store.key("aws_access_key_id") == "AKIA_SECRET"
    assert settings_store.key("aws_secret_access_key") == "aws-secret-SECRET"


def test_models_endpoint_filters_openai(monkeypatch):
    # Pretend OpenAI returned a mix of chat and non-chat models.
    fake = {
        "data": [
            {"id": "gpt-4o"},
            {"id": "o3-mini"},
            {"id": "text-embedding-3-large"},
            {"id": "whisper-1"},
            {"id": "gpt-3.5-turbo-instruct"},
            {"id": "dall-e-3"},
        ]
    }
    monkeypatch.setitem(server._store.setdefault("keys", {}), "openai", "sk-test")
    monkeypatch.setattr(server, "_http_get_json", lambda *a, **k: fake)

    body = client.get("/api/models", params={"provider": "openai"}).json()
    ids = [m["id"] for m in body["models"]]
    assert ids == ["o3-mini", "gpt-4o"]  # chat models only, sorted descending


def test_models_endpoint_no_key_is_empty(monkeypatch):
    monkeypatch.setitem(server._store.setdefault("keys", {}), "openai", "")
    body = client.get("/api/models", params={"provider": "openai"}).json()
    assert body["models"] == [] and "error" not in body


def test_investigate_stream_terminates():
    events = []
    with client.stream("POST", "/api/investigate", json={"incident": "x"}) as r:
        for line in r.iter_lines():
            if line.startswith("event:"):
                events.append(line.split(":", 1)[1].strip())
    assert events[0] == "meta"
    assert events[-1] == "done"

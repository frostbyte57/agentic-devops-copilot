"""API smoke tests for the web backend — config endpoints + SSE shape.

No AWS or model keys required. The investigate stream is exercised only far
enough to assert it emits a ``meta`` frame and always terminates with ``done``
(the run itself fails gracefully without credentials, which is the contract).
"""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

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
            "reasoning_model": "claude-opus-4-8",
            "fast_model": "claude-sonnet-4-6",
            "region": "ap-southeast-2",
            "allow_code_exec": False,
            "has_api_key": False,
        },
    ).json()
    assert saved["provider"] == "anthropic"
    assert saved["region"] == "ap-southeast-2"
    assert saved["allow_code_exec"] is False
    # mirrored into the environment for the graph to resolve
    assert os.environ["AWS_REGION"] == "ap-southeast-2"

    got = client.get("/api/settings").json()
    assert got["reasoning_model"] == "claude-opus-4-8"
    # secrets are never returned
    assert "api_key" not in got or got.get("api_key") is None


def test_api_keys_persist_and_are_redacted():
    client.put(
        "/api/settings",
        json={
            "provider": "anthropic",
            "reasoning_model": "claude-opus-4-8",
            "fast_model": "claude-sonnet-4-6",
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
    # applied to the environment for the agent to use
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-SECRET"
    assert os.environ["GITHUB_TOKEN"] == "ghp_SECRET"

    # blank key on a later save keeps the stored value
    client.put(
        "/api/settings",
        json={
            "provider": "anthropic",
            "reasoning_model": "claude-opus-4-8",
            "fast_model": "claude-sonnet-4-6",
            "allow_code_exec": True,
        },
    )
    assert client.get("/api/settings").json()["has_anthropic_key"] is True


def test_investigate_stream_terminates():
    events = []
    with client.stream("POST", "/api/investigate", json={"incident": "x"}) as r:
        for line in r.iter_lines():
            if line.startswith("event:"):
                events.append(line.split(":", 1)[1].strip())
    assert events[0] == "meta"
    assert events[-1] == "done"

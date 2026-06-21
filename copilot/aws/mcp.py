"""Read-only AWS access via the AWS API MCP server.

Instead of a fixed set of boto3 calls, the investigator agent reaches AWS through
the official ``awslabs.aws-api-mcp-server``, launched as a stdio subprocess and
locked to read-only operations (``READ_OPERATIONS_ONLY``). That flag is a second
guard on top of IAM — the server only ever does what the supplied credentials
(or the host's default chain) are allowed to do, and never anything mutating.
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from typing import Any

from .. import settings_store

SERVER_NAME = "aws-api"


def _server_env(region: str | None, profile: str | None) -> dict[str, str]:
    """Subprocess env: inherit the host's, then pin read-only + region/creds."""
    env = dict(os.environ)
    env["READ_OPERATIONS_ONLY"] = "true"
    if region:
        env["AWS_REGION"] = region

    access_key = settings_store.key("aws_access_key_id")
    secret_key = settings_store.key("aws_secret_access_key")
    if access_key and secret_key:
        env["AWS_ACCESS_KEY_ID"] = access_key
        env["AWS_SECRET_ACCESS_KEY"] = secret_key
    if profile:
        env["AWS_API_MCP_PROFILE_NAME"] = profile
    return env


def connection(region: str | None = None, profile: str | None = None) -> dict[str, Any]:
    """Stdio connection spec for ``MultiServerMCPClient`` (read-only AWS API server)."""
    region = region or settings_store.get().get("region")
    return {
        "command": sys.executable,
        "args": ["-m", "awslabs.aws_api_mcp_server.server"],
        "transport": "stdio",
        "env": _server_env(region, profile),
    }


@asynccontextmanager
async def tools_session(region: str | None = None, profile: str | None = None):
    """Open one read-only AWS API MCP session and yield its tools as LangChain tools.

    Holding a single session open for the whole agent run means one MCP subprocess
    serves all of the agent's ``call_aws`` calls, instead of a cold start per call.
    """
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langchain_mcp_adapters.tools import load_mcp_tools

    client = MultiServerMCPClient({SERVER_NAME: connection(region, profile)})
    async with client.session(SERVER_NAME) as session:
        yield await load_mcp_tools(session)

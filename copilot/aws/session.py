"""Read-only boto3 session construction.

Credentials come from the UI settings store (passed in explicitly). If none are
provided, we fall back to boto3's default chain (shared ``~/.aws`` profile or an
instance role) — the copilot only ever makes read-only data-plane calls.
"""

from __future__ import annotations

import boto3


def build_session(
    region: str | None = None,
    access_key_id: str | None = None,
    secret_access_key: str | None = None,
    profile: str | None = None,
) -> boto3.Session:
    if access_key_id and secret_access_key:
        return boto3.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
        )
    # No explicit keys: let boto3 use its default chain (shared profile / role).
    return boto3.Session(region_name=region, profile_name=profile)

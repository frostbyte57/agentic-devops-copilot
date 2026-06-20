"""Read-only boto3 session construction.

The copilot must never hold write permissions. The session is built from the
standard credential chain (env / profile / instance role); if
``COPILOT_READONLY_ROLE_ARN`` is set we additionally assume a dedicated read-only
role via STS so that whatever long-lived credentials exist on the host are never
the ones making the data-plane calls.
"""

from __future__ import annotations

import os

import boto3


def build_session(region: str | None = None, profile: str | None = None) -> boto3.Session:
    region = region or os.getenv("AWS_REGION")
    profile = profile or os.getenv("AWS_PROFILE")

    base = boto3.Session(region_name=region, profile_name=profile)

    role_arn = os.getenv("COPILOT_READONLY_ROLE_ARN")
    if not role_arn:
        return base

    sts = base.client("sts")
    creds = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName="aws-devops-copilot",
    )["Credentials"]
    return boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
        region_name=region,
    )

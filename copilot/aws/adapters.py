"""Thin, typed wrappers over the read-only AWS calls the nodes need.

Every method returns plain Python data (lists/dicts), so a test or an offline demo
can substitute a stub object exposing the same surface without importing boto3.
Calls are tolerant: on failure they raise, and the calling node turns the error
into an `Evidence` entry rather than crashing the whole investigation.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from .session import build_session


class AwsAdapters:
    def __init__(self, session: Any):
        self._logs = session.client("logs")
        self._cw = session.client("cloudwatch")
        self._ecs = session.client("ecs")

    @classmethod
    def from_settings(cls, region: str | None = None, profile: str | None = None) -> "AwsAdapters":
        """Build adapters from the UI settings store (region/keys), with optional overrides."""
        from .. import settings_store

        cfg = settings_store.get()
        return cls(
            build_session(
                region=region or cfg.get("region"),
                access_key_id=settings_store.key("aws_access_key_id"),
                secret_access_key=settings_store.key("aws_secret_access_key"),
                profile=profile,
            )
        )

    # --- CloudWatch Logs Insights -----------------------------------------

    def logs_insights(
        self,
        log_group: str,
        window_minutes: int,
        query: str | None = None,
        limit: int = 500,
        poll_timeout: int = 30,
    ) -> list[dict[str, str]]:
        """Run a Logs Insights query and return result rows as field→value dicts."""
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=window_minutes)
        query = query or (
            "fields @timestamp, @message | filter @message like /(?i)(error|exception|5\\d\\d|timeout)/ "
            f"| sort @timestamp desc | limit {limit}"
        )
        started = self._logs.start_query(
            logGroupName=log_group,
            startTime=int(start.timestamp()),
            endTime=int(end.timestamp()),
            queryString=query,
        )
        query_id = started["queryId"]

        deadline = time.time() + poll_timeout
        while time.time() < deadline:
            res = self._logs.get_query_results(queryId=query_id)
            if res["status"] in ("Complete", "Failed", "Cancelled"):
                break
            time.sleep(1)
        else:
            self._logs.stop_query(queryId=query_id)
            res = self._logs.get_query_results(queryId=query_id)

        return [{f["field"]: f["value"] for f in row} for row in res.get("results", [])]

    # --- CloudWatch metrics ------------------------------------------------

    def metric_series(
        self,
        service: str,
        cluster: str | None,
        window_minutes: int,
        period: int = 60,
    ) -> dict[str, list[float]]:
        """Fetch CPU / memory utilization for an ECS service."""
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=window_minutes)
        dims = [{"Name": "ServiceName", "Value": service}]
        if cluster:
            dims.append({"Name": "ClusterName", "Value": cluster})

        def q(qid: str, metric: str):
            return {
                "Id": qid,
                "MetricStat": {
                    "Metric": {"Namespace": "AWS/ECS", "MetricName": metric, "Dimensions": dims},
                    "Period": period,
                    "Stat": "Average",
                },
                "ReturnData": True,
            }

        res = self._cw.get_metric_data(
            MetricDataQueries=[q("cpu", "CPUUtilization"), q("mem", "MemoryUtilization")],
            StartTime=start,
            EndTime=end,
        )
        out: dict[str, list[float]] = {}
        for r in res.get("MetricDataResults", []):
            out[r["Id"]] = list(r.get("Values", []))
        return out

    # --- ECS ---------------------------------------------------------------

    def describe_service(self, service: str, cluster: str) -> dict:
        res = self._ecs.describe_services(cluster=cluster, services=[service])
        services = res.get("services", [])
        return services[0] if services else {}

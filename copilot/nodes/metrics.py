"""Metrics node — fetch CPU/memory series and flag breaches/step-changes."""

from __future__ import annotations

from ..deps import Deps
from ..state import Evidence, State


def _cluster_for(state: State) -> str | None:
    for t in state.get("threads", []):
        if t.source == "metrics" and t.params.get("cluster"):
            return t.params["cluster"]
    return None


def _summarize(name: str, values: list[float]) -> tuple[str, str]:
    if not values:
        return (f"{name}: no datapoints", "info")
    peak = max(values)
    avg = sum(values) / len(values)
    sev = "critical" if peak >= 90 else "warning" if peak >= 75 else "info"
    return (f"{name}: avg {avg:.0f}%, peak {peak:.0f}%", sev)


def make_metrics_node(deps: Deps):
    def run(state: State) -> dict:
        service = state.get("service")
        if not service:
            return {"evidence": [Evidence(source="metrics", summary="No service resolved.", severity="info")]}

        try:
            series = deps.aws.metric_series(service, _cluster_for(state), state.get("window_minutes", 30))
        except Exception as e:  # noqa: BLE001
            return {"evidence": [Evidence(source="metrics", summary=f"Metric fetch failed: {e}", severity="warning")]}

        labels = {"cpu": "CPU", "mem": "Memory"}
        ev: list[Evidence] = []
        for key, label in labels.items():
            text, sev = _summarize(label, series.get(key, []))
            ev.append(Evidence(source="metrics", summary=text, severity=sev))  # type: ignore[arg-type]
        return {"evidence": ev}

    return run

"""Typer CLI — stream the investigation, then render the IncidentReport.

    copilot investigate "ECS service api-prod returning 503s for 20 minutes"
"""

from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from . import providers, settings_store
from .aws.adapters import AwsAdapters
from .deps import Deps
from .graph import build_graph
from .state import IncidentReport

app = typer.Typer(add_completion=False, help="Agentic AWS DevOps copilot.")
console = Console()

_SOURCE_LABEL = {
    "planner": "Agent Planner: breaking into investigation threads",
    "logs": "CloudWatch Logs",
    "metrics": "Metrics Fetcher",
    "github": "GitHub Diff",
    "rag": "RAG (runbooks)",
    "code": "Code Executor",
    "critic": "Critic",
    "synthesizer": "Synthesizer",
}


def _render_report(report: IncidentReport) -> None:
    body = [
        f"[bold]Root cause:[/bold] {report.root_cause}",
        f"[bold]Recommended fix:[/bold] {report.recommended_fix}",
        f"[bold]Confidence:[/bold] {report.confidence:.0%}",
    ]
    if report.evidence_refs:
        body.append("\n[bold]Evidence:[/bold]\n" + "\n".join(f"  • {e}" for e in report.evidence_refs))
    if report.commands_to_run:
        body.append("\n[bold]Commands:[/bold]\n" + "\n".join(f"  $ {c}" for c in report.commands_to_run))
    console.print(Panel("\n".join(body), title="IncidentReport", border_style="green"))


@app.command()
def investigate(
    incident: str = typer.Argument(..., help="Natural-language incident description."),
    region: Optional[str] = typer.Option(None, help="AWS region."),
    profile: Optional[str] = typer.Option(None, help="AWS profile."),
    no_code_exec: bool = typer.Option(False, "--no-code-exec", help="Disable the code-executor node."),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        help="LLM provider for this run: anthropic | openai | local.",
    ),
    as_json: bool = typer.Option(False, "--json", help="Print the report as JSON."),
) -> None:
    if provider:
        settings_store.get()["provider"] = provider
    try:
        cfg = providers.resolve()
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2)
    console.print(
        f"  [dim]provider:[/dim] [magenta]{cfg.name}[/magenta] "
        f"[dim](model={cfg.model})[/dim]"
    )

    deps = Deps(
        aws=AwsAdapters.from_settings(region=region, profile=profile),
        allow_code_exec=not no_code_exec,
        github_token=settings_store.key("github"),
        github_repo=settings_store.get().get("github_repo"),
    )
    graph = build_graph(deps)

    final: dict = {}
    for update in graph.stream({"incident": incident}, stream_mode="updates"):
        for node, payload in update.items():
            console.print(f"  → [cyan]{_SOURCE_LABEL.get(node, node)}[/cyan]")
            for ev in payload.get("evidence", []) or []:
                console.print(f"     [dim]{ev.source}:[/dim] {ev.summary}")
            final.update(payload)

    report = final.get("report")
    if not isinstance(report, IncidentReport):
        console.print("[red]No report produced.[/red]")
        raise typer.Exit(1)

    if as_json:
        console.print_json(json.dumps(report.model_dump()))
    else:
        _render_report(report)


@app.command()
def models(
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Inspect a specific provider instead of the active one."
    ),
) -> None:
    """Show the active provider and the model it resolves to."""
    if provider:
        settings_store.get()["provider"] = provider
    try:
        cfg = providers.resolve()
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2)

    lines = [
        f"[bold]Provider:[/bold] {cfg.name}",
        f"[bold]Model:[/bold] {cfg.model}",
    ]
    if cfg.base_url:
        lines.append(f"[bold]Endpoint:[/bold] {cfg.base_url}")
    lines.append("\n[dim]Configure in the web UI, or pass[/dim] --provider")
    console.print(Panel("\n".join(lines), title="LLM configuration", border_style="magenta"))


if __name__ == "__main__":
    app()

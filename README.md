# AWS DevOps Copilot

An agentic AWS DevOps copilot. Describe an incident in plain English and a
multi-agent system investigates your live AWS environment — CloudWatch logs and
metrics, the most recent deploy, and a runbook corpus — then returns a structured
**IncidentReport** with a ranked root cause, a recommended fix, and a confidence
score.

```
$ copilot "ECS service api-prod has been returning 503s for 20 minutes"

  → Agent Planner: breaking into investigation threads
  → CloudWatch Logs
     logs: Repeated DB query timeouts consistent with an N+1 regression.
  → Metrics Fetcher
     metrics: CPU: avg 86%, peak 94%
  → RAG (runbooks)
     rag: Runbook 'high-cpu-ecs' (match 71%)
  → Critic
  → Synthesizer

╭─────────────────────────── IncidentReport ───────────────────────────╮
│ Root cause: Inefficient DB query (N+1) introduced in the last deploy. │
│ Recommended fix: Add .select_related() to /users; scale ECS to 4.     │
│ Confidence: 91%                                                       │
╰──────────────────────────────────────────────────────────────────────╯
```

It runs on a **single model** (default `claude-opus-4-8`) and switches between
Anthropic, OpenAI, or a local model. All configuration lives in the web UI —
there are no environment variables.

## Quickstart

```bash
make install   # Python (all extras) + web deps
make dev       # API on :8000 + web UI on :3000
```

Open **http://localhost:3000**, add your keys in **Configuration**, and describe
an incident. (Prefer the CLI? `pip install -e '.[server]'` then `copilot
investigate "..."`.)

## Documentation

| Doc | What's in it |
| --- | --- |
| [docs/architecture.md](docs/architecture.md) | How it works — the agent graph + Mermaid diagrams |
| [docs/setup.md](docs/setup.md) | Install, extras, read-only AWS IAM, running tests |
| [docs/providers.md](docs/providers.md) | Choosing a model provider (Anthropic / OpenAI / local) |
| [docs/cli.md](docs/cli.md) | Running from the command line |
| [docs/web-ui.md](docs/web-ui.md) | Running the web app, `make` targets, persistence, build |
| [docs/security.md](docs/security.md) | Read-only AWS, credential handling, the code sandbox |
| [demo/README.md](demo/README.md) | One-command CloudFormation demo to test against real AWS |

# Usage

## Web UI

```bash
make install   # Python (all extras) + web deps
make dev       # API on :8000 + web UI on :3000 — Ctrl-C stops both
```

Open **http://localhost:3000**. A chat app (`web/`, React + Vite) streams each
investigation step live over SSE. The **Configuration** panel holds all your
credentials (Anthropic, OpenAI, GitHub, AWS), the region, and the code-executor
toggle; the model is switched from the chat bar. No env vars, no restarts.

Other targets: `make backend`, `make frontend`, `make test`, `make help`. Build
static assets with `cd web && npm run build` (output in `web/dist/`).

Settings are saved to `~/.config/aws-devops-copilot/settings.json` (a `0600` file)
and reloaded on the next start, so you configure once.

## CLI

```bash
copilot investigate "ECS service api-prod returning 503s for 20 minutes"
copilot investigate --no-code-exec --json "RDS db-prod CPU at 100% since 14:00"
copilot models   # show the resolved model for the active provider
```

| Option | Purpose |
| --- | --- |
| `--provider anthropic\|openai\|local` | Override the provider for this run |
| `--region <aws-region>` | Override the AWS region |
| `--profile <name>` | Use a specific AWS shared profile |
| `--no-code-exec` | Skip the sandboxed code-executor node |
| `--json` | Print the `IncidentReport` as JSON |

The CLI reads the same settings store the web UI writes; flags override stored
values for that one run.

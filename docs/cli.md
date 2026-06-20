# Run (CLI)

```bash
copilot investigate "ECS service api-prod returning 503s for 20 minutes"
copilot investigate --no-code-exec --json "RDS db-prod CPU at 100% since 14:00"
```

Useful options:

| Option | Purpose |
| --- | --- |
| `--provider anthropic\|openai\|local` | Override the provider for this run |
| `--region <aws-region>` | Override the AWS region |
| `--profile <name>` | Use a specific AWS shared profile |
| `--no-code-exec` | Skip the sandboxed code-executor node |
| `--json` | Print the `IncidentReport` as JSON |

Inspect the resolved model:

```bash
copilot models
```

The CLI reads the same settings store the web UI writes (provider, model, keys,
region) — see [providers.md](./providers.md). Flags override the stored values for
that single run.

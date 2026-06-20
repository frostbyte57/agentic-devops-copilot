# Setup

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[server]'   # add ".[github]" for the deploy-diff node
```

Optional extras:

| Extra | What it adds |
| --- | --- |
| `server` | FastAPI + uvicorn (the web backend) |
| `github` | PyGithub (the deploy-diff node) |
| `openai` | `langchain-openai` (the OpenAI provider) |
| `local`  | `langchain-openai` (local OpenAI-compatible servers) |

All runtime configuration — provider, model, API keys, AWS region/credentials —
is entered in the web UI's **Configuration** panel and persisted outside the repo.
Nothing is read from the environment. See [providers.md](./providers.md) and
[web-ui.md](./web-ui.md).

## AWS access (read-only)

The copilot only ever makes read-only data-plane calls — it never holds write
permissions. The key (or role) you give it needs:

```
logs:StartQuery, logs:GetQueryResults, logs:StopQuery,
cloudwatch:GetMetricData, ecs:Describe*, ecs:List*,
elasticloadbalancing:Describe*
```

A ready-to-use policy lives at
[`demo/copilot-readonly-policy.json`](../demo/copilot-readonly-policy.json).

If you leave the AWS credentials blank in the UI, boto3 falls back to your host's
default chain (shared `~/.aws` profile or instance role).

## Test

```bash
pytest tests/   # end-to-end against stubbed AWS + LLM (no creds needed)
```

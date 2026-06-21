# Setup

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[server]'
```

Extras: `server` (web backend), `github` (deploy-diff node), `openai`, `local`.

All runtime config — provider, model, keys, AWS region/credentials — is entered in
the web UI's **Configuration** panel and persisted outside the repo. Nothing is
read from the environment.

## Model provider

The copilot runs on a **single model** and can switch between paid APIs and a
local one. Pick it in the UI (or `--provider` on the CLI).

| Provider | Cost | Needs |
| --- | --- | --- |
| `anthropic` (default) | paid | Anthropic key |
| `openai` | paid | OpenAI key, `.[openai]` |
| `local` | free | a local server, `.[local]` |

For `local`, set any OpenAI-compatible URL in the UI (Agent tab) — Ollama
(`http://localhost:11434/v1`), LM Studio (`:1234/v1`), vLLM (`:8000/v1`). Use a
recent tool-calling model (llama3.1, qwen2.5, mistral); if it can't return valid
structured output the run still completes via the evidence-based fallback. For the
best reports, prefer Anthropic or a strong instruct model.

## AWS access (read-only)

The copilot only makes read-only data-plane calls. The key or role needs:

```
logs:StartQuery, logs:GetQueryResults, logs:StopQuery,
cloudwatch:GetMetricData, ecs:Describe*, ecs:List*,
elasticloadbalancing:Describe*
```

A ready policy is at [`demo/copilot-readonly-policy.json`](../demo/copilot-readonly-policy.json).
Leave the AWS fields blank in the UI to use your host's default credential chain.

## Test

```bash
pytest tests/   # end-to-end against stubbed AWS + LLM, no creds needed
```

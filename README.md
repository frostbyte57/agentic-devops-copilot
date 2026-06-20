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

╭────────────────────────── IncidentReport ✓ ──────────────────────────╮
│ Root cause: Inefficient DB query (N+1) introduced in the last deploy. │
│ Recommended fix: Add .select_related() to /users; scale ECS to 4.     │
│ Confidence: 91%                                                       │
╰──────────────────────────────────────────────────────────────────────╯
```

## How it works

A LangGraph state graph orchestrates specialized agents:

1. **Planner** (Opus) decomposes the incident into investigation threads.
2. Specialist nodes fan out **in parallel**: CloudWatch **Logs**, **Metrics**,
   **GitHub** deploy-diff, **RAG** runbook retrieval.
3. **Code Executor** writes and runs a small sandboxed script to quantify the
   leading hypothesis when the evidence can't state it directly.
4. **Critic** (Opus) challenges the leading hypothesis and sets a calibrated
   confidence.
5. **Synthesizer** (Opus) emits the final structured `IncidentReport`.

Models (via `langchain-anthropic`): `claude-opus-4-8` for planner/critic/
synthesizer, `claude-sonnet-4-6` for the high-volume specialist summarizers.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .            # add ".[github]" for the deploy-diff node
cp .env.example .env        # set ANTHROPIC_API_KEY + AWS creds
```

AWS access is **read-only** — see the IAM actions below. The copilot never holds
write permissions.

```
logs:StartQuery, logs:GetQueryResults, logs:StopQuery,
cloudwatch:GetMetricData, ecs:Describe*, ecs:List*,
elasticloadbalancing:Describe*
```

Optionally set `COPILOT_READONLY_ROLE_ARN` to have the copilot assume a dedicated
read-only role via STS.

## Choosing a model provider

Switch the whole copilot between paid APIs and a model running on your laptop
with one variable. The graph asks for a *tier* (`reasoning` vs `fast`), so the
roles stay the same no matter which provider you pick.

| `COPILOT_PROVIDER` | Cost | Needs | Install |
| --- | --- | --- | --- |
| `anthropic` (default) | paid | `ANTHROPIC_API_KEY` | `pip install -e .` |
| `openai` | paid | `OPENAI_API_KEY` | `pip install -e '.[openai]'` |
| `local` | free | a local server | `pip install -e '.[local]'` |

```bash
copilot models                       # show the resolved models for the active provider
copilot investigate --provider local "..."   # one-off override

# Run fully on your laptop (no API key, nothing leaves the machine):
ollama pull llama3.1 && ollama serve
COPILOT_PROVIDER=local copilot investigate "..."
```

Every model id is overridable (e.g. `COPILOT_OPENAI_REASONING_MODEL`,
`COPILOT_LOCAL_FAST_MODEL`) and `COPILOT_LOCAL_BASE_URL` points at any
OpenAI-compatible server — Ollama (`:11434/v1`, default), LM Studio
(`:1234/v1`) or vLLM (`:8000/v1`). See `.env.example` for the full list. Note
the structured-output nodes (planner/critic/synthesizer) need a local model with
tool-calling support — recent instruct models (llama3.1, qwen2.5, mistral) work.

## Run

```bash
copilot investigate "ECS service api-prod returning 503s for 20 minutes"
copilot investigate --no-code-exec --json "RDS db-prod CPU at 100% since 14:00"
```

## Test

```bash
pytest tests/          # runs end-to-end against stubbed AWS + LLM (no creds needed)
```

## Security notes

- The **Code Executor** is the only place model-written code runs. It executes in
  a subprocess with a scrubbed environment, a temp working directory, a hard
  timeout, and POSIX resource limits. Treat generated scripts as untrusted.
- Secrets come from the environment / standard AWS credential chain and are never
  logged or placed in prompts.

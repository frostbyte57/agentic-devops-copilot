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

The copilot runs on a single model (default `claude-opus-4-8` via
`langchain-anthropic`), used by every node.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[server]'   # add ".[github]" for the deploy-diff node
```

All configuration — provider, model, API keys, AWS region/credentials — is set
in the web UI's **Configuration** panel and persisted outside the repo. Nothing
is read from the environment.

AWS access is **read-only** — see the IAM actions below. The copilot never holds
write permissions.

```
logs:StartQuery, logs:GetQueryResults, logs:StopQuery,
cloudwatch:GetMetricData, ecs:Describe*, ecs:List*,
elasticloadbalancing:Describe*
```

If you leave the AWS credentials blank, boto3 falls back to your host's default
chain (shared `~/.aws` profile or instance role).

## Choosing a model provider

The copilot runs on a single model and can switch between paid APIs and a model
running on your laptop. Pick the provider and model in the UI (or `--provider` on
the CLI); the model dropdown lists what your saved key can reach.

| Provider | Cost | Needs | Install |
| --- | --- | --- | --- |
| `anthropic` (default) | paid | Anthropic key | `pip install -e .` |
| `openai` | paid | OpenAI key | `pip install -e '.[openai]'` |
| `local` | free | a local server | `pip install -e '.[local]'` |

```bash
copilot models                       # show the resolved model for the active provider
copilot investigate --provider local "..."   # one-off override
```

For `local`, set the server URL in the UI (Agent tab) — any OpenAI-compatible
endpoint: Ollama (`:11434/v1`, default), LM Studio (`:1234/v1`) or vLLM
(`:8000/v1`). The structured-output nodes (planner/critic/synthesizer) need a
local model with tool-calling support — recent instruct models (llama3.1,
qwen2.5, mistral) work.

## Run (CLI)

```bash
copilot investigate "ECS service api-prod returning 503s for 20 minutes"
copilot investigate --no-code-exec --json "RDS db-prod CPU at 100% since 14:00"
```

## Run (Web UI)

A ChatGPT-style web app (`web/`, React + React Router on Vite) talks to a small
FastAPI backend that streams each investigation step live. The chat surface is
built with the [shadcn-chatbot-kit](https://github.com/Blazity/shadcn-chatbot-kit)
(`src/components/ui/chat.tsx` et al., on top of shadcn/ui) — auto-scrolling
message list, markdown rendering, prompt suggestions, and a stop button. It's a
static SPA — no Next.js, no Vercel, no Node server. The **Configuration** panel
holds **all your credentials** (Anthropic, OpenAI, GitHub, AWS), the AWS region,
and the code-executor toggle; the model is switched from the chat bar. Everything
is handled in the UI — no env vars, no `.env`, no restarts.

**One command** (installs nothing — run `make install` first):

```bash
make install   # Python (all extras) + web deps
make dev       # API on :8000 + web UI on :3000 — Ctrl-C stops both
```

Then open **http://localhost:3000**. Other targets: `make backend`,
`make frontend`, `make test`, `make help`.

<details><summary>…or run the two processes manually</summary>

```bash
pip install -e '.[server]'
uvicorn copilot.server:app --reload --port 8000     # terminal 1
cd web && npm install && npm run dev                # terminal 2
```
</details>

Keys and settings entered in the UI are persisted to
`~/.config/aws-devops-copilot/settings.json` (a `0600` file, outside the repo)
and loaded on the next start, so you configure once. The frontend reads the
backend URL from `web/.env` (`VITE_API_BASE`, default `http://localhost:8000`).
Build static assets for deployment anywhere with `cd web && npm run build`
(output in `web/dist/`).

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

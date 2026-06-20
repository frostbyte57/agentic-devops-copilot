# Run (Web UI)

A ChatGPT-style web app (`web/`, React + React Router on Vite) talks to a small
FastAPI backend that streams each investigation step live over SSE. The chat
surface is built with the
[shadcn-chatbot-kit](https://github.com/Blazity/shadcn-chatbot-kit)
(`src/components/ui/chat.tsx` et al., on top of shadcn/ui) — auto-scrolling
message list, markdown rendering, prompt suggestions, and a stop button. It's a
static SPA — no Next.js, no Vercel, no Node server.

The **Configuration** panel holds **all your credentials** (Anthropic, OpenAI,
GitHub, AWS), the AWS region, and the code-executor toggle; the model is switched
from the chat bar. Everything is handled in the UI — no env vars, no `.env`, no
restarts.

## One command

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

## Persistence & build

Keys and settings entered in the UI are persisted to
`~/.config/aws-devops-copilot/settings.json` (a `0600` file, outside the repo) and
loaded on the next start, so you configure once. The frontend reads the backend
URL from `web/.env` (`VITE_API_BASE`, default `http://localhost:8000`).

Build static assets for deployment anywhere:

```bash
cd web && npm run build   # output in web/dist/
```

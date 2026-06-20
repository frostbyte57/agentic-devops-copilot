# Security notes

- **Read-only AWS.** The copilot only makes read-only data-plane calls
  (CloudWatch Logs/Metrics, ECS describe/list). Scope the key or role you give it
  to the actions in [setup.md](./setup.md); nothing in the code can escalate
  beyond that. Leave the AWS fields blank to use your host's default credential
  chain instead.

- **Credentials stay in the settings store.** Keys and AWS credentials entered in
  the UI are written to `~/.config/aws-devops-copilot/settings.json` (a `0600`
  file, outside the repo) and are never logged or placed in prompts. The API
  redacts them — `GET /api/settings` returns only `has_*` presence flags, never
  the values. Nothing is read from or written to the environment.

- **The Code Executor is the only place model-written code runs.** It executes in
  a subprocess with a scrubbed environment (no credentials passed through), a
  temporary working directory, a hard wall-clock timeout, and POSIX resource
  limits. Treat generated scripts as untrusted; disable the node with
  `--no-code-exec` (CLI) or the Agent tab toggle (UI) if you prefer.

- **Plaintext secrets caveat.** The settings file stores secrets in plaintext at
  `0600` — acceptable for a local single-user tool, the same trust level as a
  `.env`. Don't run this as a shared/multi-user service without adding real
  secret storage.

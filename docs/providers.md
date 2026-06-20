# Choosing a model provider

The copilot runs on a **single model** and can switch between paid APIs and a
model running on your laptop. Pick the provider and model in the UI (or
`--provider` on the CLI); the model dropdown lists what your saved key can reach.

| Provider | Cost | Needs | Install |
| --- | --- | --- | --- |
| `anthropic` (default) | paid | Anthropic key | `pip install -e .` |
| `openai` | paid | OpenAI key | `pip install -e '.[openai]'` |
| `local` | free | a local server | `pip install -e '.[local]'` |

```bash
copilot models                                # resolved model for the active provider
copilot investigate --provider local "..."    # one-off override
```

## Local models

For `local`, set the server URL in the UI (Agent tab) — any OpenAI-compatible
endpoint works:

- Ollama — `http://localhost:11434/v1` (default)
- LM Studio — `http://localhost:1234/v1`
- vLLM — `http://localhost:8000/v1`

The structured-output nodes (planner, critic, synthesizer) need a model with
tool-calling support — recent instruct models (llama3.1, qwen2.5, mistral) work.
If a local model can't return valid structured output, the run still completes:
the synthesizer falls back to a report built from the gathered evidence (so for a
high-quality structured report, prefer Anthropic or a strong instruct model).

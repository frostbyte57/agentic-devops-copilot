# Architecture

A [LangGraph](https://github.com/langchain-ai/langgraph) state graph orchestrates
a set of specialized agents. You describe an incident in plain English; the graph
investigates your live AWS environment and returns a structured `IncidentReport`.

## Pipeline

1. **Planner** decomposes the incident into investigation threads — it extracts
   the service name and a lookback window, and decides which evidence sources are
   worth querying.
2. Specialist nodes fan out **in parallel**, each appending `Evidence`:
   - **CloudWatch Logs** — scans the service's log group for error/5xx/timeout
     lines and summarizes the dominant signature.
   - **Metrics** — pulls ECS CPU/memory series and flags breaches.
   - **GitHub** — diffs the most recent deploy for risky changes (optional).
   - **Runbooks (RAG)** — retrieves matching runbooks for the symptom.
3. **Code Executor** (optional) writes and runs a small sandboxed Python script to
   quantify the leading hypothesis when the evidence can't state it directly.
4. **Critic** challenges the leading hypothesis and sets a calibrated confidence.
5. **Synthesizer** emits the final `IncidentReport` — root cause, supporting
   evidence, a concrete fix, a confidence score, and commands to run. If the model
   can't produce structured output, it falls back to a report built from the
   gathered evidence so a run always finishes.

The copilot runs on a **single model** (default `claude-opus-4-8`), used by every
LLM node. AWS calls are **read-only**.

## Investigation flow

```mermaid
flowchart TD
    U(["User: plain-English incident"]) --> IF

    subgraph IF[Interfaces]
        WEB["Web UI (chat)<br/>streams SSE: meta · step · report"]
        CLI["CLI: copilot investigate"]
    end

    IF --> P

    subgraph GRAPH["LangGraph agent (single model per call)"]
        P["Planner<br/>extract service + window<br/>pick 2–5 threads"]
        P -->|fans out to chosen sources| LOGS
        P --> MET
        P --> GH
        P --> RAG

        LOGS["CloudWatch Logs<br/>error/5xx/timeout scan → summary"]
        MET["Metrics<br/>ECS CPU / memory → breach check"]
        GH["GitHub diff<br/>risky changes in last deploy"]
        RAG["Runbooks (RAG)<br/>keyword match over local corpus"]

        LOGS --> G
        MET --> G
        GH --> G
        RAG --> G

        G(["gather: merge Evidence"])
        G --> CODE
        CODE["Code Executor (optional)<br/>sandboxed Python to quantify<br/>a hypothesis"]
        CODE --> CRIT
        CRIT["Critic<br/>argue against obvious cause,<br/>set calibrated confidence"]
        CRIT --> SYN
        SYN["Synthesizer<br/>root cause + fix + commands<br/>(falls back to evidence if needed)"]
    end

    SYN --> REP[["IncidentReport<br/>root cause · evidence · fix · confidence"]]
    REP --> IF

    LOGS -. read-only .-> AWS[("AWS: CloudWatch Logs<br/>Metrics, ECS")]
    MET -. read-only .-> AWS
    GH -. API .-> GHAPI[("GitHub API")]
    RAG -. files .-> RB[("runbooks/*.md")]

    P & LOGS & MET & GH & CODE & CRIT & SYN -. chat .-> LLM{{"LLM provider<br/>anthropic / openai / local"}}

    classDef ext fill:#1f2937,stroke:#6b7280,color:#e5e7eb;
    class AWS,GHAPI,RB,LLM ext;
```

## Configuration & credentials

Everything is configured in the UI and persisted to a single settings store —
nothing is read from the environment. `providers.resolve()`, the AWS session, and
the GitHub node all read from that store.

```mermaid
flowchart LR
    UI["Web UI Configuration<br/>provider · model · keys · AWS · region"]
    UI -->|PUT /api/settings| STORE[("settings_store<br/>~/.config/.../settings.json (0600)")]

    STORE --> RES["providers.resolve()<br/>→ model + api_key + base_url"]
    STORE --> AWSAD["AwsAdapters.from_settings()<br/>→ region + read-only creds"]
    STORE --> GHCFG["github token + repo<br/>(via Deps)"]

    RES --> NODES["LLM nodes<br/>(planner · critic · synthesizer · summaries)"]
    AWSAD --> AWSNODES["Logs + Metrics nodes"]
    GHCFG --> GHNODE["GitHub diff node"]

    note["No environment variables —<br/>the UI store is the single source of truth"]
    STORE -.- note
    classDef n fill:#0b3d2e,stroke:#10b981,color:#d1fae5;
    class note n;
```

- The **planner** decides which sources run; only those branches execute, in
  parallel, each appending `Evidence`.
- After `gather`, the flow is sequential: **code executor → critic → synthesizer**.
- Every LLM node resolves to the single configured model; AWS calls are read-only.
- All config flows from the **UI → settings store**, never from env vars.

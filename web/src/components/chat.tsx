import { useRef, useState } from "react";

import { ModelPicker } from "@/components/model-picker";
import { Chat as ChatUI } from "@/components/ui/chat";
import { type Message } from "@/components/ui/chat-message";
import { investigate } from "@/lib/api";
import type { ProviderInfo, Report, Settings, StepEvidence } from "@/lib/types";

const SUGGESTIONS = [
  "ECS service api-prod returning 503s for 20 minutes",
  "RDS db-prod CPU at 100% since 14:00",
  "Latency spike on checkout-svc after the last deploy",
];

const SEV: Record<StepEvidence["severity"], string> = {
  info: "🔹",
  warning: "🟠",
  critical: "🔴",
};

// Live accumulator for the assistant turn, rendered to markdown as events arrive.
type Acc = {
  meta: string | null;
  steps: { label: string; evidence: StepEvidence[] }[];
  report: Report | null;
  error: string | null;
};

function renderMarkdown(a: Acc): string {
  const out: string[] = [];
  if (a.meta) out.push(`*${a.meta}*`);
  for (const s of a.steps) {
    out.push(`\n**${s.label}**`);
    for (const e of s.evidence) {
      out.push(`- ${SEV[e.severity]} \`${e.source}\` — ${e.summary}`);
    }
  }
  if (a.error) out.push(`\n> ⚠️ ${a.error}`);
  if (a.report) {
    const r = a.report;
    out.push(`\n---\n### Incident Report · ${Math.round(r.confidence * 100)}% confidence`);
    out.push(`\n**Root cause:** ${r.root_cause}`);
    out.push(`\n**Recommended fix:** ${r.recommended_fix}`);
    if (r.evidence_refs.length) {
      out.push(`\n**Evidence**`);
      for (const e of r.evidence_refs) out.push(`- ${e}`);
    }
    if (r.commands_to_run.length) {
      out.push(`\n**Commands**\n\`\`\`bash`);
      for (const c of r.commands_to_run) out.push(c);
      out.push("```");
    }
  }
  if (!a.steps.length && !a.report && !a.error) out.push("_Investigating…_");
  return out.join("\n");
}

export function Chat({
  providers,
  settings,
  onSettingsChange,
}: {
  providers: ProviderInfo[];
  settings: Settings | null;
  onSettingsChange: (s: Settings) => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  function setAssistant(id: string, acc: Acc) {
    const content = renderMarkdown(acc);
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, content } : m)),
    );
  }

  async function run(incident: string) {
    const text = incident.trim();
    if (!text || isGenerating) return;

    const userId = crypto.randomUUID();
    const botId = crypto.randomUUID();
    setMessages((prev) => [
      ...prev,
      { id: userId, role: "user", content: text },
      { id: botId, role: "assistant", content: "_Investigating…_" },
    ]);
    setIsGenerating(true);

    const acc: Acc = { meta: null, steps: [], report: null, error: null };
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    await investigate(
      text,
      {
        onMeta: (m) => {
          acc.meta = `${m.provider} · ${m.model}`;
          setAssistant(botId, acc);
        },
        onStep: (s) => {
          acc.steps.push({ label: s.label, evidence: s.evidence });
          setAssistant(botId, acc);
        },
        onReport: (r) => {
          acc.report = r;
          setAssistant(botId, acc);
        },
        onError: (msg) => {
          acc.error = msg;
          setAssistant(botId, acc);
        },
        onDone: () => {},
      },
      ctrl.signal,
    ).catch((e) => {
      if ((e as Error).name !== "AbortError") {
        acc.error = String(e);
        setAssistant(botId, acc);
      }
    });

    setIsGenerating(false);
    abortRef.current = null;
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col overflow-hidden px-4 py-4">
      <ChatUI
        className="flex-1"
        messages={messages}
        input={input}
        handleInputChange={(e) => setInput(e.target.value)}
        handleSubmit={(e) => {
          e?.preventDefault?.();
          const text = input;
          setInput("");
          run(text);
        }}
        isGenerating={isGenerating}
        stop={() => abortRef.current?.abort()}
        append={(msg) => run(msg.content)}
        suggestions={SUGGESTIONS}
        inputFooter={
          settings && providers.length > 0 ? (
            <ModelPicker
              providers={providers}
              settings={settings}
              onChange={onSettingsChange}
            />
          ) : null
        }
      />
    </div>
  );
}

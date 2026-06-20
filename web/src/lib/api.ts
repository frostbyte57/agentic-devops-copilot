import type {
  ModelOption,
  ProviderInfo,
  Report,
  Settings,
  SettingsUpdate,
  Step,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export async function getProviders(): Promise<ProviderInfo[]> {
  const res = await fetch(`${BASE}/api/providers`);
  if (!res.ok) throw new Error("Failed to load providers");
  return (await res.json()).providers;
}

/** Models the given provider's stored key can reach. May be empty (no key / offline). */
export async function getModels(provider: string): Promise<ModelOption[]> {
  const res = await fetch(`${BASE}/api/models?provider=${encodeURIComponent(provider)}`);
  if (!res.ok) throw new Error("Failed to load models");
  const body = await res.json();
  if (body.error) throw new Error(body.error);
  return body.models as ModelOption[];
}

export async function getSettings(): Promise<Settings> {
  const res = await fetch(`${BASE}/api/settings`);
  if (!res.ok) throw new Error("Failed to load settings");
  return res.json();
}

export async function saveSettings(s: SettingsUpdate): Promise<Settings> {
  const res = await fetch(`${BASE}/api/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(s),
  });
  if (!res.ok) throw new Error("Failed to save settings");
  return res.json();
}

export type StreamHandlers = {
  onMeta?: (m: { provider: string; model: string }) => void;
  onStep?: (s: Step) => void;
  onReport?: (r: Report) => void;
  onError?: (message: string) => void;
  onDone?: () => void;
};

/** POST to /api/investigate and parse the SSE stream from the fetch body. */
export async function investigate(
  incident: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}/api/investigate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ incident }),
    signal,
  });
  if (!res.ok || !res.body) {
    handlers.onError?.(`Request failed (${res.status})`);
    handlers.onDone?.();
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line.
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      let event = "message";
      let data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      const payload = JSON.parse(data);
      if (event === "meta") handlers.onMeta?.(payload);
      else if (event === "step") handlers.onStep?.(payload);
      else if (event === "report") handlers.onReport?.(payload);
      else if (event === "error") handlers.onError?.(payload.message);
      else if (event === "done") handlers.onDone?.();
    }
  }
}

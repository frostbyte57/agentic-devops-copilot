import { useEffect, useRef, useState } from "react";
import { ChevronDown, Cpu, Loader2, Lock } from "lucide-react";
import { toast } from "sonner";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getModels, saveSettings } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ModelOption, ProviderInfo, Settings } from "@/lib/types";

// Which presence flag on Settings unlocks each paid provider.
const KEY_FLAG: Partial<Record<string, keyof Settings>> = {
  anthropic: "has_anthropic_key",
  openai: "has_openai_key",
};

/**
 * Model switcher on the chat bar. Picks the provider (paid ones unlock once their
 * key is saved) and the reasoning + fast models, choosing from the live list the
 * provider's key can actually reach.
 */
export function ModelPicker({
  providers,
  settings,
  onChange,
}: {
  providers: ProviderInfo[];
  settings: Settings;
  onChange: (s: Settings) => void;
}) {
  const [open, setOpen] = useState(false);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const current = providers.find((p) => p.id === settings.provider);
  const unlocked = (p: ProviderInfo) => {
    if (p.kind === "local") return true;
    const flag = KEY_FLAG[p.id];
    return flag ? Boolean(settings[flag]) : true;
  };

  // (Re)load the model list whenever the panel opens or the provider changes.
  useEffect(() => {
    if (!open) return;
    setLoading(true);
    getModels(settings.provider)
      .then(setModels)
      .catch(() => setModels([]))
      .finally(() => setLoading(false));
  }, [open, settings.provider]);

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  async function persist(patch: Partial<Settings>) {
    setBusy(true);
    try {
      const saved = await saveSettings({
        provider: settings.provider,
        model: settings.model,
        region: settings.region,
        local_base_url: settings.local_base_url,
        github_repo: settings.github_repo,
        allow_code_exec: settings.allow_code_exec,
        ...patch,
      });
      onChange(saved);
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(false);
    }
  }

  function switchProvider(p: ProviderInfo) {
    if (p.id === settings.provider) return;
    // New provider → start from its default; the live list then refines it.
    void persist({ provider: p.id, model: p.default_model });
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label="Model"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
      >
        <Cpu className="size-3.5" />
        <span className="font-medium text-foreground">{current?.label ?? settings.provider}</span>
        <span className="text-muted-foreground">· {settings.model}</span>
        <ChevronDown className="size-3.5" />
      </button>

      {open && (
        <div className="absolute bottom-full left-0 z-50 mb-2 w-80 rounded-xl border bg-popover p-3 shadow-md">
          {/* Provider */}
          <div className="mb-3 grid gap-1.5">
            <Label>Provider</Label>
            <div className="flex flex-wrap gap-1.5">
              {providers.map((p) => {
                const ok = unlocked(p);
                const active = p.id === settings.provider;
                return (
                  <button
                    key={p.id}
                    type="button"
                    disabled={!ok || busy}
                    onClick={() => switchProvider(p)}
                    className={cn(
                      "flex items-center gap-1 rounded-md border px-2 py-1 text-xs transition-colors",
                      active
                        ? "border-primary bg-primary/10 text-foreground"
                        : "text-muted-foreground hover:bg-accent",
                      !ok && "cursor-not-allowed opacity-50",
                    )}
                  >
                    {!ok && <Lock className="size-2.5" />}
                    {p.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Model */}
          <ModelSelect
            label="Model"
            value={settings.model}
            models={models}
            loading={loading}
            disabled={busy}
            onSelect={(id) => persist({ model: id })}
          />

          {!loading && models.length === 0 && (
            <p className="mt-2.5 text-[11px] text-muted-foreground">
              No models found — check the {settings.provider === "local" ? "server URL" : "API key"}.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function ModelSelect({
  label,
  value,
  models,
  loading,
  disabled,
  onSelect,
}: {
  label: string;
  value: string;
  models: ModelOption[];
  loading: boolean;
  disabled: boolean;
  onSelect: (id: string) => void;
}) {
  // Make sure the currently-selected model is always shown, even if the live
  // list doesn't include it (e.g. a stale default the key can't reach).
  const options = models.some((m) => m.id === value)
    ? models
    : [{ id: value, label: value }, ...models];

  return (
    <div className="grid gap-1.5">
      <Label>{label}</Label>
      <Select
        value={value}
        onValueChange={(v) => v && onSelect(v)}
        disabled={disabled || loading}
      >
        <SelectTrigger size="sm" className="w-full">
          {loading ? (
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" /> Loading…
            </span>
          ) : (
            <SelectValue />
          )}
        </SelectTrigger>
        <SelectContent className="max-h-64">
          {options.map((m) => (
            <SelectItem key={m.id} value={m.id}>
              {m.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <span className="text-xs font-medium">{children}</span>;
}

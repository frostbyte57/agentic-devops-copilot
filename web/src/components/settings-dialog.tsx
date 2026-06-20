import { useEffect, useState } from "react";
import { Settings as SettingsIcon } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getProviders, getSettings, saveSettings } from "@/lib/api";
import type { ProviderInfo, Settings } from "@/lib/types";

type Keys = { anthropic: string; openai: string; github: string };
const EMPTY_KEYS: Keys = { anthropic: "", openai: "", github: "" };

export function SettingsDialog({ onSaved }: { onSaved?: (s: Settings) => void }) {
  const [open, setOpen] = useState(false);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [keys, setKeys] = useState<Keys>(EMPTY_KEYS);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    Promise.all([getProviders(), getSettings()])
      .then(([p, s]) => {
        setProviders(p);
        setSettings(s);
        setKeys(EMPTY_KEYS);
      })
      .catch((e) => toast.error(String(e)));
  }, [open]);

  function pickProvider(id: string | null) {
    const p = providers.find((x) => x.id === id);
    if (!p || !settings) return;
    // Switch to that provider's defaults so the model fields stay valid.
    setSettings({
      ...settings,
      provider: p.id,
      reasoning_model: p.default_reasoning_model,
      fast_model: p.default_fast_model,
    });
  }

  function set<K extends keyof Settings>(key: K, value: Settings[K]) {
    if (!settings) return;
    setSettings({ ...settings, [key]: value });
  }

  async function onSave() {
    if (!settings) return;
    setSaving(true);
    try {
      const saved = await saveSettings({
        ...settings,
        anthropic_key: keys.anthropic || null,
        openai_key: keys.openai || null,
        github_token: keys.github || null,
      });
      setSettings(saved);
      onSaved?.(saved);
      toast.success("Settings saved");
      setOpen(false);
    } catch (e) {
      toast.error(String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant="outline" size="icon" aria-label="Settings" />}>
        <SettingsIcon className="h-4 w-4" />
      </DialogTrigger>
      <DialogContent className="gap-0 sm:max-w-[540px]">
        <DialogHeader className="pb-1">
          <DialogTitle>Configuration</DialogTitle>
          <DialogDescription>
            Changes apply to the next investigation.
          </DialogDescription>
        </DialogHeader>

        {settings && (
          <Tabs defaultValue="model" className="mt-3">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="model">Model</TabsTrigger>
              <TabsTrigger value="keys">API Keys</TabsTrigger>
              <TabsTrigger value="agent">Agent</TabsTrigger>
            </TabsList>

            {/* ── Model ─────────────────────────────────────────── */}
            <TabsContent value="model" className="mt-4 min-h-[248px] space-y-4">
              <Field label="Provider">
                <Select value={settings.provider} onValueChange={pickProvider}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {providers.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        <span className="flex w-full items-center justify-between gap-3">
                          {p.label}
                          <span className="text-xs text-muted-foreground">
                            {p.kind === "local" ? "free" : "paid"}
                          </span>
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>

              <div className="grid grid-cols-2 gap-3">
                <Field label="Reasoning model">
                  <Input
                    value={settings.reasoning_model}
                    onChange={(e) => set("reasoning_model", e.target.value)}
                  />
                </Field>
                <Field label="Fast model">
                  <Input
                    value={settings.fast_model}
                    onChange={(e) => set("fast_model", e.target.value)}
                  />
                </Field>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Reasoning drives the planner, critic & synthesizer; fast handles the
                high-volume log, metric & diff summaries.
              </p>

              {settings.provider === "local" && (
                <Field label="Local server URL">
                  <Input
                    placeholder="http://localhost:11434/v1"
                    value={settings.local_base_url ?? ""}
                    onChange={(e) => set("local_base_url", e.target.value)}
                  />
                </Field>
              )}
            </TabsContent>

            {/* ── API Keys ──────────────────────────────────────── */}
            <TabsContent value="keys" className="mt-4 min-h-[248px] space-y-4">
              <p className="text-xs text-muted-foreground">
                Stored securely on the server and reused across restarts. Leave a field
                blank to keep its current value.
              </p>
              <KeyInput
                label="Anthropic"
                placeholder="sk-ant-..."
                stored={settings.has_anthropic_key}
                value={keys.anthropic}
                onChange={(v) => setKeys((k) => ({ ...k, anthropic: v }))}
              />
              <KeyInput
                label="OpenAI"
                placeholder="sk-..."
                stored={settings.has_openai_key}
                value={keys.openai}
                onChange={(v) => setKeys((k) => ({ ...k, openai: v }))}
              />
              <KeyInput
                label="GitHub token"
                hint="optional · for deploy diffs"
                placeholder="ghp_..."
                stored={settings.has_github_token}
                value={keys.github}
                onChange={(v) => setKeys((k) => ({ ...k, github: v }))}
              />
            </TabsContent>

            {/* ── Agent ─────────────────────────────────────────── */}
            <TabsContent value="agent" className="mt-4 min-h-[248px] space-y-4">
              <Field label="AWS region">
                <Input
                  placeholder="us-east-1"
                  value={settings.region ?? ""}
                  onChange={(e) => set("region", e.target.value)}
                />
              </Field>

              <label className="flex cursor-pointer items-center justify-between rounded-lg border p-3.5">
                <span className="space-y-0.5 pr-4">
                  <span className="block text-sm font-medium">Code executor</span>
                  <span className="block text-xs text-muted-foreground">
                    Let the agent run sandboxed Python to analyse evidence.
                  </span>
                </span>
                <Switch
                  checked={settings.allow_code_exec}
                  onCheckedChange={(v) => set("allow_code_exec", v)}
                />
              </label>
            </TabsContent>
          </Tabs>
        )}

        <DialogFooter className="mt-2 border-t pt-4">
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={onSave} disabled={saving || !settings}>
            {saving ? "Saving…" : "Save changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-1.5">
      <div className="flex items-baseline justify-between">
        <Label>{label}</Label>
        {hint && <span className="text-[11px] text-muted-foreground">{hint}</span>}
      </div>
      {children}
    </div>
  );
}

function KeyInput({
  label,
  hint,
  placeholder,
  stored,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
  placeholder: string;
  stored: boolean;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="grid gap-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Label>{label}</Label>
          {stored && (
            <Badge variant="secondary" className="h-4 px-1.5 text-[10px] font-medium">
              Set
            </Badge>
          )}
        </div>
        {hint && <span className="text-[11px] text-muted-foreground">{hint}</span>}
      </div>
      <Input
        type="password"
        autoComplete="off"
        placeholder={stored ? "•••••••• (leave blank to keep)" : placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

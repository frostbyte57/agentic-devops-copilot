import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
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
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getSettings, saveSettings } from "@/lib/api";
import type { Settings } from "@/lib/types";

type Keys = {
  anthropic: string;
  openai: string;
  github: string;
  awsAccessKeyId: string;
  awsSecretAccessKey: string;
};
const EMPTY_KEYS: Keys = {
  anthropic: "",
  openai: "",
  github: "",
  awsAccessKeyId: "",
  awsSecretAccessKey: "",
};

export function SettingsDialog({ onSaved }: { onSaved?: (s: Settings) => void }) {
  const [open, setOpen] = useState(false);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [keys, setKeys] = useState<Keys>(EMPTY_KEYS);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    getSettings()
      .then((s) => {
        setSettings(s);
        setKeys(EMPTY_KEYS);
      })
      .catch((e) => toast.error(String(e)));
  }, [open]);

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
        aws_access_key_id: keys.awsAccessKeyId || null,
        aws_secret_access_key: keys.awsSecretAccessKey || null,
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
      <DialogContent className="gap-0 sm:max-w-[520px]">
        <DialogHeader className="pb-1">
          <DialogTitle>Configuration</DialogTitle>
          <DialogDescription>Stored on the server.</DialogDescription>
        </DialogHeader>

        {settings && (
          <Tabs defaultValue="keys" className="mt-3">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="keys">Credentials</TabsTrigger>
              <TabsTrigger value="agent">Agent</TabsTrigger>
            </TabsList>

            <AutoHeight>
              {/* ── Credentials ───────────────────────────────────── */}
              <TabsContent value="keys" className="space-y-6">
                <Section title="Models">
                  <KeyInput
                    label="Anthropic"
                    stored={settings.has_anthropic_key}
                    value={keys.anthropic}
                    onChange={(v) => setKeys((k) => ({ ...k, anthropic: v }))}
                  />
                  <KeyInput
                    label="OpenAI"
                    stored={settings.has_openai_key}
                    value={keys.openai}
                    onChange={(v) => setKeys((k) => ({ ...k, openai: v }))}
                  />
                </Section>

                <Section title="AWS" hint="Blank → host profile / role">
                  <Field label="Region">
                    <Input
                      value={settings.region ?? ""}
                      onChange={(e) => set("region", e.target.value)}
                    />
                  </Field>
                  <KeyInput
                    label="Access key ID"
                    stored={settings.has_aws_credentials}
                    value={keys.awsAccessKeyId}
                    onChange={(v) => setKeys((k) => ({ ...k, awsAccessKeyId: v }))}
                  />
                  <KeyInput
                    label="Secret access key"
                    stored={settings.has_aws_credentials}
                    value={keys.awsSecretAccessKey}
                    onChange={(v) => setKeys((k) => ({ ...k, awsSecretAccessKey: v }))}
                  />
                </Section>

                <Section title="GitHub" hint="Optional · deploy diffs">
                  <KeyInput
                    label="Token"
                    stored={settings.has_github_token}
                    value={keys.github}
                    onChange={(v) => setKeys((k) => ({ ...k, github: v }))}
                  />
                  <Field label="Repo">
                    <Input
                      value={settings.github_repo ?? ""}
                      onChange={(e) => set("github_repo", e.target.value)}
                    />
                  </Field>
                </Section>
              </TabsContent>

              {/* ── Agent ─────────────────────────────────────────── */}
              <TabsContent value="agent" className="space-y-5">
                <label className="flex cursor-pointer items-center justify-between rounded-lg border p-3.5">
                  <span className="space-y-0.5 pr-4">
                    <span className="block text-sm font-medium">Code executor</span>
                    <span className="block text-xs text-muted-foreground">
                      Run sandboxed Python on evidence.
                    </span>
                  </span>
                  <Switch
                    checked={settings.allow_code_exec}
                    onCheckedChange={(v) => set("allow_code_exec", v)}
                  />
                </label>

                <Field label="Local server URL">
                  <Input
                    value={settings.local_base_url ?? ""}
                    onChange={(e) => set("local_base_url", e.target.value)}
                  />
                </Field>
              </TabsContent>
            </AutoHeight>
          </Tabs>
        )}

        <DialogFooter className="mt-6 border-t pt-4">
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={onSave} disabled={saving || !settings}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Section({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-3">
      <div className="flex items-baseline justify-between border-b pb-1.5">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          {title}
        </span>
        {hint && <span className="text-[11px] text-muted-foreground/70">{hint}</span>}
      </div>
      {children}
    </div>
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
  stored,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
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
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

/**
 * Animates its own height to match its content, so switching between the
 * Credentials and Agent tabs resizes the card smoothly instead of snapping.
 */
function AutoHeight({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState<number | "auto">("auto");

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(() => setHeight(el.offsetHeight));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <motion.div
      animate={{ height }}
      transition={{ duration: 0.22, ease: "easeInOut" }}
      // -mx/px pair keeps content aligned while giving focus rings room not to clip.
      className="-mx-1 overflow-hidden"
    >
      <div ref={ref} className="px-1 pt-5">
        {children}
      </div>
    </motion.div>
  );
}

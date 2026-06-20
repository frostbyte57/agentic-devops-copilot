import { useEffect, useState } from "react";
import { Activity } from "lucide-react";

import { Chat } from "@/components/chat";
import { SettingsDialog } from "@/components/settings-dialog";
import { getSettings } from "@/lib/api";
import type { Settings } from "@/lib/types";

export default function Home() {
  const [settings, setSettings] = useState<Settings | null>(null);

  useEffect(() => {
    getSettings().then(setSettings).catch(() => setSettings(null));
  }, []);

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" />
          <span className="font-semibold">AWS DevOps Copilot</span>
          {settings && (
            <span className="ml-2 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
              {settings.provider} · {settings.reasoning_model}
            </span>
          )}
        </div>
        <SettingsDialog onSaved={setSettings} />
      </header>
      <Chat />
    </div>
  );
}

import { useEffect, useState } from "react";
import { Activity } from "lucide-react";

import { Chat } from "@/components/chat";
import { SettingsDialog } from "@/components/settings-dialog";
import { getProviders, getSettings } from "@/lib/api";
import type { ProviderInfo, Settings } from "@/lib/types";

export default function Home() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);

  useEffect(() => {
    getSettings().then(setSettings).catch(() => setSettings(null));
    getProviders().then(setProviders).catch(() => setProviders([]));
  }, []);

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" />
          <span className="font-semibold">AWS DevOps Copilot</span>
        </div>
        <SettingsDialog onSaved={setSettings} />
      </header>
      <Chat
        providers={providers}
        settings={settings}
        onSettingsChange={setSettings}
      />
    </div>
  );
}

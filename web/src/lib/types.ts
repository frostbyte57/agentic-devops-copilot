export type ProviderInfo = {
  id: string;
  label: string;
  kind: "paid" | "local";
  needs_key: string | null;
  default_reasoning_model: string;
  default_fast_model: string;
};

export type Settings = {
  provider: string;
  reasoning_model: string;
  fast_model: string;
  region: string | null;
  local_base_url: string | null;
  allow_code_exec: boolean;
  has_anthropic_key: boolean;
  has_openai_key: boolean;
  has_github_token: boolean;
};

// What we POST back — keys are write-only (blank = keep existing).
export type SettingsUpdate = Omit<
  Settings,
  "has_anthropic_key" | "has_openai_key" | "has_github_token"
> & {
  anthropic_key?: string | null;
  openai_key?: string | null;
  github_token?: string | null;
};

export type StepEvidence = {
  source: string;
  summary: string;
  severity: "info" | "warning" | "critical";
};

export type Step = {
  node: string;
  label: string;
  evidence: StepEvidence[];
};

export type Report = {
  root_cause: string;
  evidence_refs: string[];
  recommended_fix: string;
  confidence: number;
  commands_to_run: string[];
};

export type ProviderInfo = {
  id: string;
  label: string;
  kind: "paid" | "local";
  needs_key: string | null;
  default_model: string;
};

export type Settings = {
  provider: string;
  model: string;
  region: string | null;
  local_base_url: string | null;
  github_repo: string | null;
  allow_code_exec: boolean;
  has_anthropic_key: boolean;
  has_openai_key: boolean;
  has_github_token: boolean;
  has_aws_credentials: boolean;
};

// What we POST back — keys are write-only (blank = keep existing).
export type SettingsUpdate = Omit<
  Settings,
  | "has_anthropic_key"
  | "has_openai_key"
  | "has_github_token"
  | "has_aws_credentials"
> & {
  anthropic_key?: string | null;
  openai_key?: string | null;
  github_token?: string | null;
  aws_access_key_id?: string | null;
  aws_secret_access_key?: string | null;
};

export type ModelOption = {
  id: string;
  label: string;
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

export type Organization = {
  id: string;
  name: string;
  aliases: string[];
  domains: string[];
  reference_ids: string[];
  importance: string;
};
export type Source = {
  id: string;
  name: string;
  kind: string;
  access_context: string;
  health: string;
  last_checked: string | null;
  revision: number;
  archived_at: string | null;
  config: {
    url?: string;
    path?: string;
    filename?: string;
    allowed_hosts?: string[];
    path_prefixes?: string[];
    max_depth?: number;
    max_documents?: number;
    history_commits?: number;
  };
};
export type SourceEvent = {
  id: string;
  action: string;
  revision: number;
  user_id: string | null;
  created_at: string;
  snapshot: Pick<
    Source,
    "name" | "kind" | "config" | "access_context" | "revision" | "archived_at"
  >;
};
export type Job = {
  id: string;
  source_id: string;
  status: string;
  phase: string;
  processed: number;
  total: number;
  warnings: string[];
  errors: string[];
  created_at: string;
  source_snapshot: Partial<Source>;
};
export type Attribution = {
  organization_id: string;
  name: string;
  score: number;
  assessment: string;
  evidence_ids: string[];
  signals: { kind: string; value: string; weight: number }[];
};
export type Incident = {
  id: string;
  document_id: string;
  title: string;
  category: string;
  priority: string;
  status: string;
  summary: string;
  created_at: string;
  attribution: Attribution[];
  policy: {
    version: string;
    score: number;
    priority: string;
    note: string;
    inputs: Record<string, unknown>;
  };
  related: {
    document_id: string;
    name: string;
    method: string;
    score: number | null;
    caution: string;
    incident_id?: string;
  }[];
};
export type Evidence = {
  id: string;
  kind: string;
  excerpt: string;
  location: { line: number };
  details: Record<string, string>;
};
export type Occurrence = {
  id: string;
  source_id: string;
  source_name: string;
  access_context: string;
  locator: string;
  revision: string;
  state: string;
  first_observed: string;
  last_observed: string;
};
export type Investigation = {
  id: string;
  mode: string;
  status: string;
  error?: string;
  model: string | null;
  usage: Record<string, number | null>;
  result: {
    summary?: string;
    assessment?: string;
    uncertainty?: string[];
    missing_information?: string[];
    suggested_next_steps?: string[];
    supporting_evidence_ids?: string[];
    claim_support?: string;
  };
  tool_calls?: {
    id: string;
    name: string;
    arguments: Record<string, unknown>;
    duration_ms: number;
    success: boolean;
    result: unknown;
  }[];
};
export type Detail = Incident & {
  document: {
    name: string;
    redacted_text: string;
    metadata_json: { coverage_warnings: string[]; synthetic: boolean };
  };
  findings: {
    id: string;
    finding_type: string;
    detector: string;
    detector_version: string;
    evidence_id: string;
    placeholder: boolean;
  }[];
  evidence: Evidence[];
  occurrences: Occurrence[];
  reviews: {
    id: string;
    action: string;
    reason: string;
    created_at: string;
    priority: string | null;
  }[];
  investigations: Investigation[];
};
export type Settings = {
  mode: string;
  live_available: boolean;
  model: string | null;
  read_only: boolean;
  detectors: {
    custom: string;
    presidio: string | null;
    gitleaks: boolean;
    pii_entities: string[];
  };
  limits: Record<string, number>;
};
export type Page<T> = {
  items: T[];
  total: number;
  offset: number;
  limit: number;
};

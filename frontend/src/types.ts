export type Organization = {
  id: string;
  name: string;
  aliases: string[];
  domains: string[];
  reference_ids: string[];
  importance: string;
};

export type WorkspaceMember = { id: string; email: string };
export type RemediationTask = {
  id: string;
  incident_id: string;
  incident_title: string;
  analysis_revision: number;
  current_analysis_revision: number;
  analysis_restricted: boolean;
  title: string;
  owner_id: string | null;
  owner_email: string | null;
  due_date: string | null;
  status: "open" | "in_progress" | "blocked" | "completed" | "cancelled";
  action_taken: string;
  evidence_ids: string[];
  verification_method:
    | "credential_rotation"
    | "source_removal"
    | "other"
    | null;
  verification_notes: string;
  verified_by: string | null;
  verified_at: string | null;
  revision: number;
  created_at: string;
  updated_at: string;
  overdue: boolean;
};
export type RemediationEvent = {
  id: string;
  created_at: string;
  actor_email: string | null;
  revision: number;
  reason: string;
  snapshot: Partial<RemediationTask>;
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
  analysis_request: { reason?: string; document_id?: string };
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
  source_archived: boolean;
  reanalysis_available: boolean;
  access_context: string;
  locator: string;
  revision: string;
  state: string;
  first_observed: string;
  last_observed: string;
};
export type Investigation = {
  restricted: boolean;
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
export type Analysis = {
  id: string;
  revision: number;
  current: boolean;
  created_at: string;
  reason: string;
  restricted: boolean;
  freshness: string;
  freshness_reasons: string[];
  finding_count: number | null;
};
export type Detail = Incident & {
  analysis_revision: number;
  current_analysis_revision: number;
  analysis: Analysis;
  analyses: Analysis[];
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

export type AnalysisComparison = {
  document_id: string;
  from_analysis: Analysis;
  to_analysis: Analysis;
  changed_inputs: string[];
  category: { before: string; after: string };
  policy_priority: { before: string; after: string };
  organizations: Record<
    "before" | "after",
    { id: string; name: string; assessment: string }[]
  >;
  findings: {
    added_count: number;
    removed_count: number;
    unchanged_count: number;
    added: ChangedFinding[];
    removed: ChangedFinding[];
    complete: boolean;
  };
  text: { changed: boolean; lines: string[]; complete: boolean };
  note: string;
};
export type ChangedFinding = {
  id: string;
  evidence_id: string;
  finding_type: string;
  detector: string;
  line: number | null;
  analysis_revision: number;
};

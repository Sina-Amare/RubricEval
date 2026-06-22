export type CriterionType = "gate" | "scored";
export type GatePolicy = "must_pass" | "force_reject";
export type Verdict = "pass" | "fail" | "partial" | "error";
export type Decision = "accept" | "review" | "reject";
export type ReviewStatus = "queued" | "running" | "completed" | "failed";
export type EvidenceVerified =
  | "verified"
  | "unverified_path"
  | "unverified_lines"
  | "unverified_quote";

export interface CriterionIn {
  key: string;
  title: string;
  instructions: string;
  type: CriterionType;
  weight: number;
  gate_policy: GatePolicy | null;
  pass_threshold: number | null;
}

export interface DecisionConfig {
  accept_at: number;
  review_at: number;
}

export interface RubricDraft {
  criteria: CriterionIn[];
  decision_config: DecisionConfig;
  prompt_template_version: string;
}

export interface Task {
  id: string;
  name: string;
  description: string;
  current_rubric_version_id: string | null;
  current_version_number: number | null;
  draft: RubricDraft;
  created_at: string;
  updated_at: string;
}

export interface SubmissionFile {
  path: string;
  language: string | null;
  line_count: number;
  size_bytes: number;
}

export interface Submission {
  id: string;
  source_type: "github" | "zip";
  source_ref: string;
  commit_sha: string | null;
  branch: string | null;
  file_count: number;
  total_bytes: number;
  fileset_hash: string;
  created_at: string;
  files: SubmissionFile[];
}

export interface Evidence {
  path: string;
  start_line: number;
  end_line: number;
  quote: string;
  verified: EvidenceVerified;
}

export interface CriterionResult {
  criterion_id: string;
  criterion_key: string;
  verdict: Verdict;
  score: number | null;
  confidence: number;
  rationale: string;
  latency_ms: number;
  repaired: boolean;
  evidence: Evidence[];
}

export interface Review {
  id: string;
  task_id: string;
  rubric_version_id: string;
  submission_id: string;
  status: ReviewStatus;
  decision: Decision | null;
  final_score: number | null;
  gate_failed: boolean;
  decision_breakdown: any | null;
  model_id: string;
  prompt_template_version: string;
  rubric_content_hash: string;
  engine_version: string;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  results: CriterionResult[];
}

export interface ReviewSummary {
  id: string;
  task_id: string;
  submission_id: string;
  status: ReviewStatus;
  decision: Decision | null;
  final_score: number | null;
  created_at: string;
  completed_at: string | null;
}

export interface StreamEvent {
  id: number;
  seq?: number;
  type: string;
  payload: any;
}

export interface Health {
  ready: boolean;
  default_model: string;
  llm_backend: string;
  engine_version: string;
}

export interface ProviderConfig {
  id: string;
  name: string;
  provider: string;
  model_id: string;
  key_fingerprint: string;
  is_default: boolean;
  created_at: string;
}

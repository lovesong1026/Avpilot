export type ResearchStatus =
  | "pending"
  | "retrying"
  | "planning"
  | "researching"
  | "verifying"
  | "writing"
  | "completed"
  | "failed";

export type ResearchTask = {
  id: string;
  title: string;
  question: string;
  status: ResearchStatus;
  stage: string;
  progress: number;
  allow_web: boolean;
  use_memory: boolean;
  knowledge_base_ids: string[];
  plan: { objective?: string; questions?: string[]; deliverables?: string[] } | null;
  verifier_result: {
    sufficient?: boolean;
    coverage?: number;
    gaps?: string[];
    conflicts?: string[];
    follow_up_queries?: string[];
  } | null;
  report_markdown: string | null;
  iteration_count: number;
  max_iterations: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  started_at: string | null;
  finished_at: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type ResearchStep = {
  id: string;
  position: number;
  question: string;
  status: string;
  finding: string | null;
  evidence_count: number;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
};

export type ResearchEvidence = {
  id: string;
  step_id: string | null;
  source_type: string;
  source_id: string;
  chunk_id: string | null;
  title: string;
  quote: string;
  url: string | null;
  locator: Record<string, unknown> | null;
  score: number | null;
  query: string;
};

export type ResearchTaskDetail = ResearchTask & {
  steps: ResearchStep[];
  evidence: ResearchEvidence[];
};

export type ResearchCreate = {
  question: string;
  title?: string;
  knowledge_base_ids: string[];
  use_memory: boolean;
  allow_web: boolean;
  max_iterations: number;
};

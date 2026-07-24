export type GlobalSearchHit = {
  target_type: "document" | "image" | "memory";
  target_id: string;
  title: string;
  excerpt: string;
  score: number;
  tags: string[];
  metadata: Record<string, string | number | null>;
};

export type SearchResponse = {
  query: string;
  documents: GlobalSearchHit[];
  images: GlobalSearchHit[];
  memories: GlobalSearchHit[];
};

export type Favorite = {
  id: string;
  target_type: string;
  target_id: string;
  snapshot: Record<string, unknown> | null;
  created_at: string;
};

export type ManagedTag = {
  id: string;
  name: string;
  color: string;
  source: string;
  document_count: number;
  image_count: number;
};

export type DailyReview = {
  id: string;
  review_date: string;
  content: string;
  stats: Record<string, number>;
  created_at: string;
  updated_at: string;
};

export type DashboardData = {
  counts: Record<string, number>;
  tag_distribution: Array<{ name: string; value: number }>;
  memory_trend: Array<{ date: string; value: number }>;
  community_distribution: Array<{ name: string; value: number }>;
  observability: ObservabilitySummary;
};

export type ObservabilitySummary = {
  period_days: number;
  traces: number;
  failed_traces: number;
  success_rate: number;
  avg_duration_ms: number;
  tool_calls: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  token_trend: Array<{ date: string; input_tokens: number; output_tokens: number }>;
  tool_distribution: Array<{ name: string; value: number }>;
};

export type AgentTrace = {
  id: string;
  conversation_id: string;
  user_message_id: string;
  assistant_message_id: string | null;
  status: "running" | "completed" | "failed";
  mode: string | null;
  question: string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  tool_call_count: number;
  citation_count: number;
  error_message: string | null;
};

export type AgentSpan = {
  id: string;
  parent_span_id: string | null;
  kind: string;
  name: string;
  status: string;
  started_at: string;
  finished_at: string;
  duration_ms: number;
  input_summary: Record<string, unknown> | null;
  output_summary: Record<string, unknown> | null;
  error_message: string | null;
};

export type ModelUsage = {
  id: string;
  operation: string;
  provider: string;
  model: string;
  status: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  duration_ms: number | null;
  error_message: string | null;
};

export type RetrievalSnapshot = {
  id: string;
  tool_call_id: string;
  tool_name: string;
  query: string;
  hit_count: number;
  duration_ms: number;
  status: string;
  citations: Array<Record<string, unknown>> | null;
  result_metadata: Record<string, unknown> | null;
  top_score: number | null;
};

export type AgentTraceDetail = AgentTrace & {
  spans: AgentSpan[];
  model_usages: ModelUsage[];
  retrieval_snapshots: RetrievalSnapshot[];
};

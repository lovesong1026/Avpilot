export type MemorySource = {
  id: string;
  raw_text: string;
  source_type: "manual" | "conversation";
  source_message_id: string | null;
  status: "pending" | "extracting" | "retrying" | "completed" | "failed";
  graph_source_id: string | null;
  graph_stats: Record<string, number> | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type MemoryNode = {
  id: string;
  kind: "source" | "fragment" | "statement" | "entity";
  label: string;
  properties: Record<string, string | number | null>;
};

export type MemoryEdge = {
  id: string;
  source: string;
  target: string;
  kind: string;
  label: string;
};

export type MemoryGraph = {
  nodes: MemoryNode[];
  edges: MemoryEdge[];
  stats: Record<string, number>;
};

export type TimelineItem = {
  id: string;
  statement: string;
  event_time: string | null;
  subject: string;
  predicate: string;
  object: string;
  source_id: string;
  created_at: string | null;
};

export type MemoryCommunity = {
  id: string;
  name: string;
  member_count: number;
  members: Array<{ id: string; name: string }>;
};

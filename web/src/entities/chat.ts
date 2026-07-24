export type Conversation = {
  id: string;
  title: string;
  knowledge_base_ids: string[];
  created_at: string;
  updated_at: string;
};

export type ChatCitation = {
  id?: string;
  index?: number;
  source_type: string;
  source_id: string;
  chunk_id: string | null;
  title: string;
  file_name?: string | null;
  page?: number | null;
  locator?: {
    file_name?: string | null;
    page?: number | null;
    start_char?: number | null;
    end_char?: number | null;
    url?: string | null;
  } | null;
  quote: string;
  score: number | null;
  url?: string | null;
};

export type ChatAttachment = {
  type: "image";
  image_id: string;
  file_name: string;
  content_url: string;
};

export type ToolCallRecord = {
  tool_call_id?: string;
  name: string;
  arguments?: Record<string, unknown>;
  status: "running" | "completed" | "failed";
  duration_ms?: number;
  hit_count?: number;
  error?: string | null;
  metadata?: Record<string, unknown>;
};

export type ChatMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  attachments: ChatAttachment[] | null;
  tool_calls: ToolCallRecord[] | null;
  usage: Record<string, unknown> | null;
  citations: ChatCitation[];
  created_at: string;
  streaming?: boolean;
};

export type ChatPhase = "idle" | "planning" | "retrieving" | "generating" | "error";

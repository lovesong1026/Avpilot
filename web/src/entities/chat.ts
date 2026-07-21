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
  } | null;
  quote: string;
  score: number | null;
};

export type ChatMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  usage: Record<string, unknown> | null;
  citations: ChatCitation[];
  created_at: string;
  streaming?: boolean;
};

export type ChatPhase = "idle" | "retrieving" | "generating" | "error";

export type KnowledgeBase = {
  id: string;
  name: string;
  description: string | null;
  is_default: boolean;
  chat_enabled: boolean;
  document_count: number;
  created_at: string;
  updated_at: string;
};

export type IngestionJob = {
  id: string;
  status: "pending" | "processing" | "completed" | "failed";
  stage: string;
  progress: number;
  error_code: string | null;
  error_message: string | null;
  updated_at: string;
};

export type KnowledgeDocument = {
  id: string;
  knowledge_base_id: string;
  title: string;
  source_type: string;
  file_name: string | null;
  mime_type: string;
  file_size: number;
  status: "pending" | "processing" | "ready" | "failed";
  chunk_count: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  ingestion_job: IngestionJob | null;
};

export type SearchHit = {
  chunk_id: string;
  content: string;
  excerpt: string;
  score: number;
  citation: {
    document_id: string;
    document_title: string;
    file_name: string | null;
    page: number | null;
    start_char: number | null;
    end_char: number | null;
  };
};

import type { IngestionJob, TagSummary } from "./knowledge";

export type ImageStatus = "pending" | "processing" | "ready" | "failed";

export type ImageAsset = {
  id: string;
  knowledge_base_id: string;
  file_name: string;
  mime_type: string;
  file_size: number;
  description: string | null;
  ocr_text: string | null;
  objects: string[] | null;
  scene: string | null;
  status: ImageStatus;
  error_message: string | null;
  content_url: string;
  ingestion_job: IngestionJob | null;
  tags: TagSummary[];
  created_at: string;
  updated_at: string;
};

export type ImageSearchHit = {
  chunk_id: string;
  image_id: string;
  file_name: string;
  content: string;
  score: number;
};

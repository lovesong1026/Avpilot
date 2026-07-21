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
};


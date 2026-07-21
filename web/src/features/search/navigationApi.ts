import type {
  DailyReview,
  DashboardData,
  Favorite,
  GlobalSearchHit,
  ManagedTag,
  SearchResponse,
} from "../../entities/navigation";
import { apiClient } from "../../shared/apiClient";

export const navigationApi = {
  async search(query: string): Promise<SearchResponse> {
    const response = await apiClient.post<SearchResponse>(
      "/search",
      { query, top_k: 8, min_score: 0.25 },
      { timeout: 90_000 },
    );
    return response.data;
  },

  async favorites(): Promise<Favorite[]> {
    return (await apiClient.get<Favorite[]>("/favorites")).data;
  },

  async addFavorite(hit: GlobalSearchHit): Promise<Favorite> {
    return (
      await apiClient.post<Favorite>("/favorites", {
        target_type: hit.target_type,
        target_id: hit.target_id,
        snapshot: {
          title: hit.title,
          excerpt: hit.excerpt,
          score: hit.score,
          metadata: hit.metadata,
        },
      })
    ).data;
  },

  async removeFavorite(id: string): Promise<void> {
    await apiClient.delete(`/favorites/${id}`);
  },

  async tags(): Promise<ManagedTag[]> {
    return (await apiClient.get<ManagedTag[]>("/tags")).data;
  },

  async createTag(name: string, color?: string): Promise<ManagedTag> {
    return (await apiClient.post<ManagedTag>("/tags", { name, color })).data;
  },

  async updateTag(id: string, name: string, color: string): Promise<ManagedTag> {
    return (await apiClient.patch<ManagedTag>(`/tags/${id}`, { name, color })).data;
  },

  async removeTag(id: string): Promise<void> {
    await apiClient.delete(`/tags/${id}`);
  },

  async dailyReview(refresh = false): Promise<DailyReview> {
    return (await apiClient.get<DailyReview>("/daily-review", { params: { refresh }, timeout: 90_000 })).data;
  },

  async dashboard(): Promise<DashboardData> {
    return (await apiClient.get<DashboardData>("/dashboard")).data;
  },
};


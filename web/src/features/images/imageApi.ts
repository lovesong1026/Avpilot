import type { ImageAsset, ImageSearchHit } from "../../entities/images";
import { apiClient } from "../../shared/apiClient";

export const imageApi = {
  async list(knowledgeBaseId?: string): Promise<ImageAsset[]> {
    const response = await apiClient.get<ImageAsset[]>("/images", {
      params: knowledgeBaseId ? { knowledge_base_id: knowledgeBaseId } : undefined,
    });
    return response.data;
  },

  async upload(knowledgeBaseId: string, file: File): Promise<ImageAsset> {
    const form = new FormData();
    form.append("knowledge_base_id", knowledgeBaseId);
    form.append("file", file);
    const response = await apiClient.post<ImageAsset>("/images", form, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 60_000,
    });
    return response.data;
  },

  async search(query: string, knowledgeBaseIds: string[]): Promise<ImageSearchHit[]> {
    const response = await apiClient.post<{ hits: ImageSearchHit[] }>(
      "/images/search",
      { query, knowledge_base_ids: knowledgeBaseIds, top_k: 18 },
      { timeout: 90_000 },
    );
    return response.data.hits;
  },

  async content(imageId: string): Promise<Blob> {
    const response = await apiClient.get<Blob>(`/images/${imageId}/content`, {
      responseType: "blob",
    });
    return response.data;
  },

  async remove(imageId: string): Promise<void> {
    await apiClient.delete(`/images/${imageId}`);
  },

  async retry(imageId: string): Promise<ImageAsset> {
    const response = await apiClient.post<ImageAsset>(`/images/${imageId}/retry`);
    return response.data;
  },
};

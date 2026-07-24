import type { KnowledgeBase, KnowledgeDocument, SearchHit } from "../../entities/knowledge";
import { apiClient } from "../../shared/apiClient";

export const knowledgeApi = {
  async listBases(): Promise<KnowledgeBase[]> {
    const response = await apiClient.get<KnowledgeBase[]>("/knowledge-bases");
    return response.data;
  },

  async createBase(input: { name: string; description?: string }): Promise<KnowledgeBase> {
    const response = await apiClient.post<KnowledgeBase>("/knowledge-bases", input);
    return response.data;
  },

  async deleteBase(id: string): Promise<void> {
    await apiClient.delete(`/knowledge-bases/${id}`);
  },

  async listDocuments(knowledgeBaseId: string): Promise<KnowledgeDocument[]> {
    const response = await apiClient.get<KnowledgeDocument[]>(
      `/knowledge-bases/${knowledgeBaseId}/documents`,
    );
    return response.data;
  },

  async uploadDocument(knowledgeBaseId: string, file: File): Promise<KnowledgeDocument> {
    const form = new FormData();
    form.append("file", file);
    const response = await apiClient.post<KnowledgeDocument>(
      `/knowledge-bases/${knowledgeBaseId}/documents`,
      form,
      { headers: { "Content-Type": "multipart/form-data" }, timeout: 60_000 },
    );
    return response.data;
  },

  async addWebPage(knowledgeBaseId: string, url: string): Promise<KnowledgeDocument> {
    const response = await apiClient.post<KnowledgeDocument>(
      `/knowledge-bases/${knowledgeBaseId}/web-pages`,
      { url },
    );
    return response.data;
  },

  async deleteDocument(documentId: string): Promise<void> {
    await apiClient.delete(`/knowledge-bases/documents/${documentId}`);
  },

  async retryDocument(documentId: string): Promise<KnowledgeDocument> {
    const response = await apiClient.post<KnowledgeDocument>(
      `/knowledge-bases/documents/${documentId}/retry`,
    );
    return response.data;
  },

  async search(
    knowledgeBaseId: string,
    query: string,
    useRerank: boolean,
  ): Promise<SearchHit[]> {
    const response = await apiClient.post<{ hits: SearchHit[] }>(
      `/knowledge-bases/${knowledgeBaseId}/search`,
      { query, top_k: 6, use_rerank: useRerank },
      { timeout: 90_000 },
    );
    return response.data.hits;
  },
};

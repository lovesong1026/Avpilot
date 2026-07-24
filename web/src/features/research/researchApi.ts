import type {
  ResearchCreate,
  ResearchTask,
  ResearchTaskDetail,
} from "../../entities/research";
import { apiClient } from "../../shared/apiClient";

export const researchApi = {
  async list(): Promise<ResearchTask[]> {
    const response = await apiClient.get<ResearchTask[]>("/research");
    return response.data;
  },

  async get(id: string): Promise<ResearchTaskDetail> {
    const response = await apiClient.get<ResearchTaskDetail>(`/research/${id}`);
    return response.data;
  },

  async create(input: ResearchCreate): Promise<ResearchTask> {
    const response = await apiClient.post<ResearchTask>("/research", input);
    return response.data;
  },

  async retry(id: string): Promise<ResearchTask> {
    const response = await apiClient.post<ResearchTask>(`/research/${id}/retry`);
    return response.data;
  },

  async remove(id: string): Promise<void> {
    await apiClient.delete(`/research/${id}`);
  },

  async exportMarkdown(task: ResearchTask): Promise<void> {
    const response = await apiClient.get<Blob>(`/research/${task.id}/export`, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(response.data);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${safeName(task.title)}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  },
};

function safeName(value: string) {
  return value.replace(/[\\/:*?"<>|]/g, "_").slice(0, 80) || "研究报告";
}

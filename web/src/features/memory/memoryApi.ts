import type {
  MemoryCommunity,
  MemoryGraph,
  MemorySource,
  TimelineItem,
} from "../../entities/memory";
import { apiClient } from "../../shared/apiClient";

export const memoryApi = {
  async remember(text: string): Promise<MemorySource> {
    const response = await apiClient.post<MemorySource>("/memories", { text });
    return response.data;
  },

  async list(): Promise<MemorySource[]> {
    const response = await apiClient.get<MemorySource[]>("/memories");
    return response.data;
  },

  async graph(): Promise<MemoryGraph> {
    const response = await apiClient.get<MemoryGraph>("/memories/graph");
    return response.data;
  },

  async timeline(): Promise<TimelineItem[]> {
    const response = await apiClient.get<TimelineItem[]>("/memories/timeline");
    return response.data;
  },

  async communities(): Promise<MemoryCommunity[]> {
    const response = await apiClient.get<MemoryCommunity[]>("/memories/communities");
    return response.data;
  },

  async remove(sourceId: string): Promise<void> {
    await apiClient.delete(`/memories/${sourceId}`);
  },
};


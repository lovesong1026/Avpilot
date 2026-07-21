import type { ChatCitation, ChatMessage, Conversation } from "../../entities/chat";
import { apiClient } from "../../shared/apiClient";
import { tokenStorage } from "../../shared/tokenStorage";

type StreamHandlers = {
  onMeta?: (payload: { conversation_id: string; title: string; user_message_id: string }) => void;
  onRetrievalStarted?: () => void;
  onRetrievalCompleted?: (payload: { hit_count: number }) => void;
  onCitation?: (citations: ChatCitation[]) => void;
  onToken?: (text: string) => void;
  onCompleted?: (payload: { conversation_id: string; message_id: string }) => void;
  onError?: (message: string) => void;
};

export const chatApi = {
  async listConversations(): Promise<Conversation[]> {
    const response = await apiClient.get<Conversation[]>("/conversations");
    return response.data;
  },

  async createConversation(input: {
    title?: string;
    knowledge_base_ids: string[];
  }): Promise<Conversation> {
    const response = await apiClient.post<Conversation>("/conversations", input);
    return response.data;
  },

  async updateConversation(
    id: string,
    input: { title?: string; knowledge_base_ids?: string[] },
  ): Promise<Conversation> {
    const response = await apiClient.patch<Conversation>(`/conversations/${id}`, input);
    return response.data;
  },

  async deleteConversation(id: string): Promise<void> {
    await apiClient.delete(`/conversations/${id}`);
  },

  async listMessages(id: string): Promise<ChatMessage[]> {
    const response = await apiClient.get<ChatMessage[]>(`/conversations/${id}/messages`);
    return response.data;
  },

  async streamMessage(
    input: { conversation_id?: string; message: string; knowledge_base_ids: string[] },
    handlers: StreamHandlers,
    signal?: AbortSignal,
  ): Promise<void> {
    const token = tokenStorage.getAccessToken();
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(input),
      signal,
    });
    if (!response.ok || !response.body) {
      let message = `请求失败（HTTP ${response.status}）`;
      try {
        const body = (await response.json()) as { detail?: string };
        message = body.detail || message;
      } catch {
        // Keep the HTTP fallback when the response is not JSON.
      }
      throw new Error(message);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";
      blocks.forEach((block) => dispatchBlock(block, handlers));
    }
    if (buffer.trim()) dispatchBlock(buffer, handlers);
  },
};

function dispatchBlock(block: string, handlers: StreamHandlers) {
  let event = "message";
  const data: string[] = [];
  block.split("\n").forEach((line) => {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) data.push(line.slice(5).trim());
  });
  if (!data.length) return;
  const payload = JSON.parse(data.join("\n")) as Record<string, unknown>;
  switch (event) {
    case "meta": handlers.onMeta?.(payload as never); break;
    case "retrieval_started": handlers.onRetrievalStarted?.(); break;
    case "retrieval_completed": handlers.onRetrievalCompleted?.(payload as never); break;
    case "citation": handlers.onCitation?.((payload.citations as ChatCitation[]) || []); break;
    case "token": handlers.onToken?.(String(payload.text || "")); break;
    case "completed": handlers.onCompleted?.(payload as never); break;
    case "error": handlers.onError?.(String(payload.message || "问答失败")); break;
  }
}

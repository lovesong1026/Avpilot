import {
  BookOutlined,
  CommentOutlined,
  DeleteOutlined,
  PlusOutlined,
  RocketOutlined,
  SendOutlined,
} from "@ant-design/icons";
import {
  App,
  Avatar,
  Button,
  Drawer,
  Empty,
  Input,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { ChatCitation, ChatMessage, ChatPhase, Conversation } from "../../entities/chat";
import type { KnowledgeBase } from "../../entities/knowledge";
import { apiErrorMessage } from "../../shared/apiClient";
import { knowledgeApi } from "../knowledge/knowledgeApi";
import { chatApi } from "./chatApi";

const { Title, Text, Paragraph } = Typography;

const phaseCopy: Record<ChatPhase, string> = {
  idle: "",
  retrieving: "正在沿知识轨道检索资料…",
  generating: "已找到资料，正在组织带引用的回答…",
  error: "本轮回答未完成",
};

export function ChatPage() {
  const { message, modal } = App.useApp();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [activeId, setActiveId] = useState<string>();
  const [selectedBaseIds, setSelectedBaseIds] = useState<string[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [phase, setPhase] = useState<ChatPhase>("idle");
  const [activeCitation, setActiveCitation] = useState<ChatCitation>();
  const abortRef = useRef<AbortController | undefined>(undefined);
  const messageEndRef = useRef<HTMLDivElement>(null);

  const defaultBaseIds = useMemo(
    () => knowledgeBases.filter((item) => item.chat_enabled).map((item) => item.id),
    [knowledgeBases],
  );

  const loadConversations = useCallback(async () => {
    const items = await chatApi.listConversations();
    setConversations(items);
    return items;
  }, []);

  const openConversation = useCallback(async (conversation: Conversation) => {
    setActiveId(conversation.id);
    setSelectedBaseIds(conversation.knowledge_base_ids);
    setMessages(await chatApi.listMessages(conversation.id));
    setPhase("idle");
  }, []);

  useEffect(() => {
    void Promise.all([chatApi.listConversations(), knowledgeApi.listBases()])
      .then(([conversationItems, baseItems]) => {
        setConversations(conversationItems);
        setKnowledgeBases(baseItems);
        const first = conversationItems[0];
        if (first) void openConversation(first);
        else setSelectedBaseIds(baseItems.filter((item) => item.chat_enabled).map((item) => item.id));
      })
      .catch((error) => message.error(apiErrorMessage(error, "智能问答加载失败")))
      .finally(() => setLoading(false));
    return () => abortRef.current?.abort();
  }, [message, openConversation]);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, phase]);

  const startNewConversation = () => {
    abortRef.current?.abort();
    setActiveId(undefined);
    setMessages([]);
    setSelectedBaseIds(defaultBaseIds);
    setInput("");
    setPhase("idle");
  };

  const removeConversation = (conversation: Conversation) => {
    modal.confirm({
      title: `删除“${conversation.title}”？`,
      content: "该对话的消息和引用快照将一并删除。",
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        await chatApi.deleteConversation(conversation.id);
        const next = await loadConversations();
        if (activeId === conversation.id) {
          if (next[0]) await openConversation(next[0]);
          else startNewConversation();
        }
      },
    });
  };

  const updateAssistant = (id: string, updater: (item: ChatMessage) => ChatMessage) => {
    setMessages((items) => items.map((item) => (item.id === id ? updater(item) : item)));
  };

  const sendMessage = async () => {
    const question = input.trim();
    if (!question || sending) return;
    if (!selectedBaseIds.length) {
      message.warning("请至少选择一个知识库");
      return;
    }
    const assistantId = `stream-${Date.now()}`;
    const temporaryConversationId = activeId || "pending";
    const now = new Date().toISOString();
    setMessages((items) => [
      ...items,
      { id: `user-${Date.now()}`, conversation_id: temporaryConversationId, role: "user", content: question, usage: null, citations: [], created_at: now },
      { id: assistantId, conversation_id: temporaryConversationId, role: "assistant", content: "", usage: null, citations: [], created_at: now, streaming: true },
    ]);
    setInput("");
    setSending(true);
    setPhase("retrieving");
    const controller = new AbortController();
    abortRef.current = controller;
    let streamError = "";
    let streamConversationId = activeId;
    try {
      await chatApi.streamMessage(
        { conversation_id: activeId, message: question, knowledge_base_ids: selectedBaseIds },
        {
          onMeta: ({ conversation_id }) => {
            streamConversationId = conversation_id;
            setActiveId(conversation_id);
          },
          onRetrievalStarted: () => setPhase("retrieving"),
          onRetrievalCompleted: () => setPhase("generating"),
          onCitation: (citations) => updateAssistant(assistantId, (item) => ({ ...item, citations })),
          onToken: (text) => updateAssistant(assistantId, (item) => ({ ...item, content: item.content + text })),
          onCompleted: ({ message_id }) => updateAssistant(assistantId, (item) => ({ ...item, id: message_id, streaming: false })),
          onError: (errorMessage) => { streamError = errorMessage; setPhase("error"); },
        },
        controller.signal,
      );
      if (streamError) throw new Error(streamError);
      setPhase("idle");
      const refreshed = await loadConversations();
      const current = refreshed.find((item) => item.id === streamConversationId) || refreshed[0];
      if (current) {
        setActiveId(current.id);
        setMessages(await chatApi.listMessages(current.id));
      }
    } catch (error) {
      if (controller.signal.aborted) return;
      const errorMessage = error instanceof Error ? error.message : "问答失败，请稍后重试";
      updateAssistant(assistantId, (item) => ({ ...item, content: item.content || errorMessage, streaming: false }));
      setPhase("error");
      message.error(errorMessage);
    } finally {
      setSending(false);
      abortRef.current = undefined;
    }
  };

  return (
    <div className="chat-page">
      <aside className="conversation-rail">
        <div className="conversation-brand"><CommentOutlined /><span><strong>问答航线</strong><small>对话与引用记录</small></span></div>
        <Button type="primary" block icon={<PlusOutlined />} onClick={startNewConversation}>新对话</Button>
        <div className="conversation-list">
          {conversations.map((conversation) => (
            <div className={`conversation-item ${conversation.id === activeId ? "active" : ""}`} key={conversation.id}>
              <button type="button" onClick={() => void openConversation(conversation)}><strong>{conversation.title}</strong><small>{new Date(conversation.updated_at).toLocaleDateString("zh-CN")}</small></button>
              <Button type="text" size="small" danger icon={<DeleteOutlined />} aria-label={`删除 ${conversation.title}`} onClick={() => removeConversation(conversation)} />
            </div>
          ))}
          {!loading && conversations.length === 0 && <div className="conversation-empty">还没有历史航线</div>}
        </div>
      </aside>

      <main className="chat-main">
        <header className="chat-header">
          <div><Text className="page-kicker">GROUND CONTROL</Text><Title level={2}>{activeId ? conversations.find((item) => item.id === activeId)?.title || "智能问答" : "新对话"}</Title></div>
          <Select
            mode="multiple"
            maxTagCount="responsive"
            value={selectedBaseIds}
            placeholder="选择知识库"
            options={knowledgeBases.map((item) => ({ label: item.name, value: item.id }))}
            onChange={setSelectedBaseIds}
            disabled={sending}
            suffixIcon={<BookOutlined />}
          />
        </header>

        <section className="message-space">
          {loading ? <Spin size="large" /> : messages.length === 0 ? (
            <div className="chat-welcome">
              <span className="welcome-orbit"><RocketOutlined /></span>
              <Title level={2}>从知识库发起一次探索</Title>
              <Paragraph>星航仪会先检索资料，再生成带编号引用的回答。每个结论都可以回到原始文档。</Paragraph>
              <Space wrap>
                {["总结这个知识库的核心内容", "资料中有哪些关键结论？", "帮我找出相关实验参数"].map((item) => <Button key={item} onClick={() => setInput(item)}>{item}</Button>)}
              </Space>
            </div>
          ) : messages.map((item) => (
            <article className={`chat-message ${item.role}`} key={item.id}>
              <Avatar className="message-avatar">{item.role === "user" ? "我" : "星"}</Avatar>
              <div className="message-body">
                <div className="message-role">{item.role === "user" ? "你" : "星航仪"}{item.streaming && <Tag color="processing">生成中</Tag>}</div>
                <div className="message-content">{item.content || (item.streaming ? "正在读取知识坐标…" : "")}</div>
                {item.citations.length > 0 && (
                  <div className="message-citations">
                    {item.citations.map((citation, index) => (
                      <button type="button" key={citation.id || citation.chunk_id || index} onClick={() => setActiveCitation({ ...citation, index: citation.index || index + 1 })}>
                        [{citation.index || index + 1}] {citation.title}{(citation.page ?? citation.locator?.page) ? ` · 第 ${citation.page ?? citation.locator?.page} 页` : ""}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </article>
          ))}
          {phase !== "idle" && <div className={`chat-phase ${phase}`}><span />{phaseCopy[phase]}</div>}
          <div ref={messageEndRef} />
        </section>

        <footer className="chat-composer">
          <Input.TextArea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onPressEnter={(event) => { if (!event.shiftKey) { event.preventDefault(); void sendMessage(); } }}
            placeholder="向你的知识库提问，Shift + Enter 换行"
            autoSize={{ minRows: 2, maxRows: 6 }}
            disabled={sending}
          />
          <Button type="primary" shape="circle" size="large" icon={<SendOutlined />} aria-label="发送问题" loading={sending} onClick={() => void sendMessage()} />
        </footer>
      </main>

      <Drawer title={`引用 [${activeCitation?.index || ""}]`} open={Boolean(activeCitation)} onClose={() => setActiveCitation(undefined)} size={460}>
        {activeCitation && <div className="citation-drawer"><Tag color="green">知识库文档</Tag><Title level={3}>{activeCitation.title}</Title><Text type="secondary">{activeCitation.file_name || activeCitation.locator?.file_name || activeCitation.title}{(activeCitation.page ?? activeCitation.locator?.page) ? ` · 第 ${activeCitation.page ?? activeCitation.locator?.page} 页` : ""}</Text><Paragraph>{activeCitation.quote}</Paragraph>{activeCitation.score != null && <Text type="secondary">检索相关度：{Math.round(activeCitation.score * 100)}%</Text>}</div>}
      </Drawer>
    </div>
  );
}

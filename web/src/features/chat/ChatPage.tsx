import {
  BookOutlined,
  CommentOutlined,
  DeleteOutlined,
  ExperimentOutlined,
  GlobalOutlined,
  LoadingOutlined,
  PaperClipOutlined,
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
  Switch,
  Tag,
  Typography,
} from "antd";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import type {
  ChatCitation,
  ChatMessage,
  ChatPhase,
  Conversation,
  ToolCallRecord,
} from "../../entities/chat";
import type { ImageAsset } from "../../entities/images";
import type { KnowledgeBase } from "../../entities/knowledge";
import { apiErrorMessage } from "../../shared/apiClient";
import { knowledgeApi } from "../knowledge/knowledgeApi";
import { AuthenticatedImage } from "../images/AuthenticatedImage";
import { imageApi } from "../images/imageApi";
import { chatApi } from "./chatApi";

const { Title, Text, Paragraph } = Typography;

const phaseCopy: Record<ChatPhase, string> = {
  idle: "",
  planning: "正在判断需要调用哪些工具…",
  retrieving: "正在沿知识轨道检索资料…",
  generating: "已找到资料，正在组织带引用的回答…",
  error: "本轮回答未完成",
};

export function ChatPage() {
  const { message, modal } = App.useApp();
  const navigate = useNavigate();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [images, setImages] = useState<ImageAsset[]>([]);
  const [activeId, setActiveId] = useState<string>();
  const [selectedBaseIds, setSelectedBaseIds] = useState<string[]>([]);
  const [selectedImageIds, setSelectedImageIds] = useState<string[]>([]);
  const [allowWeb, setAllowWeb] = useState(false);
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
    void Promise.all([chatApi.listConversations(), knowledgeApi.listBases(), imageApi.list()])
      .then(([conversationItems, baseItems, imageItems]) => {
        setConversations(conversationItems);
        setKnowledgeBases(baseItems);
        setImages(imageItems.filter((item) => item.status === "ready"));
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
    setSelectedImageIds([]);
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

  const upsertToolCall = (assistantId: string, call: ToolCallRecord) => {
    updateAssistant(assistantId, (item) => {
      const current = item.tool_calls || [];
      const key = call.tool_call_id || call.name;
      const exists = current.some((row) => (row.tool_call_id || row.name) === key);
      return {
        ...item,
        tool_calls: exists
          ? current.map((row) => ((row.tool_call_id || row.name) === key ? { ...row, ...call } : row))
          : [...current, call],
      };
    });
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
      {
        id: `user-${Date.now()}`,
        conversation_id: temporaryConversationId,
        role: "user",
        content: question,
        attachments: selectedImageIds.map((imageId) => {
          const image = images.find((item) => item.id === imageId);
          return {
            type: "image" as const,
            image_id: imageId,
            file_name: image?.file_name || "图片",
            content_url: `/api/images/${imageId}/content`,
          };
        }),
        tool_calls: null,
        usage: null,
        citations: [],
        created_at: now,
      },
      {
        id: assistantId,
        conversation_id: temporaryConversationId,
        role: "assistant",
        content: "",
        attachments: null,
        tool_calls: [],
        usage: null,
        citations: [],
        created_at: now,
        streaming: true,
      },
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
        {
          conversation_id: activeId,
          message: question,
          knowledge_base_ids: selectedBaseIds,
          image_ids: selectedImageIds,
          allow_web: allowWeb,
        },
        {
          onMeta: ({ conversation_id }) => {
            streamConversationId = conversation_id;
            setActiveId(conversation_id);
          },
          onAgentStarted: () => setPhase("planning"),
          onAgentFallback: () => message.info("当前模型已降级为 ReAct 工具编排"),
          onToolStarted: (call) => {
            setPhase("retrieving");
            upsertToolCall(assistantId, call);
          },
          onToolCompleted: (call) => upsertToolCall(assistantId, call),
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
      setSelectedImageIds([]);
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

  const startResearch = () => {
    const question =
      input.trim() ||
      [...messages].reverse().find((item) => item.role === "user")?.content.trim();
    if (!question) {
      message.warning("请先输入一个研究课题");
      return;
    }
    const params = new URLSearchParams({
      question,
      knowledge_base_ids: selectedBaseIds.join(","),
      allow_web: String(allowWeb),
    });
    navigate(`/research?${params.toString()}`);
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
          <Space className="chat-agent-controls" wrap>
            <Select
              mode="multiple"
              maxTagCount={1}
              value={selectedImageIds}
              placeholder="附加图片"
              options={images.map((item) => ({ label: item.file_name, value: item.id }))}
              onChange={(values) => setSelectedImageIds(values.slice(-3))}
              disabled={sending}
              suffixIcon={<PaperClipOutlined />}
            />
            <span className="web-toggle">
              <GlobalOutlined />
              允许联网
              <Switch checked={allowWeb} onChange={setAllowWeb} disabled={sending} />
            </span>
          </Space>
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
                {item.attachments && item.attachments.length > 0 && (
                  <div className="message-attachments">
                    {item.attachments.map((attachment) => (
                      <div key={attachment.image_id} title={attachment.file_name}>
                        <AuthenticatedImage imageId={attachment.image_id} alt={attachment.file_name} />
                      </div>
                    ))}
                  </div>
                )}
                {item.tool_calls && item.tool_calls.length > 0 && (
                  <div className="tool-trace">
                    {item.tool_calls.map((call, index) => (
                      <div className={`tool-trace-item ${call.status}`} key={call.tool_call_id || `${call.name}-${index}`}>
                        <span>{call.status === "running" ? <LoadingOutlined spin /> : call.status === "completed" ? "✓" : "!"}</span>
                        <strong>{toolLabel(call.name)}</strong>
                        {call.status === "completed" && <small>{call.hit_count ?? Number(call.metadata?.hit_count || 0)} 条结果</small>}
                        {call.status === "failed" && <small>{call.error || "调用失败"}</small>}
                      </div>
                    ))}
                  </div>
                )}
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
          <Space direction="vertical">
            <Button type="primary" shape="circle" size="large" icon={<SendOutlined />} aria-label="发送问题" loading={sending} onClick={() => void sendMessage()} />
            <Button type="text" size="small" icon={<ExperimentOutlined />} disabled={sending} onClick={startResearch}>深度研究</Button>
          </Space>
        </footer>
      </main>

      <Drawer title={`引用 [${activeCitation?.index || ""}]`} open={Boolean(activeCitation)} onClose={() => setActiveCitation(undefined)} size={460}>
        {activeCitation && <div className="citation-drawer"><Tag color="green">{sourceLabel(activeCitation.source_type)}</Tag><Title level={3}>{activeCitation.title}</Title><Text type="secondary">{activeCitation.file_name || activeCitation.locator?.file_name || activeCitation.title}{(activeCitation.page ?? activeCitation.locator?.page) ? ` · 第 ${activeCitation.page ?? activeCitation.locator?.page} 页` : ""}</Text>{activeCitation.url && <Typography.Link href={activeCitation.url} target="_blank" rel="noreferrer">{activeCitation.url}</Typography.Link>}<Paragraph>{activeCitation.quote}</Paragraph>{activeCitation.score != null && <Text type="secondary">检索相关度：{Math.round(activeCitation.score * 100)}%</Text>}</div>}
      </Drawer>
    </div>
  );
}

function toolLabel(name: string) {
  return ({
    knowledge_search: "搜索知识库",
    memory_search: "搜索长期记忆",
    web_search: "联网搜索",
  } as Record<string, string>)[name] || name;
}

function sourceLabel(type: string) {
  return ({ document: "知识库文档", memory: "长期记忆", web: "网页资料" } as Record<string, string>)[type] || type;
}

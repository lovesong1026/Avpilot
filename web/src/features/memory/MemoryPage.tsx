import {
  ApartmentOutlined,
  ClockCircleOutlined,
  DeleteOutlined,
  RadarChartOutlined,
  RedoOutlined,
  SaveOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import { App, Button, Empty, Input, Segmented, Space, Spin, Tag, Typography } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import type {
  MemoryCommunity,
  MemoryGraph,
  MemorySource,
  TimelineItem,
} from "../../entities/memory";
import { apiErrorMessage } from "../../shared/apiClient";
import { MemoryGraphCanvas } from "./MemoryGraphCanvas";
import { memoryApi } from "./memoryApi";

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

const statusMeta: Record<MemorySource["status"], { label: string; color: string }> = {
  pending: { label: "等待萃取", color: "default" },
  extracting: { label: "正在萃取", color: "processing" },
  retrying: { label: "等待重试", color: "warning" },
  completed: { label: "已进入图谱", color: "success" },
  failed: { label: "萃取失败", color: "error" },
};

const kindMeta = {
  source: { label: "来源", className: "source" },
  fragment: { label: "片段", className: "fragment" },
  statement: { label: "陈述", className: "statement" },
  entity: { label: "实体", className: "entity" },
};

export function MemoryPage() {
  const { message, modal } = App.useApp();
  const [text, setText] = useState("");
  const [sources, setSources] = useState<MemorySource[]>([]);
  const [graph, setGraph] = useState<MemoryGraph>({ nodes: [], edges: [], stats: {} });
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [communities, setCommunities] = useState<MemoryCommunity[]>([]);
  const [view, setView] = useState<string>("图谱");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    const [nextSources, nextGraph, nextTimeline, nextCommunities] = await Promise.all([
      memoryApi.list(),
      memoryApi.graph(),
      memoryApi.timeline(),
      memoryApi.communities(),
    ]);
    setSources(nextSources);
    setGraph(nextGraph);
    setTimeline(nextTimeline);
    setCommunities(nextCommunities);
  }, []);

  useEffect(() => {
    void load()
      .catch((error) => message.error(apiErrorMessage(error, "记忆轨道加载失败")))
      .finally(() => setLoading(false));
  }, [load, message]);

  useEffect(() => {
    if (!sources.some((item) => ["pending", "extracting", "retrying"].includes(item.status))) return;
    const timer = window.setInterval(() => void load(), 1800);
    return () => window.clearInterval(timer);
  }, [load, sources]);

  const recentNodes = useMemo(
    () => graph.nodes.filter((node) => node.kind !== "fragment").slice(-36).reverse(),
    [graph.nodes],
  );

  const remember = async () => {
    const value = text.trim();
    if (value.length < 2) return;
    setSaving(true);
    try {
      const source = await memoryApi.remember(value);
      setSources((items) => [source, ...items]);
      setText("");
      message.success("已送入记忆轨道，AI 正在异步萃取");
    } catch (error) {
      message.error(apiErrorMessage(error, "主动记住失败"));
    } finally {
      setSaving(false);
    }
  };

  const remove = (source: MemorySource) => {
    modal.confirm({
      title: "删除这条记忆来源？",
      content: "只属于该来源的片段、陈述和实体会同步从图谱移除。",
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        await memoryApi.remove(source.id);
        await load();
        message.success("记忆来源已删除");
      },
    });
  };

  const retry = async (source: MemorySource) => {
    try {
      await memoryApi.retry(source.id);
      await load();
      message.success("记忆已重新进入萃取队列");
    } catch (error) {
      message.error(apiErrorMessage(error, "重新萃取失败"));
    }
  };

  return (
    <div className="memory-page">
      <header className="page-heading">
        <div>
          <Text className="page-kicker">MEMORY CONSTELLATION</Text>
          <Title level={1}>记忆星图</Title>
          <Paragraph>把零散经历萃取成可追溯的画像与事件，让每一条长期记忆都有来路。</Paragraph>
        </div>
        <div className="memory-summary">
          <span><strong>{graph.stats.entity || 0}</strong> 实体</span>
          <span><strong>{graph.stats.statement || 0}</strong> 陈述</span>
          <span><strong>{communities.length}</strong> 社区</span>
        </div>
      </header>

      <section className="remember-panel">
        <div className="remember-copy">
          <SaveOutlined />
          <div><Text strong>主动记住</Text><Text type="secondary">写下稳定偏好、目标、人物关系或一件有时间的事。</Text></div>
        </div>
        <TextArea
          value={text}
          autoSize={{ minRows: 3, maxRows: 7 }}
          maxLength={20_000}
          placeholder="例如：我计划在 2026 年 10 月参加上海的人工智能大会，我更关注知识图谱方向。"
          onChange={(event) => setText(event.target.value)}
        />
        <Button type="primary" icon={<RadarChartOutlined />} loading={saving} onClick={() => void remember()}>
          送入记忆轨道
        </Button>
      </section>

      <div className="memory-layout">
        <aside className="memory-source-panel">
          <div className="section-heading"><Title level={3}>来源记录</Title><Text type="secondary">{sources.length} 条</Text></div>
          {loading && <Spin />}
          {!loading && sources.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="还没有长期记忆" />}
          <div className="memory-source-list">
            {sources.map((source) => (
              <article className="memory-source-card" key={source.id}>
                <div className="memory-source-head">
                  <Tag color={source.source_type === "manual" ? "green" : "blue"}>{source.source_type === "manual" ? "主动记住" : "对话萃取"}</Tag>
                  <Tag color={statusMeta[source.status].color}>{statusMeta[source.status].label}</Tag>
                </div>
                <Paragraph ellipsis={{ rows: 3 }}>{source.raw_text}</Paragraph>
                {source.graph_stats && <Text type="secondary">{source.graph_stats.statements || 0} 条陈述 · {source.graph_stats.entities || 0} 个实体 · 复用 {source.graph_stats.entities_reused || 0}</Text>}
                {source.error_message && <Text type="danger">{source.error_message}</Text>}
                <div className="memory-source-foot">
                  <Text type="secondary">{new Date(source.created_at).toLocaleString("zh-CN")}</Text>
                  <Space>
                    {source.status === "failed" && <Button type="text" size="small" icon={<RedoOutlined />} onClick={() => void retry(source)}>重试</Button>}
                    <Button type="text" danger size="small" icon={<DeleteOutlined />} onClick={() => remove(source)} />
                  </Space>
                </div>
              </article>
            ))}
          </div>
        </aside>

        <section className="memory-explorer">
          <div className="memory-view-head">
            <Segmented
              value={view}
              onChange={(value) => setView(String(value))}
              options={[
                { label: "图谱", value: "图谱", icon: <ApartmentOutlined /> },
                { label: "时间线", value: "时间线", icon: <ClockCircleOutlined /> },
                { label: "社区", value: "社区", icon: <TeamOutlined /> },
              ]}
            />
            <Text type="secondary">四层溯源：来源 → 片段 → 陈述 → 实体</Text>
          </div>

          {view === "图谱" && <>
            {recentNodes.length === 0 ? <Empty description="记住一条内容后，这里会形成星图" /> : <MemoryGraphCanvas data={graph} />}
            {recentNodes.length > 0 && <div className="memory-graph-legend">{Object.entries(kindMeta).map(([key, item]) => <span className={item.className} key={key}><i />{item.label}</span>)}</div>}
          </>}

          {view === "时间线" && <div className="memory-timeline">
            {timeline.length === 0 && <Empty description="带明确时间的事件会进入时间线" />}
            {timeline.map((item) => <article key={item.id}>
              <time>{item.event_time ? new Date(item.event_time).toLocaleString("zh-CN") : "时间待确认"}</time>
              <div><Text strong>{item.statement}</Text><Text type="secondary">{item.subject} · {item.predicate} · {item.object}</Text></div>
            </article>)}
          </div>}

          {view === "社区" && <div className="community-grid">
            {communities.length === 0 && <Empty description="实体关系形成后会自动聚类" />}
            {communities.map((community) => <article key={community.id}>
              <TeamOutlined />
              <Title level={4}>{community.name || "未命名社区"}</Title>
              <Text type="secondary">{community.member_count} 个关联实体</Text>
              <Space wrap>{community.members.map((member) => <Tag key={member.id}>{member.name}</Tag>)}</Space>
            </article>)}
          </div>}
        </section>
      </div>
    </div>
  );
}

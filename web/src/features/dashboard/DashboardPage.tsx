import {
  ArrowRightOutlined,
  BookOutlined,
  CloudUploadOutlined,
  NodeIndexOutlined,
  PictureOutlined,
  RadarChartOutlined,
} from "@ant-design/icons";
import { App, Button, Card, Col, Drawer, Empty, Progress, Row, Skeleton, Space, Tag, Timeline, Typography } from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuthStore } from "../auth/authStore";
import type { AgentTrace, AgentTraceDetail, DashboardData } from "../../entities/navigation";
import { apiErrorMessage } from "../../shared/apiClient";
import { navigationApi } from "../search/navigationApi";
import { DashboardCharts } from "./DashboardCharts";

const { Title, Paragraph, Text } = Typography;

export function DashboardPage() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const { message } = App.useApp();
  const [data, setData] = useState<DashboardData>();
  const [traces, setTraces] = useState<AgentTrace[]>([]);
  const [activeTrace, setActiveTrace] = useState<AgentTraceDetail>();

  useEffect(() => {
    void Promise.all([navigationApi.dashboard(), navigationApi.traces()])
      .then(([dashboard, recentTraces]) => {
        setData(dashboard);
        setTraces(recentTraces);
      })
      .catch((error) => message.error(apiErrorMessage(error, "统计仪表盘加载失败")));
  }, [message]);

  return (
    <div className="dashboard-page">
      <section className="welcome-panel">
        <div>
          <Tag color="green">系统基础能力已连接</Tag>
          <Title level={1}>早上好，{user?.display_name || user?.username}</Title>
          <Paragraph>从一份论文或实验记录开始，让零散资料成为可检索、可引用的课题组知识。</Paragraph>
          <Space wrap>
            <Button type="primary" size="large" icon={<CloudUploadOutlined />} onClick={() => navigate("/knowledge")}>
              前往知识库
            </Button>
            <Button size="large" icon={<ArrowRightOutlined />} onClick={() => navigate("/chat")}>进入问答</Button>
          </Space>
        </div>
        <div className="readiness-card">
          <Text type="secondary">产品能力建设进度</Text>
          <strong>知识与记忆闭环</strong>
          <Progress percent={88} strokeColor="#315f4d" railColor="#dce6df" />
          <small>多模态知识、可追溯问答与长期记忆已形成闭环</small>
        </div>
      </section>

      <Row gutter={[18, 18]}>
        <Col xs={24} md={12} lg={6}>
          <Card className="feature-card">
            <span className="feature-icon"><BookOutlined /></span>
            <Title level={4}>知识库</Title>
            <Paragraph>文档与公开网页统一进入父子分块和混合检索。</Paragraph>
            <Tag color="green">已可用</Tag>
          </Card>
        </Col>
        <Col xs={24} md={12} lg={6}>
          <Card className="feature-card">
            <span className="feature-icon"><ArrowRightOutlined /></span>
            <Title level={4}>可追溯问答</Title>
            <Paragraph>混合检索、流式生成与原文引用。</Paragraph>
            <Tag color="green">已可用</Tag>
          </Card>
        </Col>
        <Col xs={24} md={12} lg={6}>
          <Card className="feature-card">
            <span className="feature-icon"><PictureOutlined /></span>
            <Title level={4}>多模态图片</Title>
            <Paragraph>AI 描述、OCR、物体、场景和语义检索。</Paragraph>
            <Tag color="green">已可用</Tag>
          </Card>
        </Col>
        <Col xs={24} md={12} lg={6}>
          <Card className="feature-card">
            <span className="feature-icon"><NodeIndexOutlined /></span>
            <Title level={4}>长期记忆</Title>
            <Paragraph>画像、事件、四层溯源、去重与社区聚类。</Paragraph>
            <Tag color="green">已可用</Tag>
          </Card>
        </Col>
      </Row>

      {data ? <>
        <section className="dashboard-metrics">
          {[
            ["documents", "文档"],
            ["images", "图片"],
            ["memories", "记忆来源"],
            ["entities", "记忆实体"],
            ["favorites", "收藏"],
            ["tags", "标签"],
          ].map(([key, label]) => <article key={key}><strong>{data.counts[key] || 0}</strong><span>{label}</span></article>)}
        </section>
        <DashboardCharts data={data} />
        <section className="dashboard-metrics">
          <article><strong>{data.observability.total_tokens.toLocaleString("zh-CN")}</strong><span>近 14 天 Token</span></article>
          <article><strong>{Math.round(data.observability.success_rate * 100)}%</strong><span>Agent 成功率</span></article>
          <article><strong>{data.observability.avg_duration_ms} ms</strong><span>平均响应耗时</span></article>
          <article><strong>{data.observability.tool_calls}</strong><span>工具调用</span></article>
        </section>
        <section className="document-section">
          <div className="section-heading"><Title level={3}>最近 Agent Trace</Title><Text type="secondary">问题 → 编排 → 工具 → 检索 → 回答</Text></div>
          {traces.length === 0 && <Empty description="完成一次智能问答后，这里会出现全链路记录" />}
          <div className="document-list">
            {traces.map((trace) => (
              <button
                type="button"
                className="document-row"
                key={trace.id}
                onClick={() => void navigationApi.trace(trace.id).then(setActiveTrace).catch((error) => message.error(apiErrorMessage(error, "Trace 加载失败")))}
              >
                <span className="document-icon"><RadarChartOutlined /></span>
                <span className="document-copy">
                  <Space wrap><Text strong>{trace.question}</Text><Tag color={trace.status === "completed" ? "green" : trace.status === "failed" ? "red" : "blue"}>{trace.status}</Tag></Space>
                  <Space wrap size="large" className="document-meta"><span>{trace.mode || "等待编排"}</span><span>{trace.tool_call_count} 次工具</span><span>{trace.citation_count} 条引用</span><span>{trace.duration_ms ?? 0} ms</span></Space>
                </span>
              </button>
            ))}
          </div>
        </section>
      </> : <Skeleton active className="dashboard-skeleton" />}

      <Drawer title="Agent Trace" open={Boolean(activeTrace)} onClose={() => setActiveTrace(undefined)} size={640}>
        {activeTrace && <>
          <Title level={3}>{activeTrace.question}</Title>
          <Space wrap><Tag color={activeTrace.status === "completed" ? "green" : "red"}>{activeTrace.status}</Tag><Tag>{activeTrace.mode || "unknown"}</Tag><Text type="secondary">{activeTrace.duration_ms ?? 0} ms</Text></Space>
          <Title level={4}>执行阶段</Title>
          <Timeline items={activeTrace.spans.map((span) => ({
            color: span.status === "completed" ? "green" : "red",
            children: <div><Text strong>{span.name}</Text><br /><Text type="secondary">{span.kind} · {span.duration_ms} ms</Text>{span.error_message && <Paragraph type="danger">{span.error_message}</Paragraph>}</div>,
          }))} />
          <Title level={4}>模型 Token</Title>
          {activeTrace.model_usages.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="模型未返回 Token 统计" /> : activeTrace.model_usages.map((usage) => (
            <Card size="small" key={usage.id}><Space wrap><Tag>{usage.operation}</Tag><Text>{usage.model}</Text><Text>输入 {usage.input_tokens}</Text><Text>输出 {usage.output_tokens}</Text><Text strong>共 {usage.total_tokens}</Text></Space></Card>
          ))}
          <Title level={4}>检索快照</Title>
          {activeTrace.retrieval_snapshots.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="本次没有调用检索工具" /> : activeTrace.retrieval_snapshots.map((snapshot) => (
            <Card size="small" key={snapshot.id} title={snapshot.tool_name}><Paragraph>{snapshot.query}</Paragraph><Space><Tag color="green">{snapshot.hit_count} 条命中</Tag><Text type="secondary">{snapshot.duration_ms} ms</Text>{snapshot.top_score !== null && <Text type="secondary">最高相关度 {Math.round(snapshot.top_score * 100)}%</Text>}</Space></Card>
          ))}
        </>}
      </Drawer>
    </div>
  );
}

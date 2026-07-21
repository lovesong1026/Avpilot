import {
  ArrowRightOutlined,
  BookOutlined,
  CloudUploadOutlined,
  NodeIndexOutlined,
  PictureOutlined,
} from "@ant-design/icons";
import { App, Button, Card, Col, Progress, Row, Skeleton, Space, Tag, Typography } from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuthStore } from "../auth/authStore";
import type { DashboardData } from "../../entities/navigation";
import { apiErrorMessage } from "../../shared/apiClient";
import { navigationApi } from "../search/navigationApi";
import { DashboardCharts } from "./DashboardCharts";

const { Title, Paragraph, Text } = Typography;

export function DashboardPage() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const { message } = App.useApp();
  const [data, setData] = useState<DashboardData>();

  useEffect(() => {
    void navigationApi.dashboard()
      .then(setData)
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
      </> : <Skeleton active className="dashboard-skeleton" />}
    </div>
  );
}

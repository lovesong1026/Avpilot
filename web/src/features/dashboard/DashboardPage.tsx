import { ArrowRightOutlined, BookOutlined, CloudUploadOutlined, NodeIndexOutlined } from "@ant-design/icons";
import { Button, Card, Col, Progress, Row, Space, Tag, Typography } from "antd";
import { useNavigate } from "react-router-dom";

import { useAuthStore } from "../auth/authStore";

const { Title, Paragraph, Text } = Typography;

export function DashboardPage() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);

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
          <strong>RAG 基础层</strong>
          <Progress percent={38} strokeColor="#315f4d" railColor="#dce6df" />
          <small>认证、模型、数据库、IK 与分块已完成</small>
        </div>
      </section>

      <Row gutter={[18, 18]}>
        <Col xs={24} md={8}>
          <Card className="feature-card">
            <span className="feature-icon"><BookOutlined /></span>
            <Title level={4}>知识库</Title>
            <Paragraph>PDF、Word、Markdown、网页与图片统一入库。</Paragraph>
            <Tag>下一阶段</Tag>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card className="feature-card">
            <span className="feature-icon"><ArrowRightOutlined /></span>
            <Title level={4}>可追溯问答</Title>
            <Paragraph>混合检索、工具编排与原文引用。</Paragraph>
            <Tag>规划中</Tag>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card className="feature-card">
            <span className="feature-icon"><NodeIndexOutlined /></span>
            <Title level={4}>长期记忆</Title>
            <Paragraph>从对话中提取实体、事件和关系图谱。</Paragraph>
            <Tag>规划中</Tag>
          </Card>
        </Col>
      </Row>
    </div>
  );
}

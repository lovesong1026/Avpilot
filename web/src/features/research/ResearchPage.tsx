import {
  BookOutlined,
  CheckCircleOutlined,
  CloudDownloadOutlined,
  DeleteOutlined,
  ExperimentOutlined,
  FileSearchOutlined,
  GlobalOutlined,
  LoadingOutlined,
  PlusOutlined,
  RedoOutlined,
} from "@ant-design/icons";
import {
  App,
  Button,
  Card,
  Checkbox,
  Collapse,
  Empty,
  Form,
  Input,
  Modal,
  Progress,
  Select,
  Space,
  Spin,
  Steps,
  Tag,
  Typography,
} from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import type { KnowledgeBase } from "../../entities/knowledge";
import type {
  ResearchCreate,
  ResearchEvidence,
  ResearchStatus,
  ResearchTask,
  ResearchTaskDetail,
} from "../../entities/research";
import { apiErrorMessage } from "../../shared/apiClient";
import { knowledgeApi } from "../knowledge/knowledgeApi";
import { researchApi } from "./researchApi";

const { Title, Text, Paragraph } = Typography;
const runningStatuses: ResearchStatus[] = [
  "pending",
  "retrying",
  "planning",
  "researching",
  "verifying",
  "writing",
];

const stageLabels: Record<string, string> = {
  queued: "等待发射",
  retry_wait: "等待重试",
  recovered: "已恢复任务",
  planning: "制定研究计划",
  collecting_evidence: "检索并整理证据",
  verifying_evidence: "Verifier 审查证据",
  writing_report: "撰写研究报告",
  completed: "研究完成",
  failed: "研究失败",
};

export function ResearchPage() {
  const { message, modal } = App.useApp();
  const [searchParams, setSearchParams] = useSearchParams();
  const [form] = Form.useForm<ResearchCreate>();
  const [tasks, setTasks] = useState<ResearchTask[]>([]);
  const [active, setActive] = useState<ResearchTaskDetail>();
  const [bases, setBases] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const hasRunning = useMemo(
    () => tasks.some((item) => runningStatuses.includes(item.status)),
    [tasks],
  );

  const load = useCallback(
    async (preferredId?: string) => {
      const items = await researchApi.list();
      setTasks(items);
      const targetId = preferredId || active?.id || items[0]?.id;
      if (targetId) {
        const detail = await researchApi.get(targetId);
        setActive(detail);
      } else {
        setActive(undefined);
      }
    },
    [active?.id],
  );

  useEffect(() => {
    void Promise.all([researchApi.list(), knowledgeApi.listBases()])
      .then(async ([items, baseItems]) => {
        setTasks(items);
        setBases(baseItems);
        if (items[0]) setActive(await researchApi.get(items[0].id));
        const question = searchParams.get("question");
        if (question) {
          const selected = (searchParams.get("knowledge_base_ids") || "")
            .split(",")
            .filter(Boolean);
          form.setFieldsValue({
            question,
            knowledge_base_ids: selected,
            use_memory: true,
            allow_web: searchParams.get("allow_web") === "true",
            max_iterations: 2,
          });
          setCreateOpen(true);
          setSearchParams({}, { replace: true });
        }
      })
      .catch((error) => message.error(apiErrorMessage(error, "深度研究加载失败")))
      .finally(() => setLoading(false));
  }, [form, message, searchParams, setSearchParams]);

  useEffect(() => {
    if (!hasRunning) return;
    const timer = window.setInterval(() => {
      void load().catch((error) =>
        message.error(apiErrorMessage(error, "研究进度刷新失败")),
      );
    }, 2500);
    return () => window.clearInterval(timer);
  }, [hasRunning, load, message]);

  const openCreate = () => {
    form.setFieldsValue({
      question: "",
      knowledge_base_ids: bases.filter((item) => item.chat_enabled).map((item) => item.id),
      use_memory: true,
      allow_web: false,
      max_iterations: 2,
    });
    setCreateOpen(true);
  };

  const create = async (values: ResearchCreate) => {
    setCreating(true);
    try {
      const task = await researchApi.create(values);
      setCreateOpen(false);
      await load(task.id);
      message.success("研究任务已进入后台队列，可以离开页面等待完成");
    } catch (error) {
      message.error(apiErrorMessage(error, "研究任务创建失败"));
    } finally {
      setCreating(false);
    }
  };

  const remove = (task: ResearchTask) => {
    modal.confirm({
      title: `删除“${task.title}”？`,
      content: "研究计划、证据和报告将一并删除。",
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        await researchApi.remove(task.id);
        setActive(undefined);
        await load();
      },
    });
  };

  return (
    <div className="research-page">
      <aside className="research-rail">
        <div className="conversation-brand">
          <ExperimentOutlined />
          <span><strong>深度研究</strong><small>计划、证据与报告</small></span>
        </div>
        <Button type="primary" block icon={<PlusOutlined />} onClick={openCreate}>
          新建研究
        </Button>
        <div className="research-task-list">
          {tasks.map((task) => (
            <button
              type="button"
              className={`research-task ${active?.id === task.id ? "active" : ""}`}
              key={task.id}
              onClick={() =>
                void researchApi.get(task.id).then(setActive).catch((error) =>
                  message.error(apiErrorMessage(error, "研究详情加载失败")),
                )
              }
            >
              <span>{runningStatuses.includes(task.status) ? <LoadingOutlined spin /> : task.status === "completed" ? <CheckCircleOutlined /> : <FileSearchOutlined />}</span>
              <span><strong>{task.title}</strong><small>{stageLabels[task.stage] || task.stage}</small></span>
            </button>
          ))}
          {!loading && tasks.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="还没有研究任务" />}
        </div>
      </aside>

      <main className="research-main">
        {loading ? <Spin size="large" /> : !active ? (
          <div className="research-welcome">
            <span><ExperimentOutlined /></span>
            <Title>让星航仪完成一次系统研究</Title>
            <Paragraph>自动拆解课题，联合知识库、长期记忆和互联网搜集证据，经 Verifier 检查后生成可导出的引用报告。</Paragraph>
            <Button type="primary" size="large" icon={<PlusOutlined />} onClick={openCreate}>开始第一次研究</Button>
          </div>
        ) : (
          <ResearchDetail
            task={active}
            onDelete={() => remove(active)}
            onRetry={async () => {
              await researchApi.retry(active.id);
              await load(active.id);
            }}
          />
        )}
      </main>

      <Modal
        title="新建深度研究"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => form.submit()}
        okText="开始研究"
        cancelText="取消"
        confirmLoading={creating}
        forceRender
        width={680}
      >
        <Form form={form} layout="vertical" onFinish={(values) => void create(values)}>
          <Form.Item name="question" label="研究课题" rules={[{ required: true, min: 5, message: "请输入至少 5 个字的研究课题" }]}>
            <Input.TextArea autoSize={{ minRows: 4, maxRows: 8 }} placeholder="例如：系统分析城市物流无人机的技术路线、监管限制和商业化难点" />
          </Form.Item>
          <Form.Item name="title" label="报告标题（可选）"><Input placeholder="默认使用研究课题" /></Form.Item>
          <Form.Item name="knowledge_base_ids" label="知识库">
            <Select mode="multiple" maxTagCount="responsive" options={bases.map((item) => ({ label: item.name, value: item.id }))} suffixIcon={<BookOutlined />} />
          </Form.Item>
          <Space size="large" wrap>
            <Form.Item name="use_memory" valuePropName="checked"><Checkbox>使用长期记忆</Checkbox></Form.Item>
            <Form.Item name="allow_web" valuePropName="checked"><Checkbox><GlobalOutlined /> 使用联网搜索</Checkbox></Form.Item>
            <Form.Item name="max_iterations" label="最大验证轮数">
              <Select options={[1, 2, 3].map((value) => ({ label: `${value} 轮`, value }))} style={{ width: 110 }} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </div>
  );
}

function ResearchDetail({
  task,
  onDelete,
  onRetry,
}: {
  task: ResearchTaskDetail;
  onDelete: () => void;
  onRetry: () => Promise<void>;
}) {
  const { message } = App.useApp();
  const running = runningStatuses.includes(task.status);
  return (
    <>
      <header className="research-header">
        <div><Text className="page-kicker">DEEP RESEARCH</Text><Title level={2}>{task.title}</Title><Paragraph>{task.question}</Paragraph></div>
        <Space wrap>
          {task.allow_web && <Tag icon={<GlobalOutlined />} color="blue">联网</Tag>}
          {task.use_memory && <Tag color="purple">长期记忆</Tag>}
          <Button danger type="text" icon={<DeleteOutlined />} disabled={running} onClick={onDelete}>删除</Button>
        </Space>
      </header>

      <Card className="research-progress-card">
        <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
          <Space><Tag color={task.status === "completed" ? "green" : task.status === "failed" ? "red" : "processing"}>{stageLabels[task.stage] || task.stage}</Tag><Text type="secondary">验证 {task.iteration_count}/{task.max_iterations} 轮</Text><Text type="secondary">Token {task.total_tokens.toLocaleString("zh-CN")}</Text></Space>
          <Progress percent={Math.round(task.progress * 100)} status={task.status === "failed" ? "exception" : task.status === "completed" ? "success" : "active"} />
          {task.error_message && <Paragraph type="danger">{task.error_message}</Paragraph>}
          {task.status === "failed" && <Button icon={<RedoOutlined />} onClick={() => void onRetry().catch((error) => message.error(apiErrorMessage(error, "重试失败")))}>重新运行</Button>}
        </Space>
      </Card>

      {task.steps.length > 0 && <>
        <Title level={3}>研究计划与进度</Title>
        <Steps orientation="vertical" current={task.steps.filter((item) => item.status === "completed").length} items={task.steps.map((step) => ({
          title: step.question,
          status: step.status === "completed" ? "finish" : step.status === "running" ? "process" : "wait",
          content: step.finding ? <Paragraph ellipsis={{ rows: 3, expandable: true, symbol: "展开" }}>{step.finding}</Paragraph> : `${step.evidence_count} 条证据`,
        }))} />
      </>}

      {task.verifier_result && <Card title="Verifier 证据审查" className="verifier-card">
        <Space wrap><Tag color={task.verifier_result.sufficient ? "green" : "orange"}>{task.verifier_result.sufficient ? "证据充分" : "仍有证据缺口"}</Tag>{typeof task.verifier_result.coverage === "number" && <Tag>覆盖率 {Math.round(task.verifier_result.coverage * 100)}%</Tag>}</Space>
        {(task.verifier_result.gaps || []).map((gap) => <Paragraph key={gap}>• {gap}</Paragraph>)}
        {(task.verifier_result.conflicts || []).map((conflict) => <Paragraph type="warning" key={conflict}>冲突：{conflict}</Paragraph>)}
      </Card>}

      {task.evidence.length > 0 && <>
        <Title level={3}>证据库</Title>
        <Collapse items={task.evidence.map((item, index) => ({
          key: item.id,
          label: <Space><Tag>{sourceLabel(item)}</Tag><Text strong>[{index + 1}] {item.title}</Text></Space>,
          children: <><Paragraph>{item.quote}</Paragraph>{item.url && <Typography.Link href={item.url} target="_blank" rel="noreferrer">{item.url}</Typography.Link>}<br /><Text type="secondary">检索问题：{item.query}</Text></>,
        }))} />
      </>}

      {task.report_markdown && <section className="research-report-section">
        <div className="section-heading"><Title level={3}>最终研究报告</Title><Button icon={<CloudDownloadOutlined />} onClick={() => void researchApi.exportMarkdown(task).catch((error) => message.error(apiErrorMessage(error, "报告导出失败")))}>导出 Markdown</Button></div>
        <pre className="research-report">{task.report_markdown}</pre>
      </section>}
    </>
  );
}

function sourceLabel(item: ResearchEvidence) {
  return ({ document: "知识库", memory: "记忆", web: "网页" } as Record<string, string>)[item.source_type] || item.source_type;
}

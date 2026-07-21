import {
  CloudUploadOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  FileTextOutlined,
  LinkOutlined,
  PlusOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import {
  App,
  Button,
  Card,
  Empty,
  Form,
  Input,
  Modal,
  Progress,
  Space,
  Switch,
  Tag,
  Typography,
  Upload,
} from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { KnowledgeBase, KnowledgeDocument, SearchHit } from "../../entities/knowledge";
import { apiErrorMessage } from "../../shared/apiClient";
import { knowledgeApi } from "./knowledgeApi";

const { Dragger } = Upload;
const { Title, Paragraph, Text } = Typography;

const statusMeta: Record<KnowledgeDocument["status"], { label: string; color: string }> = {
  pending: { label: "等待处理", color: "default" },
  processing: { label: "处理中", color: "processing" },
  ready: { label: "可检索", color: "success" },
  failed: { label: "处理失败", color: "error" },
};

const stageLabels: Record<string, string> = {
  queued: "等待处理",
  fetching: "抓取网页",
  parsing: "解析文本",
  chunking: "父子分块",
  embedding: "生成向量",
  indexing: "建立索引",
  completed: "处理完成",
  failed: "处理失败",
};

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function KnowledgePage() {
  const { message, modal } = App.useApp();
  const [form] = Form.useForm<{ name: string; description?: string }>();
  const [bases, setBases] = useState<KnowledgeBase[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [addingWebPage, setAddingWebPage] = useState(false);
  const [searching, setSearching] = useState(false);
  const [useRerank, setUseRerank] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const selectedBase = useMemo(
    () => bases.find((item) => item.id === selectedId),
    [bases, selectedId],
  );

  const loadBases = useCallback(async () => {
    const items = await knowledgeApi.listBases();
    setBases(items);
    setSelectedId((current) =>
      current && items.some((item) => item.id === current) ? current : items[0]?.id,
    );
  }, []);

  const loadDocuments = useCallback(async (knowledgeBaseId: string) => {
    setDocuments(await knowledgeApi.listDocuments(knowledgeBaseId));
  }, []);

  useEffect(() => {
    void loadBases()
      .catch((error) => message.error(apiErrorMessage(error, "知识库加载失败")))
      .finally(() => setLoading(false));
  }, [loadBases, message]);

  useEffect(() => {
    setHits([]);
    if (!selectedId) return;
    void loadDocuments(selectedId).catch((error) =>
      message.error(apiErrorMessage(error, "文档加载失败")),
    );
  }, [loadDocuments, message, selectedId]);

  useEffect(() => {
    if (!selectedId || !documents.some((item) => ["pending", "processing"].includes(item.status))) {
      return;
    }
    const timer = window.setInterval(() => void loadDocuments(selectedId), 1800);
    return () => window.clearInterval(timer);
  }, [documents, loadDocuments, selectedId]);

  const createBase = async () => {
    try {
      const values = await form.validateFields();
      const created = await knowledgeApi.createBase(values);
      await loadBases();
      setSelectedId(created.id);
      setCreateOpen(false);
      form.resetFields();
      message.success("知识库已创建");
    } catch (error) {
      if (error && typeof error === "object" && "errorFields" in error) return;
      message.error(apiErrorMessage(error, "知识库创建失败"));
    }
  };

  const uploadFile = async (file: File) => {
    if (!selectedId) return Upload.LIST_IGNORE;
    setUploading(true);
    try {
      await knowledgeApi.uploadDocument(selectedId, file);
      await Promise.all([loadDocuments(selectedId), loadBases()]);
      message.success("文件已上传，正在建立索引");
    } catch (error) {
      message.error(apiErrorMessage(error, "文件上传失败"));
    } finally {
      setUploading(false);
    }
    return Upload.LIST_IGNORE;
  };

  const addWebPage = async (url: string) => {
    if (!selectedId || !url.trim()) return;
    setAddingWebPage(true);
    try {
      await knowledgeApi.addWebPage(selectedId, url.trim());
      await Promise.all([loadDocuments(selectedId), loadBases()]);
      message.success("网页已加入抓取队列");
    } catch (error) {
      message.error(apiErrorMessage(error, "网页入库失败"));
    } finally {
      setAddingWebPage(false);
    }
  };

  const removeDocument = (document: KnowledgeDocument) => {
    modal.confirm({
      title: `删除“${document.title}”？`,
      content: "原文件和检索索引会一并删除。",
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        await knowledgeApi.deleteDocument(document.id);
        if (selectedId) await Promise.all([loadDocuments(selectedId), loadBases()]);
        message.success("文档已删除");
      },
    });
  };

  const runSearch = async (query: string) => {
    if (!selectedId || !query.trim()) return;
    setSearching(true);
    try {
      setHits(await knowledgeApi.search(selectedId, query.trim(), useRerank));
    } catch (error) {
      message.error(apiErrorMessage(error, "检索失败"));
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="knowledge-page">
      <header className="page-heading">
        <div>
          <Text className="page-kicker">KNOWLEDGE ORBIT</Text>
          <Title level={1}>知识库</Title>
          <Paragraph>让文档进入可检索的知识轨道，每一次命中都有来源坐标。</Paragraph>
        </div>
        <Button type="primary" size="large" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          新建知识库
        </Button>
      </header>

      <div className="knowledge-workspace">
        <aside className="base-rail">
          <div className="rail-label">知识舱</div>
          {bases.map((item) => (
            <button
              type="button"
              className={`base-item ${item.id === selectedId ? "active" : ""}`}
              key={item.id}
              onClick={() => setSelectedId(item.id)}
            >
              <span className="base-icon"><DatabaseOutlined /></span>
              <span>
                <strong>{item.name}</strong>
                <small>{item.document_count} 份文档 · {item.image_count} 张图片{item.is_default ? " · 默认" : ""}</small>
              </span>
            </button>
          ))}
          {!loading && bases.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无知识库" />}
        </aside>

        <main className="knowledge-main">
          {selectedBase ? (
            <>
              <section className="base-overview">
                <div>
                  <Space><Tag color="green">检索已启用</Tag>{selectedBase.is_default && <Tag>默认知识库</Tag>}</Space>
                  <Title level={2}>{selectedBase.name}</Title>
                  <Paragraph>{selectedBase.description || "收纳资料，并建立带来源坐标的知识索引。"}</Paragraph>
                </div>
                <div className="base-stat"><strong>{selectedBase.document_count + selectedBase.image_count}</strong><span>份资料在轨</span></div>
              </section>

              <Dragger
                className="knowledge-uploader"
                accept=".pdf,.docx,.md,.markdown,.txt,.html,.htm"
                showUploadList={false}
                beforeUpload={uploadFile}
                disabled={uploading}
              >
                <p className="ant-upload-drag-icon"><CloudUploadOutlined /></p>
                <p className="ant-upload-text">{uploading ? "正在传输文件…" : "拖入资料，送入知识轨道"}</p>
                <p className="ant-upload-hint">支持 PDF、Word、Markdown、TXT、HTML，单个文件最大 25 MB</p>
              </Dragger>

              <section className="web-ingestion-bar">
                <span className="web-ingestion-icon"><LinkOutlined /></span>
                <div><Text strong>网页入库</Text><Text type="secondary">抓取公开网页正文，并进入同一套父子分块和混合检索。</Text></div>
                <Input.Search
                  enterButton="抓取入库"
                  placeholder="https://example.com/article"
                  loading={addingWebPage}
                  onSearch={(value) => void addWebPage(value)}
                />
              </section>

              <section className="document-section">
                <div className="section-heading"><Title level={3}>文档状态</Title><Text type="secondary">解析 → 分块 → 向量化 → 建立索引</Text></div>
                <div className="document-list" aria-busy={loading}>
                  {!loading && documents.length === 0 && (
                    <Empty description="上传第一份资料，开始构建知识库" />
                  )}
                  {documents.map((document) => {
                    const meta = statusMeta[document.status];
                    const progress = Math.round((document.ingestion_job?.progress ?? 0) * 100);
                    return (
                      <article className="document-row" key={document.id}>
                        <span className="document-icon">{document.source_type === "web" ? <LinkOutlined /> : <FileTextOutlined />}</span>
                        <div className="document-copy">
                          <Space wrap><Text strong>{document.title}</Text><Tag color={meta.color}>{meta.label}</Tag></Space>
                          {document.tags.length > 0 && <Space wrap size={4} className="content-tags">{document.tags.map((tag) => <Tag key={tag.id} color={tag.color}>{tag.name}</Tag>)}</Space>}
                          <Space wrap size="large" className="document-meta"><span>{document.source_type === "web" ? "网页" : formatSize(document.file_size)}</span><span>{document.chunk_count} 个检索片段</span><span>{new Date(document.created_at).toLocaleString("zh-CN")}</span></Space>
                          {document.ingestion_job && ["pending", "processing"].includes(document.status) && (
                            <div className="document-progress"><Progress percent={progress} size="small" /><small>{stageLabels[document.ingestion_job.stage] || document.ingestion_job.stage}</small></div>
                          )}
                          {document.status === "failed" && <Text className="document-error" type="danger">{document.error_message}</Text>}
                        </div>
                        <Button type="text" danger icon={<DeleteOutlined />} aria-label={`删除 ${document.title}`} onClick={() => removeDocument(document)} />
                      </article>
                    );
                  })}
                </div>
              </section>

              <section className="retrieval-section">
                <div className="section-heading">
                  <div><Title level={3}>混合检索</Title><Text type="secondary">IK-BM25 + 百炼向量，命中子块后返回父块上下文</Text></div>
                  <Space><Text type="secondary">Rerank</Text><Switch checked={useRerank} onChange={setUseRerank} /></Space>
                </div>
                <Input.Search size="large" enterButton={<><SearchOutlined /> 检索</>} placeholder="输入文档中出现的问题或概念" loading={searching} onSearch={(value) => void runSearch(value)} />
                <div className="search-results">
                  {hits.map((hit, index) => (
                    <Card key={hit.chunk_id} className="search-hit">
                      <div className="hit-head"><Tag color="green">#{index + 1}</Tag><Text strong>{hit.citation.document_title}</Text><Text type="secondary">相关度 {Math.round(hit.score * 100)}%</Text></div>
                      <Paragraph ellipsis={{ rows: 4, expandable: true, symbol: "展开上下文" }}>{hit.content}</Paragraph>
                      <div className="citation-line">来源：{hit.citation.file_name || hit.citation.document_title}{hit.citation.page ? ` · 第 ${hit.citation.page} 页` : ""}</div>
                    </Card>
                  ))}
                  {!searching && hits.length === 0 && documents.some((item) => item.status === "ready") && <div className="search-empty">输入关键词，验证文档是否已经进入知识轨道。</div>}
                </div>
              </section>
            </>
          ) : <Empty description="请先创建知识库" />}
        </main>
      </div>

      <Modal title="新建知识库" open={createOpen} okText="创建" cancelText="取消" onOk={() => void createBase()} onCancel={() => setCreateOpen(false)}>
        <Form form={form} layout="vertical" requiredMark={false}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: "请输入知识库名称" }]}><Input placeholder="例如：课题论文" maxLength={128} /></Form.Item>
          <Form.Item name="description" label="说明"><Input.TextArea placeholder="这个知识库收录什么资料？" rows={3} maxLength={1024} showCount /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

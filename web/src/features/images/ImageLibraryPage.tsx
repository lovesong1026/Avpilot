import {
  CloudUploadOutlined,
  DeleteOutlined,
  EyeOutlined,
  PictureOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import {
  App,
  Button,
  Drawer,
  Empty,
  Input,
  Progress,
  Select,
  Space,
  Tag,
  Typography,
  Upload,
} from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { ImageAsset, ImageSearchHit } from "../../entities/images";
import type { KnowledgeBase } from "../../entities/knowledge";
import { apiErrorMessage } from "../../shared/apiClient";
import { knowledgeApi } from "../knowledge/knowledgeApi";
import { AuthenticatedImage } from "./AuthenticatedImage";
import { imageApi } from "./imageApi";

const { Dragger } = Upload;
const { Title, Paragraph, Text } = Typography;

const statusMeta: Record<ImageAsset["status"], { label: string; color: string }> = {
  pending: { label: "等待分析", color: "default" },
  processing: { label: "AI 分析中", color: "processing" },
  ready: { label: "可检索", color: "success" },
  failed: { label: "处理失败", color: "error" },
};

const stageLabels: Record<string, string> = {
  queued: "等待处理",
  vision: "理解图片",
  embedding: "生成向量",
  indexing: "建立索引",
  completed: "处理完成",
  failed: "处理失败",
};

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function ImageLibraryPage() {
  const { message, modal } = App.useApp();
  const [bases, setBases] = useState<KnowledgeBase[]>([]);
  const [selectedBaseId, setSelectedBaseId] = useState<string>();
  const [images, setImages] = useState<ImageAsset[]>([]);
  const [hits, setHits] = useState<ImageSearchHit[]>([]);
  const [query, setQuery] = useState("");
  const [uploading, setUploading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeImage, setActiveImage] = useState<ImageAsset>();

  const loadImages = useCallback(async (knowledgeBaseId?: string) => {
    setImages(await imageApi.list(knowledgeBaseId));
  }, []);

  useEffect(() => {
    void knowledgeApi.listBases()
      .then((items) => {
        setBases(items);
        setSelectedBaseId(items[0]?.id);
      })
      .catch((error) => message.error(apiErrorMessage(error, "图片库加载失败")))
      .finally(() => setLoading(false));
  }, [message]);

  useEffect(() => {
    setHits([]);
    setQuery("");
    if (!selectedBaseId) return;
    void loadImages(selectedBaseId).catch((error) =>
      message.error(apiErrorMessage(error, "图片加载失败")),
    );
  }, [loadImages, message, selectedBaseId]);

  useEffect(() => {
    if (!selectedBaseId || !images.some((item) => ["pending", "processing"].includes(item.status))) return;
    const timer = window.setInterval(() => void loadImages(selectedBaseId), 1800);
    return () => window.clearInterval(timer);
  }, [images, loadImages, selectedBaseId]);

  const imageById = useMemo(
    () => new Map(images.map((item) => [item.id, item])),
    [images],
  );

  const uploadImage = async (file: File) => {
    if (!selectedBaseId) return Upload.LIST_IGNORE;
    setUploading(true);
    try {
      await imageApi.upload(selectedBaseId, file);
      await loadImages(selectedBaseId);
      message.success("图片已上传，正在进行多模态分析");
    } catch (error) {
      message.error(apiErrorMessage(error, "图片上传失败"));
    } finally {
      setUploading(false);
    }
    return Upload.LIST_IGNORE;
  };

  const runSearch = async (value: string) => {
    const normalized = value.trim();
    setQuery(normalized);
    if (!normalized || !selectedBaseId) {
      setHits([]);
      return;
    }
    setSearching(true);
    try {
      setHits(await imageApi.search(normalized, [selectedBaseId]));
    } catch (error) {
      message.error(apiErrorMessage(error, "图片检索失败"));
    } finally {
      setSearching(false);
    }
  };

  const removeImage = (image: ImageAsset) => {
    modal.confirm({
      title: `删除“${image.file_name}”？`,
      content: "原图、AI 分析结果和检索索引将一并删除。",
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        await imageApi.remove(image.id);
        if (selectedBaseId) await loadImages(selectedBaseId);
        setHits((items) => items.filter((item) => item.image_id !== image.id));
        message.success("图片已删除");
      },
    });
  };

  const visibleImages = query
    ? hits.map((hit) => ({ image: imageById.get(hit.image_id), hit })).filter((item) => item.image)
    : images.map((image) => ({ image, hit: undefined }));

  return (
    <div className="image-library-page">
      <header className="page-heading">
        <div>
          <Text className="page-kicker">VISUAL ORBIT</Text>
          <Title level={1}>图片库</Title>
          <Paragraph>让图片拥有描述、文字和语义坐标，不再只能依靠文件名寻找。</Paragraph>
        </div>
        <Select
          className="image-base-select"
          value={selectedBaseId}
          placeholder="选择知识库"
          options={bases.map((item) => ({ label: item.name, value: item.id }))}
          onChange={setSelectedBaseId}
        />
      </header>

      <section className="image-control-panel">
        <Dragger
          accept=".jpg,.jpeg,.png,.webp,.gif,.bmp"
          showUploadList={false}
          beforeUpload={uploadImage}
          disabled={uploading || !selectedBaseId}
        >
          <p className="ant-upload-drag-icon"><CloudUploadOutlined /></p>
          <p className="ant-upload-text">{uploading ? "正在上传图片…" : "拖入图片，送入视觉轨道"}</p>
          <p className="ant-upload-hint">AI 将自动生成描述、OCR、物体与场景，单张最大 20 MB</p>
        </Dragger>
        <div className="image-search-box">
          <Text strong>语义检索</Text>
          <Input.Search
            size="large"
            allowClear
            enterButton={<><SearchOutlined /> 搜索</>}
            placeholder="例如：带有流程图的实验室截图"
            loading={searching}
            onSearch={(value) => void runSearch(value)}
            onChange={(event) => { if (!event.target.value) void runSearch(""); }}
          />
          <Text type="secondary">同时检索图片描述、OCR 文字、物体和场景。</Text>
        </div>
      </section>

      <section className="image-gallery-section">
        <div className="section-heading">
          <Title level={3}>{query ? `“${query}”的搜索结果` : "图片航图"}</Title>
          <Text type="secondary">{query ? `命中 ${hits.length} 张` : `${images.length} 张图片`}</Text>
        </div>
        {!loading && visibleImages.length === 0 && (
          <Empty image={<PictureOutlined />} description={query ? "没有找到相关图片" : "上传第一张图片开始构建视觉知识库"} />
        )}
        <div className="image-grid">
          {visibleImages.map(({ image, hit }) => image && (
            <article className="image-card" key={image.id}>
              <button className="image-preview" type="button" onClick={() => setActiveImage(image)}>
                <AuthenticatedImage imageId={image.id} alt={image.file_name} />
                {hit && <Tag color="green">相关度 {Math.round(hit.score * 100)}%</Tag>}
              </button>
              <div className="image-card-copy">
                <div className="image-card-head"><Text strong ellipsis>{image.file_name}</Text><Tag color={statusMeta[image.status].color}>{statusMeta[image.status].label}</Tag></div>
                <Paragraph ellipsis={{ rows: 2 }}>{image.description || "等待 AI 生成图片描述…"}</Paragraph>
                {image.tags.length > 0 && <Space wrap size={4} className="content-tags">{image.tags.map((tag) => <Tag key={tag.id} color={tag.color}>{tag.name}</Tag>)}</Space>}
                {image.status === "processing" && image.ingestion_job && <Progress percent={Math.round(image.ingestion_job.progress * 100)} size="small" format={() => stageLabels[image.ingestion_job?.stage || ""] || "处理中"} />}
                {image.status === "failed" && <Text type="danger">{image.error_message}</Text>}
                <div className="image-card-actions"><Text type="secondary">{formatSize(image.file_size)}</Text><Space><Button type="text" size="small" icon={<EyeOutlined />} onClick={() => setActiveImage(image)}>详情</Button><Button type="text" size="small" danger icon={<DeleteOutlined />} onClick={() => removeImage(image)} /></Space></div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <Drawer title="图片语义档案" open={Boolean(activeImage)} onClose={() => setActiveImage(undefined)} size={520}>
        {activeImage && <div className="image-detail">
          <div className="image-detail-preview"><AuthenticatedImage imageId={activeImage.id} alt={activeImage.file_name} /></div>
          <Title level={3}>{activeImage.file_name}</Title>
          <Space wrap>{activeImage.scene && <Tag color="green">{activeImage.scene}</Tag>}{activeImage.objects?.map((item) => <Tag key={item}>{item}</Tag>)}</Space>
          {activeImage.tags.length > 0 && <><Title level={5}>AI 分类</Title><Space wrap>{activeImage.tags.map((tag) => <Tag key={tag.id} color={tag.color}>{tag.name}</Tag>)}</Space></>}
          <Title level={5}>AI 描述</Title><Paragraph>{activeImage.description || "尚未生成"}</Paragraph>
          <Title level={5}>OCR 文字</Title><Paragraph className="image-ocr">{activeImage.ocr_text || "没有识别到文字"}</Paragraph>
        </div>}
      </Drawer>
    </div>
  );
}

import {
  BookOutlined,
  BulbOutlined,
  DeleteOutlined,
  EditOutlined,
  FileImageOutlined,
  NodeIndexOutlined,
  PlusOutlined,
  SearchOutlined,
  StarFilled,
  StarOutlined,
  TagsOutlined,
} from "@ant-design/icons";
import { App, Button, Empty, Input, Modal, Space, Spin, Tag, Typography } from "antd";
import { useEffect, useMemo, useState } from "react";

import type {
  DailyReview,
  Favorite,
  GlobalSearchHit,
  ManagedTag,
  SearchResponse,
} from "../../entities/navigation";
import { apiErrorMessage } from "../../shared/apiClient";
import { navigationApi } from "./navigationApi";

const { Title, Paragraph, Text } = Typography;

const emptyResults: SearchResponse = { query: "", documents: [], images: [], memories: [] };

const lanes = [
  { key: "documents", title: "文档", icon: <BookOutlined />, empty: "没有相关文档" },
  { key: "images", title: "图片", icon: <FileImageOutlined />, empty: "没有相关图片" },
  { key: "memories", title: "记忆", icon: <NodeIndexOutlined />, empty: "没有相关记忆" },
] as const;

export function SearchPage() {
  const { message, modal } = App.useApp();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResponse>(emptyResults);
  const [favorites, setFavorites] = useState<Favorite[]>([]);
  const [tags, setTags] = useState<ManagedTag[]>([]);
  const [review, setReview] = useState<DailyReview>();
  const [searching, setSearching] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [tagModal, setTagModal] = useState<{ tag?: ManagedTag; name: string; color: string }>();

  const loadNavigation = async () => {
    const [nextFavorites, nextTags, nextReview] = await Promise.all([
      navigationApi.favorites(),
      navigationApi.tags(),
      navigationApi.dailyReview(),
    ]);
    setFavorites(nextFavorites);
    setTags(nextTags);
    setReview(nextReview);
  };

  useEffect(() => {
    void loadNavigation().catch((error) =>
      message.error(apiErrorMessage(error, "导航数据加载失败")),
    );
  }, [message]);

  const favoriteByTarget = useMemo(
    () => new Map(favorites.map((item) => [`${item.target_type}:${item.target_id}`, item])),
    [favorites],
  );

  const runSearch = async (value: string) => {
    const normalized = value.trim();
    setQuery(normalized);
    if (!normalized) {
      setResults(emptyResults);
      return;
    }
    setSearching(true);
    try {
      setResults(await navigationApi.search(normalized));
    } catch (error) {
      message.error(apiErrorMessage(error, "全局搜索失败"));
    } finally {
      setSearching(false);
    }
  };

  const toggleFavorite = async (hit: GlobalSearchHit) => {
    const key = `${hit.target_type}:${hit.target_id}`;
    const existing = favoriteByTarget.get(key);
    try {
      if (existing) {
        await navigationApi.removeFavorite(existing.id);
        setFavorites((items) => items.filter((item) => item.id !== existing.id));
        message.success("已取消收藏");
      } else {
        const favorite = await navigationApi.addFavorite(hit);
        setFavorites((items) => [favorite, ...items.filter((item) => item.id !== favorite.id)]);
        message.success("已加入收藏夹");
      }
    } catch (error) {
      message.error(apiErrorMessage(error, "收藏操作失败"));
    }
  };

  const saveTag = async () => {
    if (!tagModal?.name.trim()) return;
    try {
      if (tagModal.tag) {
        await navigationApi.updateTag(tagModal.tag.id, tagModal.name.trim(), tagModal.color);
      } else {
        await navigationApi.createTag(tagModal.name.trim(), tagModal.color);
      }
      setTags(await navigationApi.tags());
      setTagModal(undefined);
      message.success("标签已保存");
    } catch (error) {
      message.error(apiErrorMessage(error, "标签保存失败"));
    }
  };

  const removeTag = (item: ManagedTag) => {
    modal.confirm({
      title: `删除标签“${item.name}”？`,
      content: "文档、图片和搜索索引中的该标签关联会一并移除。",
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        await navigationApi.removeTag(item.id);
        setTags((items) => items.filter((tag) => tag.id !== item.id));
      },
    });
  };

  const refreshReview = async () => {
    setReviewing(true);
    try {
      setReview(await navigationApi.dailyReview(true));
      message.success("今日回顾已更新");
    } catch (error) {
      message.error(apiErrorMessage(error, "每日回顾生成失败"));
    } finally {
      setReviewing(false);
    }
  };

  return (
    <div className="global-search-page">
      <header className="search-hero">
        <Text className="page-kicker">UNIFIED NAVIGATION</Text>
        <Title level={1}>全局领航</Title>
        <Paragraph>一次查询横跨文档、图片和长期记忆；只有超过语义相关度门槛的结果才会出现。</Paragraph>
        <Input.Search
          size="large"
          allowClear
          value={query}
          loading={searching}
          enterButton={<><SearchOutlined /> 搜索全部</>}
          placeholder="搜索一个主题、画面、人物或事件"
          onChange={(event) => setQuery(event.target.value)}
          onSearch={(value) => void runSearch(value)}
        />
      </header>

      <section className="search-lanes">
        {lanes.map((lane) => {
          const hits = results[lane.key];
          return <article className="search-lane" key={lane.key}>
            <div className="search-lane-head"><span>{lane.icon}</span><Title level={3}>{lane.title}</Title><Tag>{hits.length}</Tag></div>
            {searching && <div className="lane-loading"><Spin /></div>}
            {!searching && hits.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={results.query ? lane.empty : "等待搜索"} />}
            <div className="lane-results">
              {hits.map((hit) => {
                const favorite = favoriteByTarget.has(`${hit.target_type}:${hit.target_id}`);
                return <div className="global-hit" key={`${hit.target_type}-${hit.target_id}`}>
                  <div className="global-hit-head"><Text strong ellipsis={{ tooltip: hit.title }}>{hit.title}</Text><Button type="text" icon={favorite ? <StarFilled /> : <StarOutlined />} className={favorite ? "favorite-active" : ""} onClick={() => void toggleFavorite(hit)} /></div>
                  <Paragraph ellipsis={{ rows: 4 }}>{hit.excerpt}</Paragraph>
                  <div className="global-hit-foot"><Space wrap size={3}>{hit.tags.slice(0, 3).map((item) => <Tag key={item}>{item}</Tag>)}</Space><Text>{Math.round(hit.score * 100)}%</Text></div>
                </div>;
              })}
            </div>
          </article>;
        })}
      </section>

      <section className="navigation-panels">
        <article className="daily-review-panel">
          <div className="panel-title"><span><BulbOutlined /></span><div><Title level={3}>每日回顾</Title><Text type="secondary">{review?.review_date || "今天"}</Text></div><Button loading={reviewing} onClick={() => void refreshReview()}>重新生成</Button></div>
          <Paragraph>{review?.content || "正在整理今天的知识轨迹…"}</Paragraph>
          {review && <div className="review-stats">{Object.entries(review.stats).map(([key, value]) => <span key={key}><strong>{value}</strong>{({ questions: "提问", memories: "记忆", documents: "文档", images: "图片" } as Record<string, string>)[key] || key}</span>)}</div>}
        </article>

        <article className="favorites-panel">
          <div className="panel-title"><span><StarFilled /></span><div><Title level={3}>收藏夹</Title><Text type="secondary">{favorites.length} 项</Text></div></div>
          <div className="favorite-list">
            {favorites.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="搜索结果可一键收藏" />}
            {favorites.slice(0, 8).map((item) => <div key={item.id}><Tag>{item.target_type}</Tag><Text ellipsis>{String(item.snapshot?.title || item.target_id)}</Text><Button type="text" danger icon={<DeleteOutlined />} onClick={() => void navigationApi.removeFavorite(item.id).then(() => setFavorites((rows) => rows.filter((row) => row.id !== item.id)))} /></div>)}
          </div>
        </article>

        <article className="tags-panel">
          <div className="panel-title"><span><TagsOutlined /></span><div><Title level={3}>标签管理</Title><Text type="secondary">{tags.length} 个标签</Text></div><Button icon={<PlusOutlined />} onClick={() => setTagModal({ name: "", color: "#315F4D" })}>新建</Button></div>
          <div className="managed-tags">
            {tags.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="入库后将自动生成标签" />}
            {tags.map((item) => <div key={item.id}><Tag color={item.color}>{item.name}</Tag><Text type="secondary">{item.document_count} 文档 · {item.image_count} 图片</Text><Space size={0}><Button type="text" icon={<EditOutlined />} onClick={() => setTagModal({ tag: item, name: item.name, color: item.color })} /><Button type="text" danger icon={<DeleteOutlined />} onClick={() => removeTag(item)} /></Space></div>)}
          </div>
        </article>
      </section>

      <Modal title={tagModal?.tag ? "编辑标签" : "新建标签"} open={Boolean(tagModal)} okText="保存" cancelText="取消" onOk={() => void saveTag()} onCancel={() => setTagModal(undefined)}>
        {tagModal && <div className="tag-editor"><Input value={tagModal.name} placeholder="标签名称" onChange={(event) => setTagModal({ ...tagModal, name: event.target.value })} /><label>标签颜色<input type="color" value={tagModal.color} onChange={(event) => setTagModal({ ...tagModal, color: event.target.value })} /></label></div>}
      </Modal>
    </div>
  );
}


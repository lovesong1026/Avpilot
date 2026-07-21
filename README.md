# Avpilot 星航仪

你的 AI 知识领航系统。面向 AVP 课题组，沉淀可检索、可引用、可追溯的知识与记忆。

## 文档

- [整体架构设计](docs/architecture.md)
- [v0.1 功能契约](docs/v0.1-scope.md)
- [v0.2 知识库检索闭环](docs/v0.2-knowledge-ingestion.md)
- [v0.3 可追溯流式问答](docs/v0.3-grounded-chat.md)
- [v0.4 多模态、网页与自动标签](docs/v0.4-multimodal-ingestion.md)

## 当前阶段

项目已完成 v0.4 多模态与标签：公开网页可抓取入库，图片会自动生成描述、OCR、物体和场景信息，并可通过自然语言语义检索；文档、网页和图片入库后都会自动分类，优先复用已有标签。

下一条交付主线是 v0.5 长期记忆：从主动记忆和对话中萃取结构化陈述与三元组，写入可溯源的 Neo4j 四层图谱。

## 版本演进路线

| 阶段 | 状态 | 主要改进 |
| --- | --- | --- |
| 项目骨架 | ✅ 已完成 | 建立 `api`、`web`、`docs`、`docker` 分层目录；使用 uv 管理 Python 环境，使用 React + TypeScript + Vite 构建前端。 |
| 基础设施 | ✅ 已完成 | 接入 PostgreSQL、Elasticsearch、Neo4j、Redis；提供 Docker Compose、健康检查与数据库迁移基线。 |
| v0.1 工程基座 | ✅ 已完成 | 完成用户注册登录、JWT 刷新、默认知识库、核心数据表、百炼 Chat/Embedding/Vision/Rerank 适配、IK 分词索引和父子分块；完成“Avpilot 星航仪”登录页与工作台。 |
| v0.2 知识库闭环 | ✅ 已完成 | 支持 PDF、DOCX、Markdown、TXT、HTML 上传解析；完成本地存储、任务进度、父子块索引、IK-BM25 + 向量 RRF 混合检索、可选 Rerank 和来源定位。 |
| v0.3 可追溯问答 | ✅ 已完成 | 建立会话与消息持久化，将知识检索接入百炼模型，通过 SSE 输出检索、引用、文本增量和完成事件；前端提供对话历史、知识库选择和引用展开。 |
| v0.4 多模态与标签 | ✅ 已完成 | 支持网页与图片入库，自动生成图片描述、OCR、物体和场景；自动分类并优先复用已有标签。 |
| v0.5 长期记忆 | 📋 计划中 | 从主动记忆和对话中提取三元组，建立 `来源 → 片段 → 陈述 → 实体` 四层 Neo4j 图谱；增加事件时间线、两层去重和社区聚类。 |
| v0.6 搜索与可视化 | 📋 计划中 | 实现文档、图片、记忆三类全局搜索，补充收藏、每日回顾、AntV X6 知识图谱和 ECharts 统计仪表盘。 |

### 已完成的改进记录

#### 1. 项目骨架

- 建立前后端分离的单仓库结构。
- 后端使用 FastAPI，前端使用 React、TypeScript 和 Vite。
- 建立架构文档、ADR 与 API 文档目录。
- 对应提交：`ab6e754 avpilot框架1.0`。

#### 2. 基础设施连接

- 使用 Docker Compose 管理 PostgreSQL、Elasticsearch、Neo4j 和 Redis。
- Elasticsearch 使用带 IK 中文分词插件的自定义镜像。
- 增加存活检查与四类依赖健康检查。
- 对应提交：`724e354 feat: 完成基础设施连接与健康检查`。

#### 3. 知识系统工程基座与星航仪前端

- 建立用户、知识库、文档、图片、标签、对话、记忆和每日回顾等核心数据模型。
- 完成注册、登录、退出、Token 轮换和受保护路由。
- 接入阿里百炼 Chat、Embedding、Vision 与可选 Rerank。
- 建立父子分块和 Elasticsearch 向量索引定义。
- 完成“Avpilot 星航仪”品牌、登录注册页、主布局和工作台。
- 对应提交：`63dc688 实现知识系统基础架构与星航仪前端`。

#### 4. 知识库入库与混合检索闭环

- 支持知识库创建、列表和删除。
- 支持 PDF、Word、Markdown、TXT 与 HTML 文档上传。
- 文档经过解析、父子分块、百炼向量化后进入 Elasticsearch。
- 使用 IK-BM25 与向量召回，通过 RRF 融合，支持可选 Rerank。
- 搜索结果返回父块上下文，并保留文件名、PDF 页码或字符位置。
- 前端展示上传、处理进度、文档状态、检索结果与引用来源。
- 对应提交：`1272b79 实现知识库入库与混合检索闭环`。

#### 5. 可追溯流式问答

- 建立会话、消息和引用快照的持久化，并支持会话知识库多选。
- 将 IK-BM25、向量召回与 RRF 融合结果注入百炼模型上下文。
- 通过 SSE 依次返回会话元数据、检索状态、引用、文本增量和完成事件。
- 回答严格依据检索资料生成；资料不足时明确拒答，降低无依据生成风险。
- 前端支持对话历史、新建与删除、知识库选择、实时回答和引用原文抽屉。

#### 6. 多模态、网页与自动标签

- 支持公开 HTTP/HTTPS 网页抓取，阻断本机、内网、保留地址和不安全重定向。
- 网页正文快照复用文档父子分块、向量化、IK-BM25 与 RRF 混合检索。
- 支持 JPG、PNG、WebP、GIF 与 BMP 图片上传，并校验真实图片内容和像素上限。
- 百炼视觉模型自动生成图片描述、OCR 文字、主要物体和场景分类。
- 图片描述与 OCR 统一向量化进入 Elasticsearch，可通过自然语言语义检索。
- 文档、网页和图片自动生成宽泛主题标签，并优先复用当前用户已有标签。
- 新增独立图片库页面，支持知识库筛选、处理进度、语义搜索和详情档案。

### 后续实施原则

- 每一版先完成一条可以真实验收的纵向闭环，再扩展更多输入类型和工具。
- 已完成能力必须通过单元测试、生产构建和真实浏览器流程验证。
- PostgreSQL 保存业务事实，Elasticsearch 负责检索，Neo4j 负责可溯源记忆关系，Redis 负责任务与缓存。
- 参考 Comet 的成熟思路，但保持 Avpilot 自己的领域模型、接口契约、界面和测试。

## 本地开发

安装并验证后端：

```bash
cd api
uv sync
uv run pytest
uv run uvicorn app.main:app --reload
```

安装并启动前端：

```bash
cd web
npm install
npm run dev
```

启动基础存储：

```bash
cp .env.example .env
docker compose up -d
cd api
uv run alembic upgrade head
```

健康检查：

```text
GET http://localhost:8000/api/health/live  # 进程存活
GET http://localhost:8000/api/health       # 四类存储就绪状态
```

Avpilot 的 Elasticsearch 使用宿主机端口 `19200`，避免与其他本地项目常用的 `9200` 冲突。

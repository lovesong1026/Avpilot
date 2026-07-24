# Avpilot 星航仪

你的 AI 知识领航系统。面向 AVP 课题组，沉淀可检索、可引用、可追溯的知识与记忆。

## 文档

- [整体架构设计](docs/architecture.md)
- [v0.1 功能契约](docs/v0.1-scope.md)
- [v0.2 知识库检索闭环](docs/v0.2-knowledge-ingestion.md)
- [v0.3 可追溯流式问答](docs/v0.3-grounded-chat.md)
- [v0.4 多模态、网页与自动标签](docs/v0.4-multimodal-ingestion.md)
- [v0.5 可溯源长期记忆](docs/v0.5-traceable-memory.md)
- [v0.6 搜索导航与可视化](docs/v0.6-search-and-visualization.md)
- [v0.7 智能 Agent Workflow](docs/v0.7-agent-workflow.md)
- [v0.8 可靠任务系统](docs/v0.8-reliable-tasks.md)
- [v0.9 质量评测与可观测性](docs/v0.9-quality-observability.md)

## 当前阶段

项目已完成 v0.9 质量评测与可观测性：每次智能问答都会形成用户隔离的 Agent
Trace，记录编排模式、阶段 Span、工具调用、检索快照、引用、模型、输入/输出 Token、
耗时和失败状态。仪表盘可以查看 Token 趋势、Agent 成功率、工具分布及最近 Trace；
`eval/` 提供确定性的 RAG 离线评测，GitHub Actions 自动执行后端、前端、迁移、
PostgreSQL/Redis/Celery 集成与 Compose 检查。本项目不估算或保存模型费用。

## 版本演进路线

| 阶段 | 状态 | 主要改进 |
| --- | --- | --- |
| 项目骨架 | ✅ 已完成 | 建立 `api`、`web`、`docs`、`docker` 分层目录；使用 uv 管理 Python 环境，使用 React + TypeScript + Vite 构建前端。 |
| 基础设施 | ✅ 已完成 | 接入 PostgreSQL、Elasticsearch、Neo4j、Redis；提供 Docker Compose、健康检查与数据库迁移基线。 |
| v0.1 工程基座 | ✅ 已完成 | 完成用户注册登录、JWT 刷新、默认知识库、核心数据表、百炼 Chat/Embedding/Vision/Rerank 适配、IK 分词索引和父子分块；完成“Avpilot 星航仪”登录页与工作台。 |
| v0.2 知识库闭环 | ✅ 已完成 | 支持 PDF、DOCX、Markdown、TXT、HTML 上传解析；完成本地存储、任务进度、父子块索引、IK-BM25 + 向量 RRF 混合检索、可选 Rerank 和来源定位。 |
| v0.3 可追溯问答 | ✅ 已完成 | 建立会话与消息持久化，将知识检索接入百炼模型，通过 SSE 输出检索、引用、文本增量和完成事件；前端提供对话历史、知识库选择和引用展开。 |
| v0.4 多模态与标签 | ✅ 已完成 | 支持网页与图片入库，自动生成图片描述、OCR、物体和场景；自动分类并优先复用已有标签。 |
| v0.5 长期记忆 | ✅ 已完成 | 从主动记忆和对话中提取三元组，建立 `来源 → 片段 → 陈述 → 实体` 四层 Neo4j 图谱；增加事件时间线、两层去重和社区聚类。 |
| v0.6 搜索与可视化 | ✅ 已完成 | 实现文档、图片、记忆三类全局搜索，补充收藏、标签管理、每日回顾、AntV X6 知识图谱和 ECharts 统计仪表盘。 |
| v0.7 智能 Agent | ✅ 已完成 | 使用 LangChain 自主编排知识库、长期记忆和可选联网搜索；支持 Function Calling/ReAct 双模式、SSE 工具轨迹、统一引用、Token 刷新和图片多模态问答。 |
| v0.8 可靠任务系统 | ✅ 已完成 | 使用 Redis/Celery 的 ingestion、memory、maintenance 队列迁移耗时任务；加入事务型 Outbox、晚确认、指数退避、任务认领、Beat 补投与卡死恢复，并支持前端手动重试。 |
| v0.9 质量与可观测性 | ✅ 已完成 | 建立 Agent Trace、Span、检索快照和 Token 统计；仪表盘展示耗时、成功率与工具分布；加入 RAG 离线评测、真实 PostgreSQL/Celery 集成测试和 GitHub Actions。 |

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

#### 7. 可溯源长期记忆

- 支持“主动记住”，并在知识问答结束后异步分析用户消息，不阻塞 SSE 回答。
- 百炼模型只萃取稳定画像、偏好、目标、关系和明确事件，过滤寒暄、普通问句与低置信内容。
- Neo4j 建立 `来源 → 片段 → 陈述 → 实体` 四层溯源链，同时保存实体间三元组关系。
- 画像类陈述进入用户画像，事件类陈述保留 ISO 时间并进入独立时间线。
- 第一层按规范化业务键去重，第二层按 Embedding 余弦相似度跨批次复用实体与陈述。
- 不依赖 Neo4j GDS，使用连通分量为实体关系生成社区并回写 `community_id`。
- 新增记忆星图页面，展示来源任务、抽取统计、画像/事件节点、时间线和社区成员。

#### 8. 搜索导航与可视化

- 单次 Embedding 后并行检索 Elasticsearch 文档、图片与 Neo4j 记忆，三类结果并列展示。
- 使用绝对余弦相关度门控，不再因为“总有第一名”而展示无关结果。
- 启用收藏夹，支持文档、图片、记忆和消息快照的幂等收藏与取消。
- 增加标签新建、重命名、换色和删除；变更会同步更新 Elasticsearch 标签字段。
- 汇总当天提问、记忆、文档与图片，由百炼生成每日回顾并持久化复用。
- 使用 AntV X6 将四层记忆图谱变成可拖拽、可缩放的关系图。
- 使用 ECharts 展示近 14 天记忆趋势、标签或社区分布，并增加六类实时统计。
- 前端改为路由级懒加载，避免 X6 与 ECharts 进入登录和普通业务页面的首屏包。

#### 9. 智能 Agent Workflow

- 使用 LangChain `create_agent` 把知识库、长期记忆和联网搜索封装为用户隔离工具。
- 强模型走原生 Function Calling，不支持工具调用时自动降级到受限 ReAct 循环。
- SSE 实时发送 Agent、工具开始、工具完成、引用、文本增量和完成事件。
- 工具名称、参数、状态、耗时、命中数和错误随助手消息持久化。
- 联网搜索由用户显式开关控制，关闭时不向模型注册联网工具。
- 文档、记忆和网页使用统一引用结构，网页引用保留真实 URL。
- 支持从图片库附加最多三张图片，由百炼视觉模型进行看图问答。
- 修复聊天流绕过 Axios 后无法自动刷新 Access Token 的问题。

#### 10. 可靠任务系统

- 文档、网页、图片和记忆萃取不再由 FastAPI `BackgroundTasks` 或脱离请求的
  `asyncio.create_task` 执行。
- PostgreSQL 在创建业务记录的同一事务中写入 `task_outbox`；Redis 暂时不可用时，
  Celery Beat 会在恢复后补投，避免任务永久停留在 `pending`。
- Celery 按 `ingestion`、`memory`、`maintenance` 三队列隔离任务，并启用
  `acks_late`、Worker 丢失重入队、单任务预取、软硬超时和 Redis 可见性窗口。
- 临时错误最多自动重试四次，使用 30 秒起步的指数退避；解析错误、文件不存在和
  安全校验错误直接失败。
- Outbox 通过数据库行锁认领任务，过滤并发重复投递；ES 写入前删除旧索引，
  Neo4j 延续业务键 `MERGE`，实现至少一次投递下的幂等收敛。
- Beat 每 30 秒补投 Outbox，每分钟检查中断任务，每天重建记忆社区。
- 文档、图片和记忆页面在失败后提供手动重试入口。

#### 11. 质量评测与可观测性

- 每轮智能问答从用户消息开始创建稳定 `trace_id`，并随 SSE `meta` 和 `completed`
  事件返回。
- PostgreSQL 分别保存 Trace、Agent/工具/回答 Span、模型 Token 用量和检索快照；
  所有查询按用户隔离。
- 模型统计只包含供应商、模型、阶段、输入 Token、输出 Token、总 Token、耗时和
  状态，不建立价格表，也不计算费用。
- 检索快照保存工具、查询、命中数、耗时、最高分和引用证据，便于复盘回答来源。
- 仪表盘增加 14 天 Token 趋势、工具调用分布、Agent 成功率、平均耗时和 Trace
  详情抽屉。
- `eval/` 提供版本化 JSONL 数据集与 Recall@K、MRR、引用命中率、引用编号合法性
  等确定性评测。
- GitHub Actions 自动运行 Ruff、单元测试、前端构建、Alembic 漂移检查、
  PostgreSQL 集成测试、Celery/Redis 往返和 Compose 配置检查。

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
docker compose up -d postgres elasticsearch neo4j redis
cd api
uv run alembic upgrade head
cd ..
docker compose up -d worker beat
```

也可以在宿主机直接启动任务进程：

```bash
cd api
uv run celery -A app.worker.celery_app worker -l INFO \
  -Q ingestion,memory,maintenance --concurrency=2
uv run celery -A app.worker.celery_app beat -l INFO
```

健康检查：

```text
GET http://localhost:8000/api/health/live  # 进程存活
GET http://localhost:8000/api/health       # 四类存储就绪状态
```

Avpilot 的 Elasticsearch 使用宿主机端口 `19200`，避免与其他本地项目常用的 `9200` 冲突。

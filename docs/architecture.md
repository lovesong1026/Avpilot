# Avpilot 整体架构设计

## 1. 建设目标

Avpilot 参考 Comet 的产品能力，从零实现一个多用户 AI 知识库与记忆助手。复现强调功能行为和工程能力等价，而不是逐文件模仿参考项目。

首要闭环：

```text
注册登录 → 配置模型 → 创建知识库 → 上传文档 → 异步解析和索引
        → 发起问题 → Agent 检索知识 → 流式回答 → 展示来源引用
```

完整能力分为六个域：

1. 身份、权限与模型配置
2. 多知识库与多模态内容处理
3. RAG 检索、对话与 Agent 工具编排
4. 长期记忆、事件时间线与知识图谱
5. 深度研究、定时任务与消息通知
6. 评测、反馈、Tracing 与成本核算

情绪、音乐、角色群聊等增强能力放在核心闭环稳定以后实现。

## 2. 架构原则

- 依赖方向固定为 `接口层 → 应用层 → 领域层 → 基础设施接口`。
- controller 只处理 HTTP；业务规则放在 service/use case；repository 只处理持久化。
- PostgreSQL 是业务事实源；Elasticsearch 和 Neo4j 均为可重建的派生索引。
- 文档解析、向量化、记忆提取、研究任务等耗时工作全部异步执行。
- LLM、Embedding、Rerank、搜索和文件存储都通过接口适配，不把供应商 SDK 渗透到业务代码。
- 每个检索结果、记忆和研究结论都保留来源链路。
- 先完成纵向可运行闭环，再扩展功能面。

## 3. 系统上下文

```text
                         ┌─────────────────────┐
                         │ React Web           │
                         │ 管理、检索、对话、图谱 │
                         └──────────┬──────────┘
                                    │ HTTP / SSE
                         ┌──────────▼──────────┐
                         │ FastAPI             │
                         │ API + 应用服务       │
                         └───┬────┬────┬───────┘
                             │    │    │
                ┌────────────┘    │    └─────────────┐
                ▼                 ▼                  ▼
         PostgreSQL        Elasticsearch          Neo4j
         业务事实数据       文本/向量检索           记忆图谱
                │
                └────────────┐
                             ▼
                           Redis
                       缓存、事件、Celery
                             │
                  ┌──────────┴──────────┐
                  ▼                     ▼
             Celery Worker         Celery Beat
             后台任务执行           周期任务调度
```

外部依赖包括：OpenAI 兼容模型服务、Embedding/Rerank 服务、联网搜索服务以及本地磁盘或对象存储。

## 4. 仓库结构

```text
Avpilot/
├── api/
│   ├── app/
│   │   ├── api/                 # 路由、请求校验、SSE 端点
│   │   ├── application/         # 用例编排、事务边界
│   │   ├── domain/              # 实体、值对象、领域规则、端口接口
│   │   ├── infrastructure/      # DB、搜索、图谱、LLM、存储适配器
│   │   ├── tasks/               # Celery 任务入口
│   │   ├── shared/              # 配置、异常、日志、安全、请求上下文
│   │   ├── main.py
│   │   └── worker.py
│   ├── migrations/              # Alembic 迁移
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── e2e/
│   ├── pyproject.toml
│   └── Dockerfile
├── web/
│   ├── src/
│   │   ├── app/                 # 路由、全局 Provider、布局
│   │   ├── features/            # 按业务能力组织页面与状态
│   │   ├── entities/            # 前端领域类型与通用展示
│   │   ├── shared/              # API client、组件、hooks、工具
│   │   └── main.tsx
│   ├── package.json
│   └── Dockerfile
├── docker/
│   └── elasticsearch/           # 中文分词插件镜像
├── docs/
│   ├── architecture.md
│   ├── adr/                     # 架构决策记录
│   └── api/                     # 接口及事件契约
├── eval/                        # RAG、问答、Agent 离线评测
├── scripts/                     # 初始化、开发和运维脚本
├── .env.example
└── docker-compose.yml
```

后端不按 `controller/service/repository` 建一个覆盖全项目的大目录，而是在各领域内部保持内聚，防止项目扩大后模块互相穿透。

## 5. 后端领域划分

```text
identity       用户、令牌、权限
model_registry 模型供应商、能力、默认模型、密钥加密
knowledge      知识库、文档、图片、标签、收藏
ingestion      解析、分块、描述、Embedding、索引任务
retrieval      BM25、向量检索、融合、Rerank、语义门控
conversation   会话、消息、反馈、分享
agent          工具注册、工具循环、上下文和流式事件
memory         陈述、实体、关系、事件、召回、审查和巩固
research       规划、检索、提炼、写作、验证和报告
automation     定时任务、重试和通知
observability  Trace、Span、Token 和成本
```

领域之间通过应用服务或明确事件交互。例如 `knowledge` 创建文档后发布 `DocumentUploaded`，由 `ingestion` 消费；不能由 controller 同时直接操作 PostgreSQL、ES 和 Celery。

## 6. 存储职责

### PostgreSQL

保存不可由其他系统推导出的业务事实：

- 用户、刷新令牌、模型配置
- 知识库、文档元数据、标签和收藏
- 会话、消息、反馈和分享快照
- 文档处理任务及状态
- 研究报告、定时任务和通知配置
- Trace、成本和人工修正记录

### Elasticsearch

保存文档块和图片描述的检索副本：

- `tenant_id`、`user_id`、`knowledge_base_id` 权限过滤字段
- 原文、标题、标签、页码和来源定位
- 中文分词字段
- 稠密向量字段
- 索引版本和文档版本

检索采用 BM25 与向量结果融合，可选 Rerank。删除或修改 PostgreSQL 文档后，通过任务同步更新索引。

### Neo4j

保存可追溯记忆图：

```text
Source → Chunk → Statement → Entity
                         └→ Event
```

节点和关系必须包含用户或租户归属。人工确认、修正和删除记录先写 PostgreSQL，再更新图谱。

### Redis

- Celery broker 与结果后端使用独立 DB
- 短期缓存、分布式锁和限流
- SSE 跨进程事件转发
- 幂等键和任务心跳

Redis 不作为长期事实存储。

## 7. 核心数据模型

第一阶段建立：

```text
User
ModelProviderConfig
KnowledgeBase
Document
DocumentChunkRef
IngestionJob
Conversation
Message
Citation
```

第二阶段加入：

```text
Tag / Favorite / ImageAsset
MemorySource / MemoryStatement / MemoryCorrection
Persona / Skill / ToolConfig
```

第三阶段加入：

```text
ResearchReport / ResearchRun
ScheduledTask / NotificationChannel
AgentTrace / AgentSpan / ModelUsage
```

所有用户数据表至少带有 `id`、归属字段、`created_at`、`updated_at`；需要异步同步的数据增加 `version` 和软删除状态。

## 8. 三条关键数据流

### 8.1 文档入库

```text
上传文件
→ API 校验类型、大小和权限
→ 文件存储落盘
→ PostgreSQL 创建 Document 与 IngestionJob
→ 投递 parse 队列
→ 解析文本和页码
→ 父子分块
→ 批量 Embedding
→ 写入 Elasticsearch
→ 更新任务状态
→ 通知前端
```

要求任务幂等，并明确 `pending/running/succeeded/failed/cancelled` 状态。失败需要记录阶段、错误码和可重试性。

### 8.2 Agent 对话

```text
用户消息
→ 保存消息
→ 解析本轮模型、知识库和工具开关
→ 召回最近上下文与相关记忆
→ LLM 选择工具
→ 检索/联网/记忆工具执行
→ 组织带来源的上下文
→ SSE 输出状态、文本、引用和错误事件
→ 保存最终回答及用量
```

SSE 事件采用稳定协议：`start`、`tool_start`、`tool_result`、`delta`、`citation`、`usage`、`done`、`error`。

### 8.3 记忆生成

```text
主动记忆或对话完成
→ 投递 memory 队列
→ 提取陈述、实体、关系和事件
→ 格式与置信度校验
→ 实体归一化和去重
→ 写入 Neo4j
→ 保存来源映射
→ 对话时按相关度、置信度和时间召回
```

记忆必须能追溯到原始消息或文档片段，并支持用户确认、修正和删除。

## 9. 前端框架

前端使用 React、TypeScript、Vite、React Router、Ant Design 和 Zustand。按业务 feature 组织：

```text
features/
├── auth/
├── model-settings/
├── knowledge-bases/
├── documents/
├── chat/
├── memory/
├── graph/
├── research/
├── automation/
└── observability/
```

服务端状态由 API 查询层管理；Zustand 只保存登录信息、当前知识库、对话 UI 状态等客户端状态。SSE 解析集中在一个 client 中，不分散到页面组件。

## 10. API 边界

```text
/api/auth/*
/api/models/*
/api/knowledge-bases/*
/api/documents/*
/api/conversations/*
/api/chat/stream
/api/memories/*
/api/search/*
/api/research/*
/api/tasks/*
/api/traces/*
/api/health
```

统一使用请求 ID、错误码和响应结构。流式接口使用 SSE 专用事件结构，不套普通 JSON 响应壳。

## 11. 异步队列

v0.8 实际队列划分：

```text
ingestion    文档、网页、图片解析、分块、向量化和索引
memory       记忆提取、去重和图谱写入
maintenance  Outbox 补投、中断恢复和社区聚类
```

Beat 只负责产生周期任务，不执行重任务。任务意图先随业务记录写入 PostgreSQL
`task_outbox`，再投递 Redis，消除数据库与消息队列之间的双写丢失窗口。深度研究和
通知队列等对应能力实际出现后再增加，不提前建立空队列。

## 12. 安全与隔离

- 密码使用强哈希；访问令牌短期有效并配合刷新令牌轮换。
- 模型 API Key 使用应用级密钥加密后入库，任何日志不得输出明文。
- PostgreSQL、ES、Neo4j 的每次查询都必须包含用户或租户隔离条件。
- 上传文件检查扩展名、MIME、大小和解析资源上限。
- 网页抓取阻止环回、内网和云元数据地址，防止 SSRF。
- Markdown 渲染进行 HTML 清理；公开分享只读取不可变快照。
- 工具调用采用白名单，并设置轮数、超时和最大输出限制。

## 13. 可观测与评测

每次请求产生 `request_id`，每次 Agent 执行产生 `trace_id`。记录：

- LLM、Embedding、Rerank 和工具调用耗时
- 输入输出 token、模型、供应商、耗时和状态（不进行费用估算）
- 检索候选、融合得分和最终引用
- Celery 排队时间、执行时间和失败阶段

评测从 RAG 核心闭环开始，包括：解析正确性、Recall@K、MRR/nDCG、引用命中率、
回答忠实度和首 Token 延迟。评测集与生产数据分离并版本化。

## 14. 分阶段实施

### Phase 0：工程基座

- 后端、前端、Docker Compose 和环境配置
- PostgreSQL 迁移、Redis、ES、Neo4j 连接
- 日志、异常、请求 ID、健康检查
- CI 中运行 lint、类型检查和测试

验收：一条命令启动依赖，前后端可访问，健康检查能分别报告各依赖状态。

### Phase 1：身份与模型

- 注册、登录、刷新和当前用户
- 模型配置加密、连接测试和默认模型
- OpenAI 兼容 Chat 与 Embedding 适配器

验收：用户可以保存两个模型配置并完成真实连接测试。

### Phase 2：知识库 RAG

- 知识库、PDF/Word/Markdown/TXT 上传
- 异步解析、父子分块和 ES 索引
- BM25、向量、融合、Rerank 和引用定位

验收：上传 PDF 后可检索，并能定位到正确页码和原文。

### Phase 3：对话 Agent

- 会话和消息
- SSE 流式协议
- 知识库、记忆、联网工具抽象
- Function Calling 主路径与有限迭代保护

验收：问题触发知识库检索，回答流式展示且引用可打开。

### Phase 4：记忆系统

- 陈述、实体、关系和事件提取
- Neo4j schema、去重、召回和时间线
- 记忆审查、人工修正和来源追溯

验收：一段个人经历能生成图谱和事件，并在新会话中正确召回。

### Phase 5：产品增强

- 图片理解、标签、收藏、全局搜索
- 角色、技能、MCP 和群聊
- 分享、导出和仪表盘

### Phase 6：研究与自动化

- 多阶段深度研究
- Verifier Loop
- 定时任务、通知和失败恢复

### Phase 7：质量体系

- 全链路 Trace 和成本核算
- 离线评测数据集与回归门禁
- 压测、安全测试和生产部署

## 15. 独立复现约束

- 参考 Comet 的外部行为、功能说明和架构思想，不复制其具体函数实现、提示词、测试数据和文案。
- Avpilot 使用自己的模块命名、领域接口、数据库迁移和测试用例。
- 每实现一个模块，先写输入输出契约和验收测试，再阅读参考项目对应行为补齐差异。
- 在 `docs/adr/` 记录重大选择及其理由，确保代码演进来自 Avpilot 自身设计。

## 16. 当前里程碑

当前已经完成 Phase 0～5 的核心纵向闭环，在 v0.8 补齐可靠任务执行层，并在 v0.9
建立 Trace、Token、RAG 评测和 CI 质量门禁。下一阶段进入深度研究与自动化，但仍按
“可运行、可测试、可演示”的闭环逐项推进。

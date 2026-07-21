# Avpilot 星航仪

你的 AI 知识领航系统。面向 AVP 课题组，沉淀可检索、可引用、可追溯的知识与记忆。

## 文档

- [整体架构设计](docs/architecture.md)

## 当前阶段

项目已完成 v0.2 知识库检索闭环：用户可以创建知识库，上传 PDF、Word、Markdown、TXT 或 HTML 文档，经父子分块和百炼向量化后写入 Elasticsearch，并使用 IK-BM25 + 向量 RRF 混合检索获得带来源定位的结果。

下一条交付主线是把检索能力接入流式智能问答，让回答直接携带可展开的文档引用。

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

# Avpilot（阿维领航）

面向 AVP 课题组的 AI 知识库与记忆助手。

## 文档

- [整体架构设计](docs/architecture.md)

## 当前阶段

项目处于 Phase 0 工程基座阶段。第一条交付主线是：用户配置模型、上传文档、完成索引，并在对话中获得带来源引用的回答。

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

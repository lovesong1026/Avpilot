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
```

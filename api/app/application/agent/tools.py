"""User-scoped knowledge, memory, and web tools used by the chat agent."""

from __future__ import annotations

import uuid
from typing import Any

from app.application.agent.schemas import (
    AgentTool,
    AgentToolContext,
    ToolCitation,
    ToolResult,
)
from app.application.knowledge_search import search_knowledge_bases
from app.application.navigation import _rank_memories
from app.infrastructure.graph.memory_graph import MemoryGraphRepository
from app.infrastructure.llm.bailian import BailianGateway


def build_agent_tools(context: AgentToolContext) -> list[AgentTool]:
    async def knowledge(arguments: dict[str, Any]) -> ToolResult:
        query = _query(arguments)
        top_k = _top_k(arguments)
        hits = await search_knowledge_bases(
            user_id=context.user_id,
            knowledge_base_ids=context.knowledge_base_ids,
            query=query,
            top_k=top_k,
            use_rerank=False,
        )
        citations = [
            ToolCitation(
                source_type="document",
                source_id=str(hit["citation"]["document_id"]),
                chunk_id=hit["chunk_id"],
                title=hit["citation"]["document_title"],
                quote=hit["excerpt"],
                score=hit["score"],
                locator={
                    "file_name": hit["citation"].get("file_name"),
                    "page": hit["citation"].get("page"),
                    "start_char": hit["citation"].get("start_char"),
                    "end_char": hit["citation"].get("end_char"),
                },
            )
            for hit in hits
        ]
        content = "\n\n".join(
            f"{index}. {hit['citation']['document_title']}\n{hit['content']}"
            for index, hit in enumerate(hits, 1)
        )
        return ToolResult(
            tool_name="knowledge_search",
            content=content or "没有找到相关知识库资料。",
            citations=citations,
            metadata={"query": query, "hit_count": len(hits)},
        )

    async def memory(arguments: dict[str, Any]) -> ToolResult:
        query = _query(arguments)
        top_k = _top_k(arguments)
        gateway = BailianGateway()
        try:
            vector = (await gateway.embed([query]))[0]
        finally:
            await gateway.close()
        rows = await MemoryGraphRepository().searchable_statements(str(context.user_id))
        hits = _rank_memories(rows, vector, top_k, 0.25)
        citations = [
            ToolCitation(
                source_type="memory",
                source_id=str(hit["metadata"]["source_id"]),
                chunk_id=hit["target_id"],
                title=hit["title"],
                quote=hit["excerpt"],
                score=hit["score"],
                locator={
                    "statement_type": hit["metadata"].get("statement_type"),
                    "event_time": hit["metadata"].get("event_time"),
                },
            )
            for hit in hits
        ]
        content = "\n".join(f"{index}. {hit['excerpt']}" for index, hit in enumerate(hits, 1))
        return ToolResult(
            tool_name="memory_search",
            content=content or "没有找到相关长期记忆。",
            citations=citations,
            metadata={"query": query, "hit_count": len(hits)},
        )

    async def web(arguments: dict[str, Any]) -> ToolResult:
        query = _query(arguments)
        top_k = _top_k(arguments)
        if not context.allow_web:
            return ToolResult(
                tool_name="web_search",
                content="本轮对话未允许联网搜索。",
                metadata={"query": query, "hit_count": 0, "disabled": True},
            )
        gateway = BailianGateway()
        try:
            rows = await gateway.web_search(query, top_k=top_k)
        finally:
            await gateway.close()
        citations = [
            ToolCitation(
                source_type="web",
                source_id=str(row.get("url") or f"web:{uuid.uuid4()}"),
                title=str(row.get("title") or "网页资料"),
                quote=str(row.get("excerpt") or ""),
                url=str(row.get("url") or "") or None,
                locator={"url": str(row.get("url") or "")},
            )
            for row in rows
        ]
        content = "\n\n".join(
            f"{index}. {citation.title}\n{citation.quote}\n{citation.url or ''}"
            for index, citation in enumerate(citations, 1)
        )
        return ToolResult(
            tool_name="web_search",
            content=content or "联网搜索没有返回可用结果。",
            citations=citations,
            metadata={"query": query, "hit_count": len(citations)},
        )

    common_parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "要检索的完整问题或关键词"},
            "top_k": {
                "type": "integer",
                "description": "最多返回多少条结果，范围 1 到 8",
                "minimum": 1,
                "maximum": 8,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }
    tools = [
        AgentTool(
            name="knowledge_search",
            description="搜索当前用户选中的私人知识库，适合文档、论文和项目资料问题。",
            parameters=common_parameters,
            handler=knowledge,
        ),
        AgentTool(
            name="memory_search",
            description="搜索当前用户的长期记忆，适合偏好、目标、人物关系和历史事件问题。",
            parameters=common_parameters,
            handler=memory,
        ),
    ]
    if context.allow_web:
        tools.append(
            AgentTool(
                name="web_search",
                description="搜索互联网公开资料，适合最新、实时或知识库之外的信息。",
                parameters=common_parameters,
                handler=web,
            )
        )
    return tools


def _query(arguments: dict[str, Any]) -> str:
    query = str(arguments.get("query") or "").strip()
    if not query:
        raise ValueError("工具查询不能为空")
    return query[:2000]


def _top_k(arguments: dict[str, Any]) -> int:
    try:
        value = int(arguments.get("top_k", 5))
    except (TypeError, ValueError):
        value = 5
    return max(1, min(value, 8))

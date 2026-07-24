"""Alibaba Cloud Model Studio adapter using OpenAI-compatible APIs."""

import json
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk, ChatCompletionMessageParam

from app.domain.model_gateway import (
    ModelConfigurationError,
    ModelResponseError,
    RerankResult,
    RerankUnavailableError,
)
from app.shared.config import Settings, get_settings


class BailianGateway:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.dashscope_api_key:
            raise ModelConfigurationError("DASHSCOPE_API_KEY is not configured")
        self.client = AsyncOpenAI(
            api_key=self.settings.dashscope_api_key,
            base_url=self.settings.bailian_base_url,
            timeout=150.0,
            max_retries=2,
        )

    async def close(self) -> None:
        await self.client.close()

    async def chat(
        self,
        messages: Sequence[ChatCompletionMessageParam],
        *,
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> ChatCompletion:
        request: dict[str, Any] = {
            "model": model or self.settings.bailian_chat_model,
            "messages": list(messages),
            "temperature": temperature,
        }
        if tools:
            request["tools"] = tools
            request["tool_choice"] = "auto"
        return await self.client.chat.completions.create(**request)

    async def web_search(self, query: str, *, top_k: int = 5) -> list[dict[str, str]]:
        """Use Bailian's built-in web search and normalize sources for the agent."""
        response = await self.client.chat.completions.create(
            model=self.settings.bailian_chat_model,
            temperature=0.0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是联网检索适配器。基于联网搜索结果，只返回 JSON 对象："
                        '{"results":[{"title":"标题","url":"https://...",'
                        '"excerpt":"与问题直接相关的事实摘要"}]}。'
                        "URL 必须来自真实搜索结果，不得编造；没有可靠来源时 results 返回空数组。"
                    ),
                },
                {"role": "user", "content": f"搜索：{query}\n最多返回 {top_k} 条。"},
            ],
            extra_body={
                "enable_search": True,
                "search_options": {
                    "forced_search": True,
                    "search_strategy": "turbo",
                },
            },
        )
        content = response.choices[0].message.content
        if not content:
            return []
        body = _parse_json_object(content)
        rows = body.get("results")
        if not isinstance(rows, list):
            return []
        output: list[dict[str, str]] = []
        for row in rows[:top_k]:
            if not isinstance(row, dict):
                continue
            url = str(row.get("url") or "").strip()
            title = str(row.get("title") or "").strip()
            excerpt = str(row.get("excerpt") or "").strip()
            if not url.startswith(("http://", "https://")) or not title or not excerpt:
                continue
            output.append({"title": title[:512], "url": url[:2048], "excerpt": excerpt[:4000]})
        return output

    async def stream_chat(
        self,
        messages: Sequence[ChatCompletionMessageParam],
        *,
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> AsyncIterator[ChatCompletionChunk]:
        request: dict[str, Any] = {
            "model": model or self.settings.bailian_chat_model,
            "messages": list(messages),
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            request["tools"] = tools
            request["tool_choice"] = "auto"
        stream = await self.client.chat.completions.create(**request)
        async for chunk in stream:
            yield chunk

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for offset in range(0, len(texts), 10):
            batch = list(texts[offset : offset + 10])
            response = await self.client.embeddings.create(
                model=self.settings.bailian_embedding_model,
                input=batch,
                dimensions=self.settings.bailian_embedding_dimensions,
                encoding_format="float",
            )
            ordered = sorted(response.data, key=lambda item: item.index)
            vectors.extend(item.embedding for item in ordered)
        expected = self.settings.bailian_embedding_dimensions
        if any(len(vector) != expected for vector in vectors):
            raise ModelResponseError(f"Embedding dimension does not match configured {expected}")
        return vectors

    async def describe_image(self, image_url: str) -> dict[str, Any]:
        response = await self.client.chat.completions.create(
            model=self.settings.bailian_vision_model,
            temperature=0.1,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {
                            "type": "text",
                            "text": (
                                "分析图片并只返回 JSON："
                                '{"description":"详细描述","ocr_text":"识别文字",'
                                '"objects":["物体"],"scene":"场景"}。'
                                "没有文字时 ocr_text 为空字符串。"
                            ),
                        },
                    ],
                }
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise ModelResponseError("Vision model returned empty content")
        return _parse_json_object(content)

    async def rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_n: int,
    ) -> list[RerankResult]:
        base_url = self._rerank_base_url()
        if not base_url:
            raise RerankUnavailableError(
                "Configure BAILIAN_WORKSPACE_ID or BAILIAN_RERANK_BASE_URL to enable rerank"
            )
        payload = {
            "model": self.settings.bailian_rerank_model,
            "query": query,
            "documents": list(documents),
            "top_n": min(top_n, len(documents)),
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/reranks",
                headers={"Authorization": f"Bearer {self.settings.dashscope_api_key}"},
                json=payload,
            )
            response.raise_for_status()
        body = response.json()
        results = body.get("results") or body.get("data")
        if not isinstance(results, list):
            raise ModelResponseError("Rerank response contains no result list")
        return [
            RerankResult(
                index=int(item["index"]),
                relevance_score=float(item["relevance_score"]),
            )
            for item in results
        ]

    def _rerank_base_url(self) -> str:
        if self.settings.bailian_rerank_base_url:
            return self.settings.bailian_rerank_base_url
        if self.settings.bailian_workspace_id:
            workspace = self.settings.bailian_workspace_id
            return f"https://{workspace}.cn-beijing.maas.aliyuncs.com/compatible-api/v1"
        return ""


def _parse_json_object(content: str) -> dict[str, Any]:
    normalized = content.strip()
    if normalized.startswith("```"):
        lines = normalized.splitlines()
        normalized = "\n".join(lines[1:-1]).strip()
    try:
        value = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise ModelResponseError("Model did not return valid JSON") from exc
    if not isinstance(value, dict):
        raise ModelResponseError("Model JSON response is not an object")
    return value

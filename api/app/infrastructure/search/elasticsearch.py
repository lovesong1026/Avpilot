"""Async Elasticsearch client lifecycle."""

from elasticsearch import AsyncElasticsearch

from app.shared.config import get_settings

_client: AsyncElasticsearch | None = None


def get_elasticsearch() -> AsyncElasticsearch:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncElasticsearch(
            settings.elasticsearch_url,
            request_timeout=settings.elasticsearch_request_timeout,
        )
    return _client


async def check_elasticsearch() -> None:
    if not await get_elasticsearch().ping():
        raise ConnectionError("Elasticsearch ping returned false")


async def close_elasticsearch() -> None:
    global _client
    if _client is not None:
        await _client.close()
    _client = None

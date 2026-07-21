"""Elasticsearch schema for document children, parents, and image descriptions."""

import logging

from app.infrastructure.search.elasticsearch import get_elasticsearch
from app.shared.config import get_settings

logger = logging.getLogger(__name__)

CHUNK_INDEX = "avpilot_chunks_v1"


def index_definition() -> dict[str, object]:
    return {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "dynamic": "strict",
            "properties": {
                "user_id": {"type": "keyword"},
                "knowledge_base_id": {"type": "keyword"},
                "source_type": {"type": "keyword"},
                "source_id": {"type": "keyword"},
                "source_title": {"type": "keyword"},
                "chunk_id": {"type": "keyword"},
                "chunk_type": {"type": "keyword"},
                "parent_id": {"type": "keyword"},
                "content": {
                    "type": "text",
                    "analyzer": "ik_max_word",
                    "search_analyzer": "ik_smart",
                },
                "vector": {
                    "type": "dense_vector",
                    "dims": get_settings().bailian_embedding_dimensions,
                    "index": True,
                    "similarity": "cosine",
                },
                "tags": {"type": "keyword"},
                "locator": {"type": "object", "enabled": False},
                "created_at": {"type": "date"},
            },
        },
    }


async def ensure_chunk_index() -> None:
    client = get_elasticsearch()
    if not await client.indices.exists(index=CHUNK_INDEX):
        await client.indices.create(index=CHUNK_INDEX, **index_definition())
        logger.info("Created Elasticsearch index %s", CHUNK_INDEX)

"""Deterministic retrieval and citation metrics for versioned RAG datasets."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

_CITATION_PATTERN = re.compile(r"\[(\d+)]")


class RagEvaluationCase(BaseModel):
    id: str
    question: str
    knowledge_base_id: str | None = None
    expected_document_ids: list[str] = Field(default_factory=list)
    expected_document_titles: list[str] = Field(default_factory=list)
    reference_answer: str | None = None


def evaluate_retrieval_case(
    case: RagEvaluationCase, hits: list[dict[str, Any]], top_k: int
) -> dict[str, float | int | str]:
    expected = {
        *(f"id:{value}" for value in case.expected_document_ids),
        *(f"title:{value.casefold()}" for value in case.expected_document_titles),
    }
    retrieved = [_hit_keys(hit) for hit in hits[:top_k]]
    matched = {value for keys in retrieved for value in keys if value in expected}
    first_rank = next(
        (
            index
            for index, keys in enumerate(retrieved, 1)
            if any(value in expected for value in keys)
        ),
        None,
    )
    return {
        "case_id": case.id,
        "recall_at_k": len(matched) / len(expected) if expected else 1.0,
        "reciprocal_rank": 1 / first_rank if first_rank else 0.0,
        "citation_hit": int(bool(matched)),
        "retrieved_count": len(retrieved),
    }


def aggregate_retrieval_metrics(
    rows: list[dict[str, float | int | str]],
) -> dict[str, float | int]:
    if not rows:
        return {
            "cases": 0,
            "recall_at_k": 0.0,
            "mrr": 0.0,
            "citation_hit_rate": 0.0,
        }
    count = len(rows)
    return {
        "cases": count,
        "recall_at_k": round(sum(float(row["recall_at_k"]) for row in rows) / count, 4),
        "mrr": round(sum(float(row["reciprocal_rank"]) for row in rows) / count, 4),
        "citation_hit_rate": round(sum(int(row["citation_hit"]) for row in rows) / count, 4),
    }


def evaluate_answer_citations(answer: str, citation_count: int) -> dict[str, Any]:
    markers = [int(value) for value in _CITATION_PATTERN.findall(answer)]
    invalid = sorted({value for value in markers if value < 1 or value > citation_count})
    return {
        "citation_markers": len(markers),
        "invalid_markers": invalid,
        "citation_validity": (
            (len(markers) - sum(value in invalid for value in markers)) / len(markers)
            if markers
            else 1.0
        ),
        "unsupported_citation": bool(markers and citation_count == 0),
    }


def _hit_keys(hit: dict[str, Any]) -> set[str]:
    citation = hit.get("citation")
    if not isinstance(citation, dict):
        citation = {}
    document_id = citation.get("document_id") or hit.get("document_id")
    title = citation.get("document_title") or hit.get("title")
    output: set[str] = set()
    if document_id:
        output.add(f"id:{document_id}")
    if title:
        output.add(f"title:{str(title).casefold()}")
    return output

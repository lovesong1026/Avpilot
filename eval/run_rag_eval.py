#!/usr/bin/env python3
"""Run a versioned retrieval dataset against a local Avpilot knowledge base."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "api"))

from app.application.knowledge_search import search_knowledge_base  # noqa: E402
from app.evaluation.rag import (  # noqa: E402
    RagEvaluationCase,
    aggregate_retrieval_metrics,
    evaluate_retrieval_case,
)
from app.infrastructure.database.postgres import close_postgres  # noqa: E402
from app.infrastructure.search.elasticsearch import close_elasticsearch  # noqa: E402


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--user-id", type=uuid.UUID, required=True)
    parser.add_argument("--knowledge-base-id", type=uuid.UUID)
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--rerank", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def load_cases(path: Path) -> list[RagEvaluationCase]:
    return [
        RagEvaluationCase.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


async def run(args: argparse.Namespace) -> dict[str, object]:
    rows = []
    try:
        for case in load_cases(args.dataset):
            knowledge_base_id = (
                uuid.UUID(case.knowledge_base_id)
                if case.knowledge_base_id
                else args.knowledge_base_id
            )
            if knowledge_base_id is None:
                raise ValueError(
                    f"案例 {case.id} 未指定 knowledge_base_id，命令行也没有默认值"
                )
            hits = await search_knowledge_base(
                user_id=args.user_id,
                knowledge_base_id=knowledge_base_id,
                query=case.question,
                top_k=args.top_k,
                use_rerank=args.rerank,
            )
            rows.append(evaluate_retrieval_case(case, hits, args.top_k))
    finally:
        await close_elasticsearch()
        await close_postgres()
    return {
        "dataset": str(args.dataset),
        "top_k": args.top_k,
        "use_rerank": args.rerank,
        "metrics": aggregate_retrieval_metrics(rows),
        "cases": rows,
    }


def main() -> None:
    args = arguments()
    report = asyncio.run(run(args))
    output = json.dumps(report, ensure_ascii=False, indent=2)
    print(output)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

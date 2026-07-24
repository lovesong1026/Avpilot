from app.evaluation.rag import (
    RagEvaluationCase,
    aggregate_retrieval_metrics,
    evaluate_answer_citations,
    evaluate_retrieval_case,
)


def test_retrieval_metrics_measure_recall_and_first_relevant_rank() -> None:
    case = RagEvaluationCase(
        id="case-1",
        question="代号是什么",
        expected_document_ids=["doc-2"],
    )
    row = evaluate_retrieval_case(
        case,
        [
            {"citation": {"document_id": "doc-1", "document_title": "其他"}},
            {"citation": {"document_id": "doc-2", "document_title": "项目记录"}},
        ],
        top_k=5,
    )

    assert row["recall_at_k"] == 1.0
    assert row["reciprocal_rank"] == 0.5
    assert aggregate_retrieval_metrics([row])["mrr"] == 0.5


def test_answer_citation_check_detects_missing_and_out_of_range_sources() -> None:
    valid = evaluate_answer_citations("事实一 [1]，事实二 [2]。", citation_count=2)
    invalid = evaluate_answer_citations("没有资料但声称 [1]。", citation_count=0)

    assert valid["citation_validity"] == 1.0
    assert invalid["invalid_markers"] == [1]
    assert invalid["unsupported_citation"] is True

from app.application.knowledge_search import reciprocal_rank_fusion


def test_reciprocal_rank_fusion_rewards_cross_channel_hits() -> None:
    scores = reciprocal_rank_fusion([["vector-only", "both"], ["both", "bm25-only"]])

    assert scores["both"] > scores["vector-only"]
    assert scores["both"] > scores["bm25-only"]


def test_reciprocal_rank_fusion_handles_empty_rankings() -> None:
    assert reciprocal_rank_fusion([[], []]) == {}

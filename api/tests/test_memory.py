from app.application.memory import (
    _clean_statement,
    _dedupe_entities,
    _match_statement,
    _normalize,
    _split_fragments,
    _statement_key,
)


def test_normalize_unifies_user_self_mentions():
    assert _normalize(" 我 ") == "用户本人"
    assert _normalize("用户本人") == "用户本人"


def test_clean_statement_rejects_low_confidence_and_normalizes_type():
    assert (
        _clean_statement(
            {
                "text": "用户喜欢航天",
                "subject": "用户",
                "predicate": "喜欢",
                "object": "航天",
                "confidence": 0.2,
            }
        )
        is None
    )
    item = _clean_statement(
        {
            "text": "用户喜欢航天",
            "subject": "用户",
            "predicate": "喜欢",
            "object": "航天",
            "statement_type": "unknown",
            "confidence": 0.9,
        }
    )
    assert item is not None
    assert item["statement_type"] == "profile"


def test_split_fragments_keeps_all_text():
    text = "第一段" * 100 + "\n\n" + "第二段" * 100
    fragments = _split_fragments(text, size=300)
    assert fragments == ["第一段" * 100, "第二段" * 100]


def test_entity_dedupe_reuses_exact_graph_entity():
    vector = [1.0, 0.0]
    entities, ids, reused = _dedupe_entities(
        "user-1",
        [{"name": "用户本人", "entity_type": "person"}],
        [vector],
        [
            {
                "id": "existing",
                "name": "用户本人",
                "normalized_name": "用户本人",
                "entity_type": "person",
                "aliases": ["我"],
                "embedding": vector,
            }
        ],
        "2026-01-01T00:00:00Z",
    )
    assert reused == 1
    assert ids[("用户本人", "person")] == "existing"
    assert entities[0]["id"] == "existing"
    assert set(entities[0]["aliases"]) == {"我", "用户本人"}


def test_statement_dedupe_requires_same_event_date():
    item = {
        "subject": "用户本人",
        "predicate": "参加",
        "object": "航天大会",
        "statement_type": "event",
        "event_time": "2026-10-01T09:00:00+08:00",
    }
    exact_key = _statement_key(item)
    assert _match_statement(
        item,
        exact_key,
        [1.0, 0.0],
        [{"id": "exact", "normalized_key": exact_key}],
    )["id"] == "exact"
    assert (
        _match_statement(
            item,
            "new-key",
            [1.0, 0.0],
            [
                {
                    "id": "other-date",
                    "normalized_key": "old-key",
                    "statement_type": "event",
                    "event_time": "2026-11-01T09:00:00+08:00",
                    "embedding": [1.0, 0.0],
                }
            ],
        )
        is None
    )

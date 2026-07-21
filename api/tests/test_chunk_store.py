import uuid

from app.application.chunking import chunk_text
from app.application.document_parser import parse_document
from app.infrastructure.search.chunk_store import build_index_actions


def test_build_index_actions_links_children_to_parent_and_citation() -> None:
    parsed = parse_document("notes.txt", "第一句。第二句。".encode())
    parents = chunk_text(
        parsed.text, parent_tokens=20, child_tokens=10, child_overlap_tokens=2
    )
    child_count = sum(len(parent.children) for parent in parents)
    vectors = [[0.1, 0.2] for _ in range(child_count)]

    actions = build_index_actions(
        user_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        title="测试资料",
        file_name="notes.txt",
        parsed=parsed,
        parents=parents,
        child_vectors=vectors,
    )
    parent = next(action for action in actions if action["_source"]["chunk_type"] == "parent")
    child = next(action for action in actions if action["_source"]["chunk_type"] == "child")

    assert child["_source"]["parent_id"] == parent["_id"]
    assert child["_source"]["locator"]["file_name"] == "notes.txt"
    assert child["_source"]["vector"] == [0.1, 0.2]
    assert "vector" not in parent["_source"]

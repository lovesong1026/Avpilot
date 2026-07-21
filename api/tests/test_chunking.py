"""Parent-child chunking invariants."""

import pytest

from app.application.chunking import chunk_text


def test_chunk_text_preserves_parent_offsets_and_child_links() -> None:
    text = "第一句介绍系统。第二句介绍检索。第三句介绍记忆。第四句介绍图谱。"

    parents = chunk_text(text, parent_tokens=24, child_tokens=12, child_overlap_tokens=3)

    assert parents
    for parent in parents:
        assert text[parent.start_char : parent.end_char] == parent.text
        assert parent.children
        for child in parent.children:
            assert parent.start_char <= child.start_char < child.end_char <= parent.end_char


def test_chunk_text_rejects_invalid_limits() -> None:
    with pytest.raises(ValueError):
        chunk_text("内容", parent_tokens=100, child_tokens=100)


def test_chunk_text_returns_empty_for_whitespace() -> None:
    assert chunk_text("  \n ") == []

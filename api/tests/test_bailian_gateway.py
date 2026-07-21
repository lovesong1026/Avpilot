"""Unit tests for provider response normalization."""

import pytest

from app.domain.model_gateway import ModelResponseError
from app.infrastructure.llm.bailian import _parse_json_object


def test_parse_json_object_accepts_markdown_fence() -> None:
    result = _parse_json_object('```json\n{"scene":"实验室"}\n```')

    assert result == {"scene": "实验室"}


def test_parse_json_object_rejects_non_object() -> None:
    with pytest.raises(ModelResponseError):
        _parse_json_object("[]")

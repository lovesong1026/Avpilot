import io
import uuid

import pytest
from PIL import Image

from app.application.image_processing import (
    InvalidImageError,
    build_searchable_image_text,
    normalize_vision_result,
    prepare_image_for_vision,
)
from app.infrastructure.search.chunk_store import build_image_action


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), "navy").save(buffer, format="PNG")
    return buffer.getvalue()


def test_prepare_image_for_vision_returns_bounded_data_url() -> None:
    result = prepare_image_for_vision(_png_bytes())

    assert result.startswith("data:image/jpeg;base64,")


def test_prepare_image_for_vision_rejects_non_image() -> None:
    with pytest.raises(InvalidImageError):
        prepare_image_for_vision(b"not an image")


def test_normalize_vision_result_builds_searchable_text() -> None:
    info = normalize_vision_result(
        {
            "description": "一架飞机停在跑道上",
            "ocr_text": "AVP-01",
            "objects": ["飞机", "跑道", "飞机", ""],
            "scene": "机场",
        }
    )

    assert info["objects"] == ["飞机", "跑道"]
    searchable = build_searchable_image_text(info)
    assert "AVP-01" in searchable
    assert "场景：机场" in searchable


def test_build_image_action_is_user_scoped_and_searchable() -> None:
    user_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    image_id = uuid.uuid4()

    action = build_image_action(
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
        image_id=image_id,
        file_name="plane.png",
        content="一架飞机",
        vector=[0.1, 0.2],
    )

    assert action["_source"]["user_id"] == str(user_id)
    assert action["_source"]["source_type"] == "image"
    assert action["_source"]["chunk_type"] == "image"
    assert action["_source"]["vector"] == [0.1, 0.2]

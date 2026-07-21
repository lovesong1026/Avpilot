"""Image validation, compression, and multimodal response normalization."""

import base64
import io
from typing import Any

from PIL import Image, UnidentifiedImageError

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
SUPPORTED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/bmp",
}
IMAGE_MIME_BY_EXTENSION = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}
MAX_IMAGE_PIXELS = 40_000_000
VISION_MAX_EDGE = 1568
VISION_TARGET_BYTES = 3 * 1024 * 1024


class InvalidImageError(ValueError):
    """The uploaded payload is not a safe, supported image."""


def prepare_image_for_vision(content: bytes) -> str:
    """Validate and encode an image as a bounded JPEG data URL for the vision model."""
    try:
        with Image.open(io.BytesIO(content)) as probe:
            width, height = probe.size
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                raise InvalidImageError("图片像素尺寸过大")
            probe.verify()
        with Image.open(io.BytesIO(content)) as source:
            source.seek(0)
            image = source.convert("RGBA")
            background = Image.new("RGB", image.size, "white")
            background.paste(image, mask=image.getchannel("A"))
            background.thumbnail((VISION_MAX_EDGE, VISION_MAX_EDGE), Image.Resampling.LANCZOS)
            encoded = _encode_jpeg(background)
    except InvalidImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise InvalidImageError("文件不是有效图片或图片已经损坏") from exc
    return f"data:image/jpeg;base64,{base64.b64encode(encoded).decode('ascii')}"


def _encode_jpeg(image: Image.Image) -> bytes:
    encoded = b""
    for quality in (88, 76, 64, 52):
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality, optimize=True)
        encoded = buffer.getvalue()
        if len(encoded) <= VISION_TARGET_BYTES:
            break
    return encoded


def normalize_vision_result(value: dict[str, Any]) -> dict[str, Any]:
    objects = value.get("objects")
    normalized_objects = []
    if isinstance(objects, list):
        normalized_objects = list(
            dict.fromkeys(str(item).strip()[:64] for item in objects if str(item).strip())
        )[:30]
    return {
        "description": str(value.get("description") or "").strip()[:4000],
        "ocr_text": str(value.get("ocr_text") or "").strip()[:4000],
        "objects": normalized_objects,
        "scene": str(value.get("scene") or "").strip()[:256],
    }


def build_searchable_image_text(info: dict[str, Any]) -> str:
    parts = [
        info.get("description"),
        f"图片文字：{info['ocr_text']}" if info.get("ocr_text") else None,
        f"主要物体：{'、'.join(info['objects'])}" if info.get("objects") else None,
        f"场景：{info['scene']}" if info.get("scene") else None,
    ]
    return "\n".join(str(part) for part in parts if part).strip()

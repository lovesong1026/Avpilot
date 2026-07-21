"""Local, user-scoped asset storage for documents and images."""

import asyncio
import uuid
from pathlib import Path

from app.shared.config import get_settings


class LocalDocumentStorage:
    def __init__(self, root: str | Path | None = None) -> None:
        configured = root or get_settings().storage_path
        self.root = Path(configured).expanduser().resolve()

    def build_key(self, user_id: uuid.UUID, document_id: uuid.UUID, extension: str) -> str:
        safe_extension = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
        return f"documents/{user_id}/{document_id}{safe_extension}"

    def build_image_key(self, user_id: uuid.UUID, image_id: uuid.UUID, extension: str) -> str:
        safe_extension = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
        return f"images/{user_id}/{image_id}{safe_extension}"

    async def save(self, key: str, content: bytes) -> None:
        path = self._resolve(key)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, content)

    async def read(self, key: str) -> bytes:
        return await asyncio.to_thread(self._resolve(key).read_bytes)

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.exists():
            await asyncio.to_thread(path.unlink)

    def _resolve(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("Invalid storage key")
        return path

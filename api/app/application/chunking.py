"""Sentence-aware parent-child chunking for Chinese and English text."""

import re
from dataclasses import dataclass

import tiktoken

from app.domain.chunking import ChildChunk, ParentChunk

_BOUNDARY = re.compile(r"(?<=[。！？!?；;\.])\s*|\n+")
_ENCODER = tiktoken.get_encoding("cl100k_base")


@dataclass(frozen=True, slots=True)
class _Segment:
    text: str
    start: int
    end: int
    tokens: int


def count_tokens(text: str) -> int:
    return len(_ENCODER.encode(text))


def chunk_text(
    text: str,
    *,
    parent_tokens: int = 1024,
    child_tokens: int = 256,
    child_overlap_tokens: int = 32,
) -> list[ParentChunk]:
    if parent_tokens <= child_tokens:
        raise ValueError("parent_tokens must be larger than child_tokens")
    if not 0 <= child_overlap_tokens < child_tokens:
        raise ValueError("child_overlap_tokens must be between 0 and child_tokens")
    segments = _segments(text)
    parents = _pack(segments, parent_tokens)
    result: list[ParentChunk] = []
    for parent_index, parent_parts in enumerate(parents):
        children = _children(parent_parts, child_tokens, child_overlap_tokens)
        parent_text = text[parent_parts[0].start : parent_parts[-1].end]
        result.append(
            ParentChunk(
                index=parent_index,
                text=parent_text,
                token_count=count_tokens(parent_text),
                start_char=parent_parts[0].start,
                end_char=parent_parts[-1].end,
                children=tuple(children),
            )
        )
    return result


def _segments(text: str) -> list[_Segment]:
    stripped = text.strip()
    if not stripped:
        return []
    left_trim = len(text) - len(text.lstrip())
    segments: list[_Segment] = []
    cursor = left_trim
    for match in _BOUNDARY.finditer(stripped):
        boundary_end = left_trim + match.end()
        _append_segment(segments, text, cursor, boundary_end)
        cursor = boundary_end
    _append_segment(segments, text, cursor, left_trim + len(stripped))
    return segments


def _append_segment(segments: list[_Segment], source: str, start: int, end: int) -> None:
    while start < end and source[start].isspace():
        start += 1
    while end > start and source[end - 1].isspace():
        end -= 1
    if start < end:
        value = source[start:end]
        segments.append(_Segment(value, start, end, count_tokens(value)))


def _pack(segments: list[_Segment], limit: int) -> list[list[_Segment]]:
    groups: list[list[_Segment]] = []
    current: list[_Segment] = []
    current_tokens = 0
    for segment in segments:
        if current and current_tokens + segment.tokens > limit:
            groups.append(current)
            current = []
            current_tokens = 0
        current.append(segment)
        current_tokens += segment.tokens
    if current:
        groups.append(current)
    return groups


def _children(segments: list[_Segment], limit: int, overlap_tokens: int) -> list[ChildChunk]:
    children: list[ChildChunk] = []
    start_index = 0
    while start_index < len(segments):
        end_index = start_index
        total = 0
        while end_index < len(segments):
            candidate = segments[end_index]
            if total and total + candidate.tokens > limit:
                break
            total += candidate.tokens
            end_index += 1
            if total >= limit:
                break
        selected = segments[start_index:end_index]
        joined = " ".join(item.text for item in selected)
        children.append(
            ChildChunk(
                index=len(children),
                text=joined,
                token_count=count_tokens(joined),
                start_char=selected[0].start,
                end_char=selected[-1].end,
            )
        )
        if end_index >= len(segments):
            break
        retained = 0
        next_start = end_index
        while next_start > start_index and retained < overlap_tokens:
            next_start -= 1
            retained += segments[next_start].tokens
        start_index = max(start_index + 1, next_start)
    return children

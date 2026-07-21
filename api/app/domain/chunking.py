"""Parent-child text chunks with stable source offsets."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChildChunk:
    index: int
    text: str
    token_count: int
    start_char: int
    end_char: int


@dataclass(frozen=True, slots=True)
class ParentChunk:
    index: int
    text: str
    token_count: int
    start_char: int
    end_char: int
    children: tuple[ChildChunk, ...]

"""Provider-neutral values used by document parsing and citation mapping."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceSection:
    text: str
    start_char: int
    end_char: int
    page: int | None = None


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    text: str
    sections: tuple[SourceSection, ...]

    def page_for_offset(self, offset: int) -> int | None:
        for section in self.sections:
            if section.start_char <= offset < section.end_char:
                return section.page
        return self.sections[-1].page if self.sections else None

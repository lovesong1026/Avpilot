from app.application.auto_tagging import parse_tag_names


def test_parse_tag_names_reuses_existing_spelling_and_deduplicates() -> None:
    result = parse_tag_names('[" 技术 ", "技术", "航空航天"]', ["技术"])

    assert result == ["技术", "航空航天"]


def test_parse_tag_names_rejects_non_array_response() -> None:
    assert parse_tag_names('{"tag":"技术"}') == []

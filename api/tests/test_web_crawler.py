import asyncio

import pytest

from app.application.web_crawler import UnsafeWebUrlError, ensure_public_url, extract_web_text


def test_extract_web_text_removes_navigation_and_scripts() -> None:
    title, text = extract_web_text(
        """
        <html><head><title>星航实验</title><script>secret()</script></head>
        <body><nav>导航</nav><main><h1>猎户座实验</h1>
        <p>这是一段用于验证网页正文抽取的完整内容，包含足够多的有效文字，
        还包括实验目标、处理流程、检索方法和最终验收结论。</p></main></body></html>
        """,
        "fallback",
    )

    assert title == "星航实验"
    assert "猎户座实验" in text
    assert "secret" not in text
    assert "导航" not in text


def test_ensure_public_url_rejects_loopback() -> None:
    with pytest.raises(UnsafeWebUrlError):
        asyncio.run(ensure_public_url("http://127.0.0.1/internal"))

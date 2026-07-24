import asyncio
import uuid
from types import SimpleNamespace

from app.application.research import (
    _add_usage,
    _evidence_text,
    _follow_up_queries,
    _json_object,
    _plan_questions,
    _sanitize_report_citations,
    _write_report,
)


def test_research_plan_and_verifier_payloads_are_bounded() -> None:
    plan = _json_object(
        """```json
{"questions":["背景是什么？","有哪些路线？","风险是什么？"],"deliverables":["报告"]}
```"""
    )
    assert _plan_questions(plan, "fallback") == [
        "背景是什么？",
        "有哪些路线？",
        "风险是什么？",
    ]
    assert _follow_up_queries({"follow_up_queries": ["补充政策证据", "", "补充成本数据"]}) == [
        "补充政策证据",
        "补充成本数据",
    ]


def test_research_evidence_prompt_is_numbered_and_truncated() -> None:
    rows = [
        SimpleNamespace(title=f"来源 {index}", quote="证据" * 1000, url=None) for index in range(45)
    ]
    payload = _evidence_text(rows)  # type: ignore[arg-type]
    assert "[1] 来源 0" in payload
    assert "[40] 来源 39" in payload
    assert "来源 40" not in payload
    assert len(payload) < 60_000


def test_research_usage_only_accumulates_tokens() -> None:
    task = SimpleNamespace(
        id=uuid.uuid4(),
        input_tokens=3,
        output_tokens=2,
        total_tokens=5,
    )
    _add_usage(
        task,  # type: ignore[arg-type]
        {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14},
    )
    assert (task.input_tokens, task.output_tokens, task.total_tokens) == (13, 6, 19)


def test_report_citations_must_resolve_to_real_evidence() -> None:
    report = "有效结论 [1]，越界结论 [3]，也不能使用 [0]。"
    assert _sanitize_report_citations(report, 2) == (
        "有效结论 [1]，越界结论 （证据不足），也不能使用 （证据不足）。"
    )


def test_report_without_evidence_is_deterministic_and_has_no_citation() -> None:
    report, usage = asyncio.run(
        _write_report(
            None,  # type: ignore[arg-type]
            "测试报告",
            "测试课题",
            [],
            {"gaps": ["缺少政策资料"]},
        )
    )
    assert "不会生成任何占位引用" in report
    assert "[1]" not in report
    assert "缺少政策资料" in report
    assert usage["total_tokens"] == 0

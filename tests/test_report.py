"""报告层三律：零判定（AST 守门）、零外链、确定性。

``plan/03`` §4.1。第三律的配套细节：真实数据里合法带 URL 的单元格要**放行**
（转义冒号让判据字面成立），而不是让渲染层 `raise` —— 后者会崩在合法数据上。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from errcode_atlas import contract, report


REPORT_SRC = Path(__file__).resolve().parents[1] / "src" / "errcode_atlas" / "report.py"


# ── 律一：零判定（AST 守门）───────────────────────────────────────────────
def _report_tree() -> ast.Module:
    return ast.parse(REPORT_SRC.read_text(encoding="utf-8"))


def test_report_has_no_verdict_branching() -> None:
    """`report.py` 里不许出现 `if <x> == <某个判定态/归因字面量>` 形态的分派。

    判据用 AST 定位"比较运算的任一操作数是 contract 的判定态常量"，
    不断言"文本里出现次数"——注释里提到也会被数进去（那是假红）。
    """
    metric_names = {
        contract.UNAMBIGUOUS,
        contract.AMBIGUOUS_SAME_PLATFORM,
        contract.AMBIGUOUS_CROSS_PLATFORM,
        contract.PLATFORM_ABSENT,
        contract.UNKNOWN,
        contract.SIGNAL_KILLED,
        contract.NORMAL_EXIT,
        contract.SYSEXITS,
        contract.UNATTRIBUTABLE,
    }
    offenders: list[str] = []
    for node in ast.walk(_report_tree()):
        if not isinstance(node, ast.Compare):
            continue
        operands = [node.left, *node.comparators]
        for operand in operands:
            if isinstance(operand, ast.Constant) and operand.value in metric_names:
                offenders.append(f"line {operand.lineno}: {operand.value}")
    assert not offenders, f"report.py 出现了判定态字面量比较（应是零判定）：{offenders}"


def test_report_does_not_import_judgement_modules() -> None:
    """零判定的另一半：呈现层不许 import 判定层（否则它迟早会自己判一次）。"""
    imported: set[str] = set()
    for node in ast.walk(_report_tree()):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    forbidden = {"errcode_atlas.explain", "errcode_atlas.exitcode", "errcode_atlas.catalog"}
    assert not (imported & forbidden), f"report.py 不该 import 判定层：{imported & forbidden}"


# ── 律二：零外链 ───────────────────────────────────────────────────────────
def test_table_cells_escape_url_colons():
    """真实数据可能带 URL（如某个来源的 url 字段）——转义冒号让"零外链"字面成立，
    同时**放行合法数据**（不是 raise）。"""
    rendered = report.render_table(("k",), [("https://example.invalid/x",)])
    assert "://" not in rendered
    assert "example.invalid" in rendered


def test_explanation_rendering_has_no_live_url():
    payload = {
        "verdict": contract.UNAMBIGUOUS,
        "query": {"text": "98", "platform": "linux", "domain": "errno"},
        "candidates": [{"name": "EADDRINUSE", "value": 98, "source_label": "include/x.h:12",
                        "strength": "hard", "platform": "linux", "domain": "errno"}],
        "sources": ["https://example.invalid/doc#anchor"],
    }
    rendered = report.render_explanation(payload)
    assert "://" not in rendered


def test_attribution_rendering_has_no_live_url():
    payload = {
        "attribution": contract.SIGNAL_KILLED,
        "code": 137,
        "platform": "linux",
        "signal": 9,
        "signal_name": "SIGKILL",
        "sources": ["https://example.invalid/x"],
        "notes": ["128+n 归因是 POSIX 惯例非标准（即惯例而非标准）"],
    }
    assert "://" not in report.render_attribution(payload)


# ── 律三：确定性 ───────────────────────────────────────────────────────────
def test_rendering_is_byte_identical_across_runs():
    payload = {
        "verdict": contract.AMBIGUOUS_SAME_PLATFORM,
        "query": {"text": "6", "platform": "linux", "domain": "signal"},
        "candidates": [
            {"name": "SIGABRT", "value": 6, "platform": "linux", "domain": "signal",
             "strength": "hard", "source_label": "include/uapi/asm-generic/signal.h:90"},
            {"name": "SIGIOT", "value": 6, "platform": "linux", "domain": "signal",
             "strength": "hard", "source_label": "include/uapi/asm-generic/signal.h:91"},
        ],
        "per_platform": {"linux": ["SIGABRT", "SIGIOT"]},
        "distinguish": "同值别名",
        "notes": ["x"],
        "sources": ["a:1", "b:2"],
    }
    assert report.render_explanation(payload) == report.render_explanation(payload)
    assert report.to_json(payload) == report.to_json(payload)


def test_json_output_is_key_sorted():
    payload = {"b": 1, "a": 2}
    assert report.to_json(payload).index('"a"') < report.to_json(payload).index('"b"')


def test_empty_table_still_renders_header_and_rule():
    rendered = report.render_table(("x", "y"), [])
    assert rendered.count("\n") == 1  # 表头 + 分隔行


# ── 语义标签表覆盖 ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("verdict", contract.VERDICTS)
def test_every_verdict_has_a_label(verdict: str) -> None:
    assert report.VERDICT_LABELS.get(verdict)


@pytest.mark.parametrize("attribution", contract.ATTRIBUTIONS)
def test_every_attribution_has_a_label(attribution: str) -> None:
    assert report.ATTRIBUTION_LABELS.get(attribution)


def test_sysexits_label_mentions_convention():
    label = report.ATTRIBUTION_LABELS[contract.SYSEXITS]
    assert "约定" in label
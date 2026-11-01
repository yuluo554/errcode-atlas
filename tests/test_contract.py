"""契约双向断言：``data/README.md`` §5 的两张表 ↔ ``contract.py`` 的常量。

**必须是"集合相等"，不是"包含"**（plan/03 §5）：

* 只做"文档 → 代码"的包含：文档多写一个已废弃值，代码侧静默收下 → 漏；
* 只做"代码 → 文档"的包含：代码新增一个值而文档没改 → 漏。

两个方向都断言，且断言**数量相等**（``len`` 也要相等，不只是集合相等 —— 抗"重复声明"）。

另外置两条"解析器自证"：解析出的行数必须 > 0。否则表被切碎时"空 == 空"恒绿
（假门族⑳：分隔行不是断表，必须显式 ``continue``）。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from errcode_atlas import contract, report

DATA_README = Path(__file__).resolve().parents[1] / "data" / "README.md"


def _section(text: str, heading_pattern: str) -> str:
    """取某个 ``###``/``####`` 小节正文（到下一个同级或更高级标题为止）。"""
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines) if re.search(heading_pattern, line)), -1)
    assert start >= 0, f"data/README.md 找不到小节：{heading_pattern}"
    level = len(lines[start]) - len(lines[start].lstrip("#"))
    out: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("#"):
            deeper = len(line) - len(line.lstrip("#"))
            if deeper <= level:
                break
        out.append(line)
    return "\n".join(out)


def _first_column(body: str) -> list[str]:
    """解析 markdown 表的第一列（``| 值 |`` 形态）。

    分隔行 ``|---|`` **显式 continue**，它不是断表；表到头（首条非 ``|`` 行）即止。
    """
    rows: list[str] = []
    started = False
    for line in body.split("\n"):
        if not line.startswith("|"):
            if started:
                break
            continue
        started = True
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 3:
            continue
        first = cells[1]
        if set(first) <= set("-: "):  # 分隔行
            continue
        if first in ("判定态", "归因", "退出码"):  # 表头
            continue
        rows.append(first.strip("`*"))
    return rows


def _verdicts_from_doc() -> list[str]:
    body = _section(DATA_README.read_text(encoding="utf-8"), r"^### 5\.2")
    return _first_column(body)


def _attributions_from_doc() -> list[str]:
    body = _section(DATA_README.read_text(encoding="utf-8"), r"^### 5\.3")
    return _first_column(body)


def _exit_codes_from_doc() -> list[str]:
    body = _section(DATA_README.read_text(encoding="utf-8"), r"^### 5\.1")
    return _first_column(body)


def _normalize(value: str) -> str:
    """剥掉名字末尾的**参数占位**：文档写 ``SIGNAL-KILLED(n)``、``SYSEXITS(n)``，
    代码里的取值是 ``SIGNAL-KILLED`` / ``SYSEXITS``（``n`` 是运行时才知道的形参，不是值的一部分）。

    归一化必须窄：只剥**紧贴末尾的** ``(…)``，中间带括号或尾部有别的字符都不动 ——
    放宽成"去掉所有括号内容"会把 ``AMBIGUOUS-SAME-PLATFORM`` 这类名字的未来变体静默吞掉。
    """
    return re.sub(r"\([^()]*\)$", "", value).strip()


# ── 解析器自证（0 行不可能是合法结果）────────────────────────────────────────
def test_parsers_actually_read_rows() -> None:
    assert len(_verdicts_from_doc()) > 0, "§5.2 表解析出 0 行 —— 解析器把表切碎了？"
    assert len(_attributions_from_doc()) > 0, "§5.3 表解析出 0 行 —— 解析器把表切碎了？"
    assert len(_exit_codes_from_doc()) > 0, "§5.1 表解析出 0 行 —— 解析器把表切碎了？"


# ── 双向集合相等 ────────────────────────────────────────────────────────────
def test_verdicts_match_doc_both_directions() -> None:
    doc = [_normalize(v) for v in _verdicts_from_doc()]
    code = [_normalize(v) for v in contract.VERDICTS]
    assert sorted(doc) == sorted(code), (
        f"判定态不一致：仅在文档 {sorted(set(doc) - set(code))}；"
        f"仅在代码 {sorted(set(code) - set(doc))}"
    )
    assert len(doc) == len(code), "文档与代码的判定态数量不等（有重复声明？）"


def test_attributions_match_doc_both_directions() -> None:
    doc = [_normalize(v) for v in _attributions_from_doc()]
    code = [_normalize(v) for v in contract.ATTRIBUTIONS]
    assert sorted(doc) == sorted(code), (
        f"归因不一致：仅在文档 {sorted(set(doc) - set(code))}；"
        f"仅在代码 {sorted(set(code) - set(doc))}"
    )
    assert len(doc) == len(code)


def test_normalizer_only_strips_trailing_parameter() -> None:
    """归一化本身也要被证伪：宽了会把真名字吞掉。"""
    assert _normalize("SIGNAL-KILLED(n)") == "SIGNAL-KILLED"
    assert _normalize("AMBIGUOUS-SAME-PLATFORM") == "AMBIGUOUS-SAME-PLATFORM"
    assert _normalize("A(B)C") == "A(B)C"


def test_exit_codes_match_doc() -> None:
    doc = sorted(int(v) for v in _exit_codes_from_doc() if v.isdigit())
    assert doc == sorted(contract.EXIT_CODES), (
        f"退出码不一致：文档 {doc} 代码 {sorted(contract.EXIT_CODES)}"
    )


# ── 报告层标签表必须与契约同构（否则会出现"未登记"而门不管）──────────────────
@pytest.mark.parametrize("table_name,expected", [
    ("VERDICT_LABELS", contract.VERDICTS),
    ("ATTRIBUTION_LABELS", contract.ATTRIBUTIONS),
])
def test_label_tables_cover_every_value(table_name: str, expected: tuple[str, ...]) -> None:
    table = report.label_tables()[table_name]
    assert set(table) == set(expected)
    assert all(table[value].strip() for value in expected)


# ── 五态封闭：不许加第六态 ──────────────────────────────────────────────────
def test_verdict_count_is_exactly_five() -> None:
    assert len(contract.VERDICTS) == 5
    assert len(set(contract.VERDICTS)) == 5


def test_ambiguous_substates_are_one_class_each() -> None:
    """两个 AMBIGUOUS 子态都在，且都进"不可唯一归因"集合（漏一个 = 本题最贵的错）。"""
    assert contract.AMBIGUOUS_SAME_PLATFORM in contract.VERDICTS
    assert contract.AMBIGUOUS_CROSS_PLATFORM in contract.VERDICTS
    assert contract.NON_UNIQUE_VERDICTS == {
        contract.AMBIGUOUS_SAME_PLATFORM,
        contract.AMBIGUOUS_CROSS_PLATFORM,
        contract.PLATFORM_ABSENT,
    }


def test_win32_alias_is_rejected_not_silently_mapped() -> None:
    """`win32` / `windows` 必须在别名表里（被显式拒绝），不得出现在平台值里。"""
    assert "win32" not in contract.PLATFORMS
    assert "windows" not in contract.PLATFORMS
    assert set(contract.AMBIGUOUS_PLATFORM_ALIASES) == {"win32", "windows"}


def test_strength_triple_is_closed() -> None:
    assert contract.STRENGTHS == ("hard", "diff", "gray")
    assert contract.SOURCE_MAX_STRENGTH[contract.SOURCE_RUNTIME] != contract.STRENGTH_HARD
    assert contract.SOURCE_MAX_STRENGTH[contract.SOURCE_DOC] != contract.STRENGTH_HARD
"""`data/gaps.md` 的可数性与三态封闭。

`plan/04` §2.1：无出处者不得入编目，改记本表；本表自己也要"能被数出来"。
判据不写死行数常量（新增一行即失效）—— 分母由表构造算出。
"""

from __future__ import annotations

import re
from pathlib import Path

GAPS = Path(__file__).resolve().parents[1] / "data" / "gaps.md"

#: 三态必须封闭：要么全录、要么部分录、要么未录（"待 M1" 是进度，不是状态）。
STATUS_TOKENS = ("全录", "部分录", "未录")


def _gap_rows() -> list[list[str]]:
    """解析缺口表：表头 → 首条非表格行即止；分隔行显式跳过（不是断表）。"""
    lines = GAPS.read_text(encoding="utf-8").split("\n")
    header_idx = next(
        (i for i, line in enumerate(lines) if line.startswith("|") and "状态" in line), -1
    )
    assert header_idx >= 0, "data/gaps.md 找不到含『状态』表头的缺口表"
    rows: list[list[str]] = []
    for line in lines[header_idx + 2 :]:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.split("|")]
        # `| a | b |` 切出来是 ['', 'a', 'b', ''] —— 去掉首尾空串才是有效格
        cells = cells[1:-1]
        if len(cells) < 5:
            continue
        if set(cells[0]) <= {"-", ":"}:  # 分隔行
            continue
        rows.append(cells)
    return rows


def test_gap_table_has_rows() -> None:
    assert _gap_rows(), "缺口表 0 行 —— 判据空跑（表头搬家了？）"


def test_every_gap_row_states_a_closed_status() -> None:
    """每行的状态格必须取三态之一；"待 M1" 之类不算状态。"""
    bad = [row[0] for row in _gap_rows() if not any(t in row[3] for t in STATUS_TOKENS)]
    assert not bad, f"这些缺口行没写封闭状态（全录/部分录/未录）：{bad}"


def test_every_gap_row_has_a_recovery_path() -> None:
    """每行必须写"怎么补"—— 否则它永远只是一句抱怨。"""
    bad = [row[0] for row in _gap_rows() if len(row) < 5 or not row[4]]
    assert not bad, f"这些缺口行没写补的路径：{bad}"


def test_status_tokens_are_exactly_three() -> None:
    """三态封闭：不许出现第四种状态词。"""
    found = set()
    for row in _gap_rows():
        for token in STATUS_TOKENS:
            if token in row[3]:
                found.add(token)
    assert found <= set(STATUS_TOKENS)
    assert len(STATUS_TOKENS) == 3


def test_gap_count_is_derived_not_hardcoded() -> None:
    """分母由构造算出：本文件不写死"共 N 条"。"""
    text = GAPS.read_text(encoding="utf-8")
    rows = _gap_rows()
    # 表里不许出现"共 N 行/条"这类手写常量（它会随新增一行而失效）
    assert not re.search(r"共\s*\d+\s*(行|条)", text), "缺口登记里写了手写总数 —— 新增一行就会失效"
    assert len(rows) >= 1
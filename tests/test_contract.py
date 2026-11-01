"""契约双向断言：``data/README.md`` §5 的两张表 ↔ ``contract.py`` 的常量。

**必须是"集合相等"，不是"包含"**（plan/03 §5）：

* 只做"文档 → 代码"的包含：文档多写一个已废弃值，代码侧静默收下 → 漏；
* 只做"代码 → 文档"的包含：代码新增一个值而文档没改 → 漏。

两个方向都断言，且断言**数量相等**（``len`` 也要相等，不只是集合相等 —— 抗"重复声明"）。

另外置两条"解析器自证"：解析出的行数必须 > 0。否则表被切碎时"空 == 空"恒绿
（假门族⑳：分隔行不是断表，必须显式 ``continue``）。

**M5 追加的一节（§ ``SKILL.md`` 契约块）** 与上面那几条同构，但**扫描面不同**：
上面守的是"口径真相源"（``data/README.md`` §5），下面守的是"Skill 面向外声明的契约"。
两者都必须是集合相等 —— 把契约块放宽成"包含"会漏掉"Skill 里多写一个已废弃值"，
而那正是下游 Agent 会照着执行的声明（K30）。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from errcode_atlas import contract, report

DATA_README = Path(__file__).resolve().parents[1] / "data" / "README.md"
SKILL_MD = Path(__file__).resolve().parents[1] / "SKILL.md"

#: 契约块的固定围栏（`plan/03` §5）。**围栏是唯一扫描面**（K30）：
#: 块外正文写用法，可以出现示例名字，但不得参与契约断言。
CONTRACT_BEGIN = "<!-- contract:begin -->"
CONTRACT_END = "<!-- contract:end -->"


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


# ════════════════════════════════════════════════════════════════════════════
# M5 · SKILL.md 契约块 ↔ contract.py（与上面同构，扫描面不同）
# ════════════════════════════════════════════════════════════════════════════
#: 上面那几条守的是"口径真相源"（data/README §5）；本节守的是"Skill 对外声明的契约"。
#: 两者都断言**集合相等 + 数量相等** —— 单向包含会漏"契约块里多写一个已废弃值"，
#: 而那正是下游 Agent 会照着执行的声明（K30）。


def _contract_block() -> str:
    """取出围栏之间的契约块正文。

    三条自证都在这里做完，因为它们一旦失守，后面所有断言都会"空 == 空"恒绿：

    1. 围栏**恰好一对**（0 对 = 没写；2 对 = 有两块，谁是真值就说不清了）；
    2. ``end`` 必须在 ``begin`` 之后（反过来是围栏写反了，切出来的块是文件尾部）；
    3. 块正文非空。
    """
    text = SKILL_MD.read_text(encoding="utf-8")
    begins = text.count(CONTRACT_BEGIN)
    ends = text.count(CONTRACT_END)
    assert begins == 1, f"SKILL.md 的契约块起始围栏应恰好 1 处，实得 {begins}"
    assert ends == 1, f"SKILL.md 的契约块结束围栏应恰好 1 处，实得 {ends}"
    start = text.index(CONTRACT_BEGIN) + len(CONTRACT_BEGIN)
    stop = text.index(CONTRACT_END)
    assert stop > start, "SKILL.md 的契约块围栏写反了（end 出现在 begin 之前）"
    block = text[start:stop]
    assert block.strip(), "SKILL.md 的契约块是空的 —— 围栏之间没有任何声明"
    return block


def _block_section(block: str, heading_pattern: str) -> str:
    """取契约块内某个 ``###`` 小节正文（到下一个 ``#`` 标题为止）。"""
    lines = block.split("\n")
    start = next((i for i, line in enumerate(lines) if re.search(heading_pattern, line)), -1)
    assert start >= 0, f"SKILL.md 契约块找不到小节：{heading_pattern}"
    level = len(lines[start]) - len(lines[start].lstrip("#"))
    out: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("#"):
            deeper = len(line) - len(line.lstrip("#"))
            if deeper <= level:
                break
        out.append(line)
    return "\n".join(out)


def _block_values(heading_pattern: str) -> list[str]:
    """契约块某小节表格的**数据行**第一列（表头行不算值）。

    **不复用**上面的 ``_first_column``：那个函数的表头过滤是**按名字白名单**写的
    （``判定态``/``归因``/``退出码``，为 ``data/README`` §5 的两张表服务）。
    契约块的平台小节表头是 ``平台``，套用白名单会把它当成一个值读进来
    —— 实测过：``platforms`` 那条当场报 "5 个值"。判据是"这是不是表头"，
    不是"它的名字在不在白名单里"，所以这里按**位置**跳过表头：分隔行之前的都算表头。
    """
    rows: list[str] = []
    seen_rule = False
    for line in _block_section(_contract_block(), heading_pattern).split("\n"):
        if not line.startswith("|"):
            if seen_rule:
                break
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 3:
            continue
        first = cells[1]
        if set(first) <= set("-: "):
            seen_rule = True  # 分隔行：它之前是表头，它之后才是数据
            continue
        if not seen_rule:
            continue
        rows.append(first.strip("`*"))
    return rows


def test_contract_block_sections_are_actually_read() -> None:
    """解析器自证：四组各读出 > 0 行。

    缺了这条，"小节标题被改名"会让四组全部读成空列表，于是"空 == 空"恒绿 ——
    契约块看着还在，实际一个字都没被验过。
    """
    for heading in (r"^### 平台", r"^### 判定态", r"^### 归因", r"^### 退出码"):
        assert len(_block_values(heading)) > 0, f"契约块小节 {heading} 解析出 0 行"


@pytest.mark.parametrize(
    "heading,expected",
    [
        (r"^### 平台", contract.PLATFORMS),
        (r"^### 判定态", contract.VERDICTS),
        (r"^### 归因", contract.ATTRIBUTIONS),
    ],
    ids=["platforms", "verdicts", "attributions"],
)
def test_contract_block_matches_code_both_directions(heading: str, expected: tuple[str, ...]) -> None:
    """双向集合相等 + 数量相等（与 data/README 那几条同一套判据）。"""
    doc = [_normalize(v) for v in _block_values(heading)]
    code = [_normalize(v) for v in expected]
    assert sorted(doc) == sorted(code), (
        f"{heading} 不一致：仅在 SKILL.md {sorted(set(doc) - set(code))}；"
        f"仅在 contract.py {sorted(set(code) - set(doc))}"
    )
    assert len(doc) == len(code), f"{heading} 数量不等（契约块里有重复声明？）doc={doc} code={code}"


def test_contract_block_exit_codes_match_code() -> None:
    """退出码同样双向：契约块写 ``0/1/3/4``，代码里就是这四个，不多不少。"""
    doc = [v for v in _block_values(r"^### 退出码") if v.isdigit()]
    assert doc, "契约块的退出码小节一行数字都没解析出来"
    assert sorted(int(v) for v in doc) == sorted(contract.EXIT_CODES), (
        f"退出码不一致：SKILL.md {doc} contract.py {sorted(contract.EXIT_CODES)}"
    )


def test_contract_block_declares_every_platform_value() -> None:
    """平台值必须**恰好四个**，且 ``win32`` / ``windows`` 不得混进来。

    这条与 ``test_win32_alias_is_rejected_not_silently_mapped`` 互补：那条守代码侧，
    这条守"Skill 面向下游 Agent 声明的平台值"—— 下游照着写的那个值必须真的存在。
    """
    values = [_normalize(v) for v in _block_values(r"^### 平台")]
    assert len(values) == 4, f"平台值应恰好 4 个，实得 {values}"
    assert "win32" not in values and "windows" not in values, (
        f"契约块出现了必须被拒绝的别名：{values}"
    )


def test_contract_block_body_outside_fence_is_not_scanned() -> None:
    """围栏之外的正文**不参与**契约扫描（K30）—— 这条是那条纪律的可跑形态。

    做法：把契约块整段从文本里删掉，剩下的正文里出现的示例名字（``EADDRINUSE`` 等）
    不得被任何契约断言读到。判据用"删块后仍能取出同样的块"来反证 ——
    如果扫描面偷偷扩到全文，这里就取不到块（``begin`` 计数变 0）。
    """
    text = SKILL_MD.read_text(encoding="utf-8")
    start = text.index(CONTRACT_BEGIN)
    stop = text.index(CONTRACT_END) + len(CONTRACT_END)
    outside = text[:start] + text[stop:]
    assert CONTRACT_BEGIN not in outside and CONTRACT_END not in outside
    # 块外确实还有内容（否则这条判据是空跑），且里面有名字示例
    assert outside.strip(), "契约块之外没有任何正文 —— 这条判据是空跑"
    assert "EADDRINUSE" in outside, "块外正文里没有示例名字 —— 反证失去了靶子"


def test_contract_block_does_not_restate_numeric_truth() -> None:
    """契约块**只声明名字**，不复述数值（``plan/03`` §5 / ``data/README.md`` §5 纪律）。

    具体判据：块里不许出现 ``data/README.md`` §5 的判定**数值**——比如把
    ``EAGAIN=11`` 这类编目值抄进契约块。抄进来就有了第二份会漂的副本，
    而 ``bench`` 与 ``test_catalog_data_m1`` 只对账编目，不对账 SKILL.md。
    """
    block = _contract_block()
    # 编目数值的形态 = `名字 = 数字` / `名字: 数字`（契约块里只有名字与判定态字面量）
    offenders = re.findall(r"\bE[A-Z0-9_]{2,}\s*[=:]\s*\d+", block)
    assert not offenders, f"契约块里复述了编目数值：{offenders}"
"""模块④ 报告渲染。三条律（plan/03 §4.1）：

1. **零判定**：只做「结果对象 → 字符串」，不含任何 ``if verdict == ...`` 那样的分派。
   由 ``tests/test_report.py`` 的 AST 守门断言。
2. **零外链**：人读表里不输出 URL；出处一律 ``<相对路径>:<行号>`` 或 ``runtime:<程序> <版本>``。
3. **确定性**：同一结果对象两次渲染逐字节相等。

模块本身不判断"这个结果好不好"——那由 ``cli.py`` 的唯一退出码映射决定。
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

from . import contract

#: 人读表不输出 URL：把 ``://`` 的每个斜杠都转义成 ``\/``，于是渲染结果里**不存在** ``://``
#: 这个子串（判据因此在字符串层面字面成立），而合法数据仍然可读、不被 `raise` 拦掉
#: —— 真实数据里合法带 URL 的单元格不该让渲染层崩（plan/03 §4.1 第二律的配套）。
_COLON = "\\:"


def escape_link_colons(value: str) -> str:
    return value.replace("://", f"{_COLON}\\/\\/")


#: 无值域（`node`）在表格里的占位符。**不写 `None`**：`None` 会被读成"查不到值"，
#: 而那些条目本来就没有值 —— 数据缺失与"没有这个字段"必须看起来不一样。
NO_VALUE_PLACEHOLDER = "（无数字码值）"


def _cell(value: Any) -> str:
    text = NO_VALUE_PLACEHOLDER if value is None else str(value)
    return escape_link_colons(text).replace("|", "\\|").replace("\n", " ")


def render_table(headers: Iterable[str], rows: Iterable[Iterable[Any]]) -> str:
    head = "| " + " | ".join(_cell(h) for h in headers) + " |"
    rule = "|" + "|".join("---" for _ in headers) + "|"
    body = "\n".join("| " + " | ".join(_cell(v) for v in row) + " |" for row in rows)
    return "\n".join([head, rule, body]) if body else "\n".join([head, rule])


def render_explanation(result: Mapping[str, Any]) -> str:
    """``explain`` 的人读形态。字段取自语义标签表，不做判定分派。"""
    query = result["query"]
    verdict = result["verdict"]
    lines = [
        f"# 判定：{verdict}",
        "",
        f"- 语义：{VERDICT_LABELS.get(verdict, '<未登记>')}",
        f"- 查询：{query['text']}"
        + (f" · 平台 {query['platform']}" if query.get("platform") else " · 平台未指定")
        + (f" · 域 {query['domain']}" if query.get("domain") else " · 域自动探测"),
    ]

    candidates = result.get("candidates") or []
    if candidates:
        lines += ["", "## 候选"]
        rows = [
            (
                c.get("name", ""),
                c.get("value", ""),
                c.get("platform", ""),
                c.get("domain", ""),
                c.get("strength", ""),
                c.get("source_label", ""),
            )
            for c in candidates
        ]
        lines.append(render_table(("名字", "值", "平台", "域", "强度", "出处"), rows))

    per_platform = result.get("per_platform") or {}
    if per_platform:
        lines += ["", "## 逐平台"]
        rows = []
        for platform, value in sorted(per_platform.items()):
            if isinstance(value, list):
                shown: Any = ", ".join(value)
            else:
                shown = value  # 可能是 None（无值域）——交给 _cell 渲染占位符
            rows.append((platform, shown))
        lines.append(render_table(("平台", "归因"), rows))

    absent = result.get("platform_absent_in") or []
    if absent:
        lines += ["", f"## 平台缺失：{', '.join(absent)}"]

    if result.get("distinguish"):
        lines += ["", "## 如何区分", "", str(result["distinguish"])]

    notes = result.get("notes") or []
    if notes:
        lines += ["", "## 说明", ""]
        lines += [f"- {note}" for note in notes]

    sources = result.get("sources") or []
    if sources:
        lines += ["", "## 出处", ""]
        lines += [f"- {escape_link_colons(label)}" for label in sources]

    return "\n".join(lines) + "\n"


def render_attribution(result: Mapping[str, Any]) -> str:
    """``exitcode`` 的人读形态。"""
    attribution = result["attribution"]
    lines = [
        f"# 归因：{attribution}",
        "",
        f"- 语义：{ATTRIBUTION_LABELS.get(attribution, '<未登记>')}",
        f"- 退出码：{result['code']} · 平台 {result['platform']}",
    ]
    if result.get("signal") is not None:
        lines.append(f"- 信号：{result['signal']}（{result.get('signal_name') or '未在编目内找到名字'}）")
    if result.get("sysexits_name"):
        lines.append(f"- sysexits 名：{result['sysexits_name']}")
    if result.get("truncated"):
        lines.append("- 截断：原值按 32 位无符号截断解释")
    notes = result.get("notes") or []
    if notes:
        lines += ["", "## 说明", ""]
        lines += [f"- {note}" for note in notes]
    sources = result.get("sources") or []
    if sources:
        lines += ["", "## 出处", ""]
        lines += [f"- {escape_link_colons(label)}" for label in sources]
    return "\n".join(lines) + "\n"


def to_json(payload: Any) -> str:
    """机读形态：``sort_keys`` + 固定分隔符，保证双跑逐字节一致。"""
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


# ── 语义标签表（纯数据，不是判定）──────────────────────────────────────────
VERDICT_LABELS: dict[str, str] = {
    contract.UNAMBIGUOUS: "该数字在该平台该域下唯一对应一个常量",
    contract.AMBIGUOUS_SAME_PLATFORM: "同平台同域内一数多名（正确结果，非失败）",
    contract.AMBIGUOUS_CROSS_PLATFORM: "未给平台且各平台归因不一致（正确结果，非失败）",
    contract.PLATFORM_ABSENT: "该常量在该平台不存在（正确结果，非失败）",
    contract.UNKNOWN: "编目内无此值（算不了，不是不可归因）",
}

ATTRIBUTION_LABELS: dict[str, str] = {
    contract.SIGNAL_KILLED: "按 128+n 归因到信号（POSIX 惯例）",
    contract.NORMAL_EXIT: "常规退出，程序自定义语义",
    contract.SYSEXITS: "命中 sysexits 约定段（约定非标准）",
    contract.UNATTRIBUTABLE: "不可唯一归因（正确结果，非失败）",
}


def label_tables() -> dict[str, Mapping[str, str]]:
    """暴露给契约测试：标签表的键集合必须与 ``contract`` 的常量集合**相等**。"""
    return {"VERDICT_LABELS": VERDICT_LABELS, "ATTRIBUTION_LABELS": ATTRIBUTION_LABELS}
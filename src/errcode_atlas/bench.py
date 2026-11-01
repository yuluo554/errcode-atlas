"""基准：跑 ``fixtures/*/expected.json``，逐 case 比对**结果对象**（不是渲染文本）。

设计纪律（plan/03 §6、plan/06 R8）：

* 真值由**人手写并对照原文**，绝不从本实现产出回填 —— 否则 bench 恒绿。
* 退出码也进真值：``expected.json`` 里 ``exit_code`` 是**真值**而非运行时读到的值，
  两边都声明才算"两次跑真发生了"。
* 缺件三态分开报：``无 fixtures`` / ``case 缺 expected.json`` / ``INPUT.md 缺失``，
  三句话各不同 —— 否则"0 分"与"没扫到"同形。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import contract
from .catalog import Catalog
from .exitcode import attribute
from .explain import Query, explain

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"


def _fixture_dirs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir())


def run_bench(catalog: Catalog, root: Path | None = None, emit=print) -> int:
    root = root or FIXTURES_DIR
    cases = _fixture_dirs(root)

    if not cases:
        emit(
            f"bench: fixtures 目录 {root.name}/ 下 0 个 case —— "
            "这可能是「尚未植入语料」而不是「全部通过」"
        )
        return contract.EXIT_UNDECIDABLE

    failures: list[str] = []
    scanned = 0
    for case in cases:
        expected_path = case / "expected.json"
        input_path = case / "INPUT.md"
        if not input_path.is_file():
            failures.append(f"{case.name}: 缺 INPUT.md")
            continue
        if not expected_path.is_file():
            failures.append(f"{case.name}: 缺 expected.json")
            continue
        scanned += 1
        try:
            expected = json.loads(expected_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"{case.name}: expected.json 不是合法 JSON（{exc}）")
            continue
        failures += _check_case(case.name, expected, catalog)

    _report(emit, scanned, failures)
    if scanned == 0:
        # **"有 case 但一个也没跑成"不许报全绿**：那不是"通过"，是"没有证据"。
        # 与 `cases == 0`（目录都没有）同码，但与"跑过且全过"必须可分。
        return contract.EXIT_UNDECIDABLE
    return contract.EXIT_OK if not failures else contract.EXIT_NON_UNIQUE


def _normalized_per_platform(value: Any) -> dict[str, Any]:
    """``per_platform`` 的比对形态：列表收成 ``tuple``（顺序只由实现给，真值只声明集合），
    其余（标量 / ``None``）原样 —— `None` 是**无值域的合法取值**，不能被当成"空"消掉。"""
    normalized: dict[str, Any] = {}
    for platform, hit in (value or {}).items():
        normalized[platform] = tuple(sorted(hit)) if isinstance(hit, list) else hit
    return dict(sorted(normalized.items()))


def _check_case(name: str, expected: dict[str, Any], catalog: Catalog) -> list[str]:
    problems: list[str] = []
    query_spec = expected.get("input", {})
    kind = query_spec.get("kind")
    if kind == "explain":
        query = Query.parse(
            str(query_spec["query"]), query_spec.get("platform"), query_spec.get("domain")
        )
        actual = explain(query, catalog).as_dict()
        for key in ("verdict",):
            if expected.get(key) != actual[key]:
                problems.append(f"{name}: verdict 期望 {expected.get(key)!r} 实得 {actual[key]!r}")
        if "exit_code" in expected:
            got = contract.exit_code_for_verdict(actual["verdict"])
            if expected["exit_code"] != got:
                problems.append(f"{name}: exit_code 期望 {expected['exit_code']} 实得 {got}")
        if "candidate_names" in expected:
            got_names = sorted(c.get("name", "") for c in actual["candidates"])
            want = sorted(expected["candidate_names"])
            if got_names != want:
                problems.append(f"{name}: candidate_names 期望 {want} 实得 {got_names}")
        if "platform_absent_in" in expected:
            got_absent = sorted(actual["platform_absent_in"])
            want_absent = sorted(expected["platform_absent_in"])
            if got_absent != want_absent:
                problems.append(
                    f"{name}: platform_absent_in 期望 {want_absent} 实得 {got_absent}"
                )
        # 跨平台 case 的核心证据是**逐平台归因**：只断言 verdict 的话，
        # "linux 是 X、macos 是 Y" 这件事没有任何断言在看（M3 补）。
        if "per_platform" in expected:
            got = _normalized_per_platform(actual["per_platform"])
            want = _normalized_per_platform(expected["per_platform"])
            if got != want:
                problems.append(f"{name}: per_platform 期望 {want} 实得 {got}")
        # `gray` 强制字样（"惯例非标准"/"约定非标准"）必须真出现在 notes 里 ——
        # 这不是靠人记得写，而是 bench 断言它存在（plan/04 §2.3）。
        if expected.get("require_note_markers"):
            joined = " ".join(actual.get("notes") or [])
            for marker in expected["require_note_markers"]:
                if marker not in joined:
                    problems.append(f"{name}: 说明里缺强制字样 {marker!r}")
    elif kind == "exitcode":
        result = attribute(int(query_spec["code"]), str(query_spec["platform"]), catalog)
        actual = result.as_dict()
        for key in ("attribution", "signal", "signal_name"):
            if key in expected and expected[key] != actual[key]:
                problems.append(f"{name}: {key} 期望 {expected[key]!r} 实得 {actual[key]!r}")
        if "exit_code" in expected and expected["exit_code"] != result.exit_code:
            problems.append(
                f"{name}: exit_code 期望 {expected['exit_code']} 实得 {result.exit_code}"
            )
        if expected.get("require_note_markers"):
            joined = " ".join(actual["notes"])
            for marker in expected["require_note_markers"]:
                if marker not in joined:
                    problems.append(f"{name}: 说明里缺强制字样 {marker!r}")
    else:
        problems.append(f"{name}: input.kind={kind!r} 不支持（只认 explain / exitcode）")
    return problems


def _report(emit, scanned: int, failures: list[str]) -> None:
    for line in failures:
        emit(f"FAIL  {line}")
    emit(f"bench: 扫了 {scanned} 个 case，{len(failures)} 项不符")
    if scanned == 0:
        emit("bench: 0 个 case 通过判定 —— 这是空跑，不是全绿")
"""内置自测：不变量而不是"再跑一遍判定"。

每条失败返回一行说明；全过返回空列表。``cli.py selftest`` 与 ``tests/test_selftest.py``
都真调它（零调用点 = 空转，见 AGENTS.md「变异验证」）。
"""

from __future__ import annotations

from typing import Any

from . import contract, report
from .catalog import Catalog
from .exitcode import attribute
from .explain import Query, explain


def run_selftest(catalog: Catalog) -> list[str]:
    failures: list[str] = []
    failures += _check_determinism(catalog)
    failures += _check_exit_codes(catalog)
    failures += _check_exit_one(catalog)
    failures += _check_signal_validity(catalog)
    failures += _check_gray_markers(catalog)
    return failures


def _check_determinism(catalog: Catalog) -> list[str]:
    """同一输入两次调用，结果对象与渲染都必须逐字节相同。"""
    out: list[str] = []
    for text in ("98", "6", "EAGAIN", "SIGSTKFLT"):
        first = explain(Query.parse(text, None, None), catalog).as_dict()
        second = explain(Query.parse(text, None, None), catalog).as_dict()
        if report.to_json(first) != report.to_json(second):
            out.append(f"determinism: explain({text!r}) 两次结果不同")
        if report.render_explanation(first) != report.render_explanation(second):
            out.append(f"determinism: explain({text!r}) 两次渲染不同")
    return out


def _check_exit_codes(catalog: Catalog) -> list[str]:
    """退出码映射必须与契约一致：不可归因 → 1，算不了 → 3。

    **期望值写规范的字面量（0/1/3/4），不写 ``contract.EXIT_*`` 常量** ——
    用常量写期望值就是自我参照：把常量本身改错时，"实测"与"期望"一起错，判据恒绿。
    本项目实测过这一条（注入 ``EXIT_NON_UNIQUE = 0`` → 自测仍报全绿）。
    判别 = **"我这条断言的期望值，和被测对象读的是同一个变量吗？"**
    """
    out: list[str] = []
    mapping = {verdict: contract.exit_code_for_verdict(verdict) for verdict in contract.VERDICTS}
    expected = {
        contract.UNAMBIGUOUS: 0,
        contract.AMBIGUOUS_SAME_PLATFORM: 1,
        contract.AMBIGUOUS_CROSS_PLATFORM: 1,
        contract.PLATFORM_ABSENT: 1,
        contract.UNKNOWN: 3,
    }
    if mapping != expected:
        out.append(f"exit_codes: 判定态映射与 data/README.md §5.1 不一致: {mapping}")

    attribution_expected = {
        contract.SIGNAL_KILLED: 0,
        contract.NORMAL_EXIT: 0,
        contract.SYSEXITS: 0,
        contract.UNATTRIBUTABLE: 1,
    }
    actual = {name: contract.exit_code_for_attribution(name) for name in contract.ATTRIBUTIONS}
    if actual != attribution_expected:
        out.append(f"exit_codes: 归因映射不一致: {actual}")
    if contract.EXIT_NON_UNIQUE == contract.EXIT_UNDECIDABLE:
        out.append("exit_codes: 「不可归因」与「算不了」必须是两个退出码")
    if sorted(contract.EXIT_CODES) != [0, 1, 3, 4]:
        out.append(f"exit_codes: 退出码集合应为 0/1/3/4，实得 {sorted(contract.EXIT_CODES)}")
    return out


def _check_exit_one(catalog: Catalog) -> list[str]:
    """``exit 1`` 必须是 UNATTRIBUTABLE（plan/01 §二 模块③ 硬纪律）。"""
    out: list[str] = []
    for platform in catalog.platforms() or contract.PLATFORMS:
        result = attribute(1, platform, catalog)
        if result.attribution != contract.UNATTRIBUTABLE:
            out.append(f"exit_one: {platform} 的 exit 1 判成了 {result.attribution}")
        # 期望值写字面量 1，不写 EXIT_NON_UNIQUE（防自我参照，见 _check_exit_codes）
        if result.exit_code != 1:
            out.append(f"exit_one: {platform} 的 exit 1 退出码 {result.exit_code}（期望 1）")
    return out


def _check_signal_validity(catalog: Catalog) -> list[str]:
    """``128+n`` 的 ``n`` 必须在编目里确实存在；否则必须判 UNATTRIBUTABLE。"""
    out: list[str] = []
    # n=110 在任何平台都不是有效信号（大于 NSIG 的常规上界），用来验"无效 n 必须不成立"
    probe = 128 + 110
    for platform in contract.PLATFORMS:
        signals = catalog.signal_numbers(platform)
        result = attribute(probe, platform, catalog)
        if 110 in signals:
            continue
        if result.attribution == contract.SIGNAL_KILLED:
            out.append(
                f"signal_validity: {platform} 上 n=110 不在编目信号表内，却判成了 SIGNAL-KILLED"
            )
    return out


def _check_gray_markers(catalog: Catalog) -> list[str]:
    """``gray`` 强度条目必须带强制字样（plan/04 §2.3）——不靠人记得写。"""
    out: list[str] = []
    result = attribute(137, "linux", catalog)
    joined = " ".join(result.notes)
    if result.attribution == contract.SIGNAL_KILLED and not any(
        marker in joined for marker in contract.GRAY_MARKERS
    ):
        out.append("gray_markers: SIGNAL-KILLED 的说明里缺「惯例非标准」字样")
    syse = attribute(64, "linux", catalog)
    if syse.attribution == contract.SYSEXITS and not any(
        marker in " ".join(syse.notes) for marker in contract.GRAY_MARKERS
    ):
        out.append("gray_markers: SYSEXITS 的说明里缺「约定非标准」字样")
    return out


def describe() -> dict[str, Any]:
    """给 `bench`/报告用的自测清单描述（数量由构造算出，不写死）。"""
    return {
        "checks": [
            _check_determinism,
            _check_exit_codes,
            _check_exit_one,
            _check_signal_validity,
            _check_gray_markers,
        ]
    }
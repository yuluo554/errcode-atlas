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
    failures += _check_verdict_reachability(catalog)
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


def _check_verdict_reachability(catalog: Catalog) -> list[str]:
    """**五态可达性**（M3）：用真编目把五种 verdict 各真跑出来一次。

    为什么这是不变量而不是"再跑一遍判定"：五判定态是本项目的招牌口径
    （``plan/01`` §四 40 分维度）。任一态在真编目上**跑不出来**，说明编目或判定
    已经退化成"只能答一种情况"—— 那时 ``bench`` 也只会一片绿，因为它比对的是
    fixture 自己的期望。这条断言的是**可达性**本身：五态缺一即 FAIL。

    探针从编目事实里现挑（不是写死 ``6``/``98`` 之类的数值）—— 写死会让编目
    正常演进（例如某别名被上游移除）把自测变成假红。期望值写字面量
    ``"UNAMBIGUOUS"`` / ``0`` 等，**不写 ``contract.*`` 常量**（K26：用常量写期望
    就是自我参照，改错常量时实测与期望一起错）。
    """
    out: list[str] = []
    found: dict[str, str] = {}  # verdict -> 探针说明

    # 有值域上"一值 N 名"的两个极端：1 名 = 唯一，≥2 名 = 同平台歧义
    single: tuple[str, str, int] | None = None
    multi: tuple[str, str, int] | None = None
    values: dict[tuple[str, str], set[int]] = {}
    for entry in catalog.entries:
        if entry.value is None:
            continue
        values.setdefault((entry.platform, entry.domain), set()).add(entry.value)
    for (platform, domain), numbers in sorted(values.items()):
        for number in sorted(numbers):
            hits = catalog.names_at(platform, domain, number)
            if len(hits) == 1 and single is None:
                single = (platform, domain, number)
            if len(hits) > 1 and multi is None:
                multi = (platform, domain, number)

    # 跨平台分歧：同一数字在各已覆盖平台的命中集合不一致，或某已覆盖平台没有它
    divergent: tuple[str, int] | None = None
    for domain in contract.DOMAINS:
        covered = catalog.covered_platforms(domain)
        if len(covered) < 2:
            continue
        seen: set[int] = set()
        for platform in covered:
            for number in values.get((platform, domain), set()):
                seen.add(number)
        for number in sorted(seen):
            sets = {catalog.names_at(p, domain, number) for p in covered}
            if len(sets) > 1 or () in sets:
                divergent = (domain, number)
                break
        if divergent:
            break

    # 平台缺失：某名字在这个平台没有、在另一个**已覆盖该域**的平台有。
    # 名字表就地建（本模块不是判定层，AST 守门只守 explain.py / exitcode.py）——
    # `platforms_with_name(domain, name)` 是**单名查询**，不能拿来枚举名字。
    absent: tuple[str, str, str] | None = None
    names_by_domain: dict[str, set[str]] = {}
    for entry in catalog.entries:
        names_by_domain.setdefault(entry.domain, set()).add(entry.name)
    for domain in contract.DOMAINS:
        covered = catalog.covered_platforms(domain)
        for platform in covered:
            for name in sorted(names_by_domain.get(domain, ())):
                if catalog.has_name(platform, domain, name):
                    continue
                if any(
                    catalog.has_name(other, domain, name) for other in covered if other != platform
                ):
                    absent = (platform, domain, name)
                    break
            if absent:
                break
        if absent:
            break

    probes: list[tuple[str, str, Query, object]] = []
    if single:
        platform, domain, number = single
        probes.append(("UNAMBIGUOUS", f"{number} --platform {platform} --domain {domain}",
                       Query.parse(str(number), platform, domain), 0))
    if multi:
        platform, domain, number = multi
        probes.append(("AMBIGUOUS-SAME-PLATFORM", f"{number} --platform {platform} --domain {domain}",
                       Query.parse(str(number), platform, domain), 1))
    if divergent:
        domain, number = divergent
        probes.append(("AMBIGUOUS-CROSS-PLATFORM", f"{number} --domain {domain}",
                       Query.parse(str(number), None, domain), 1))
    if absent:
        platform, domain, name = absent
        probes.append(("PLATFORM-ABSENT", f"{name} --platform {platform} --domain {domain}",
                       Query.parse(name, platform, domain), 1))
    # 越界值恒可达：编目里不可能有这么大的 errno/信号号
    unknown_domain = catalog.covered_platforms(contract.DOMAIN_ERRNO)[0] if catalog.covered_platforms(
        contract.DOMAIN_ERRNO
    ) else None
    if unknown_domain:
        probes.append(("UNKNOWN", f"99999 --platform {unknown_domain}",
                       Query.parse("99999", unknown_domain, contract.DOMAIN_ERRNO), 3))

    for verdict, label, query, want_exit in probes:
        result = explain(query, catalog)
        if result.verdict != verdict:
            out.append(
                f"verdict_reachability: {label} 期望 {verdict}，实得 {result.verdict}"
                "（编目或判定只能答一种情况了）"
            )
            continue
        if result.exit_code != int(want_exit):
            out.append(
                f"verdict_reachability: {label} 是 {verdict}，退出码实得 "
                f"{result.exit_code}（期望 {want_exit}）"
            )
            continue
        found[verdict] = label

    # 一个探针都没造出来 = 编目里连"一值一名"或"一值多名"都找不到 —— 那也是漏，且更严重。
    for verdict in contract.VERDICTS:
        if verdict in found:
            continue
        if any(f"期望 {verdict}" in line for line in out):
            continue  # 已报过"跑出来是别的态"，不重复报
        out.append(
            f"verdict_reachability: {verdict} 在真编目上**跑不出来** —— "
            "这不是数据不够，是判定面退化成了只能答一种情况"
        )
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
            _check_verdict_reachability,
        ]
    }
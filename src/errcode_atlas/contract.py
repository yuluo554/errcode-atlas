"""代码侧契约：五判定态 / 四归因 / 四平台 / 三域 / 退出码。

**这是代码侧的唯一定义处**。口径的真相源是 ``data/README.md`` §5，本模块是它的解析结果：
``tests/test_contract.py`` 把 §5 的两张表反向解析成集合，与本模块做**集合相等**的双向断言
（单向包含会漏掉"文档多写了一个已废弃值"）。

三个禁忌：
1. 这里只放**名字与语义标签**，不放任何会漂的编目数值（如 ``EAGAIN=11``）——那些在 catalog 里。
2. 判定层不许 import 呈现层；呈现层不许自己定义判定态字面量，一律从这里取。
3. 退出码映射只在 ``cli.py::_exit_code_for`` 一处，本模块只导出映射表的数据。
"""

from __future__ import annotations

from typing import Final

# ── 平台 ────────────────────────────────────────────────────────────────────
# Windows 拆两个视角：同一台机器上 Node 与 Python 给的 errno 数值不同
# （data/README.md §1.1，实测 EADDRINUSE: Node 100 / Python 10048）。
# 合并成一个 "windows" 在结构上就无法表达这个事实 —— 见 plan/02 D3。
PLATFORMS: Final[tuple[str, ...]] = ("linux", "macos", "win32-node", "win32-python")

#: 用户可能输入但必须被显式拒绝（exit 4）的平台别名 —— 拒绝时提示两个视角。
AMBIGUOUS_PLATFORM_ALIASES: Final[dict[str, str]] = {
    "win32": "Windows 有两个视角：win32-node（Node 运行时）与 win32-python（Python 运行时），数值不同，必须指定其一",
    "windows": "Windows 有两个视角：win32-node（Node 运行时）与 win32-python（Python 运行时），数值不同，必须指定其一",
}

# ── 域 ──────────────────────────────────────────────────────────────────────
DOMAINS: Final[tuple[str, ...]] = ("errno", "signal", "exit")

# ── 五判定态（data/README.md §5.2）─────────────────────────────────────────
UNAMBIGUOUS: Final = "UNAMBIGUOUS"
AMBIGUOUS_SAME_PLATFORM: Final = "AMBIGUOUS-SAME-PLATFORM"
AMBIGUOUS_CROSS_PLATFORM: Final = "AMBIGUOUS-CROSS-PLATFORM"
PLATFORM_ABSENT: Final = "PLATFORM-ABSENT"
UNKNOWN: Final = "UNKNOWN"

VERDICTS: Final[tuple[str, ...]] = (
    UNAMBIGUOUS,
    AMBIGUOUS_SAME_PLATFORM,
    AMBIGUOUS_CROSS_PLATFORM,
    PLATFORM_ABSENT,
    UNKNOWN,
)

#: 「判定完成但不可唯一归因」——这不是失败，是**正确的判定结果**。
NON_UNIQUE_VERDICTS: Final[frozenset[str]] = frozenset(
    {AMBIGUOUS_SAME_PLATFORM, AMBIGUOUS_CROSS_PLATFORM, PLATFORM_ABSENT}
)

#: 「算不了」（编目缺失 -> exit 3），与"有答案但不可归因"（exit 1）是两个语义。
UNDECIDABLE_VERDICTS: Final[frozenset[str]] = frozenset({UNKNOWN})

# ── 四归因（data/README.md §5.3）───────────────────────────────────────────
SIGNAL_KILLED: Final = "SIGNAL-KILLED"
NORMAL_EXIT: Final = "NORMAL-EXIT"
SYSEXITS: Final = "SYSEXITS"
UNATTRIBUTABLE: Final = "UNATTRIBUTABLE"

ATTRIBUTIONS: Final[tuple[str, ...]] = (SIGNAL_KILLED, NORMAL_EXIT, SYSEXITS, UNATTRIBUTABLE)

#: 归因结果里"不可唯一归因"的那一个 —— exit 1 必须落这里。
NON_UNIQUE_ATTRIBUTIONS: Final[frozenset[str]] = frozenset({UNATTRIBUTABLE})

# ── 本工具自身退出码（data/README.md §5.1）─────────────────────────────────
EXIT_OK: Final = 0  # 判定完成，且结果可唯一归因
EXIT_NON_UNIQUE: Final = 1  # 判定完成，但结果不可唯一归因（正确的判定结果，不是失败）
EXIT_UNDECIDABLE: Final = 3  # 算不了：编目缺失 / 域不支持
EXIT_USAGE: Final = 4  # 用法错误

EXIT_CODES: Final[tuple[int, ...]] = (EXIT_OK, EXIT_NON_UNIQUE, EXIT_UNDECIDABLE, EXIT_USAGE)

EXIT_CODE_LABELS: Final[dict[int, str]] = {
    EXIT_OK: "判定完成，结果可唯一归因",
    EXIT_NON_UNIQUE: "判定完成，结果不可唯一归因（AMBIGUOUS / PLATFORM-ABSENT / UNATTRIBUTABLE）",
    EXIT_UNDECIDABLE: "算不了：编目未覆盖此值，或域不支持",
    EXIT_USAGE: "用法错误",
}

# ── 强度（plan/04 §2.2：判定强度三值封闭，不可升级、不可加第四值）─────────────
STRENGTH_HARD: Final = "hard"  # 能指到「文件 + 行号」的逐字原文
STRENGTH_DIFF: Final = "diff"  # 能指到运行时实读或文档锚点，但指不到行号
STRENGTH_GRAY: Final = "gray"  # 只有惯例，没有原文 —— 报告里必须用"惯例/约定"措辞

STRENGTHS: Final[tuple[str, ...]] = (STRENGTH_HARD, STRENGTH_DIFF, STRENGTH_GRAY)

#: `gray` 强度条目在报告里必须出现的字样（bench 断言它存在，不靠人记得写）。
GRAY_MARKERS: Final[tuple[str, ...]] = ("惯例非标准", "约定非标准")

# ── 出处类型（plan/04 §2.1：fail-closed）───────────────────────────────────
SOURCE_FILE: Final = "file"
SOURCE_RUNTIME: Final = "runtime"
SOURCE_DOC: Final = "doc"
SOURCE_KINDS: Final[tuple[str, ...]] = (SOURCE_FILE, SOURCE_RUNTIME, SOURCE_DOC)

#: 各 kind 的必填字段。装载期 fail-closed：缺一个就抛 CatalogError。
SOURCE_REQUIRED_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    SOURCE_FILE: ("file", "line", "repo", "ref"),
    SOURCE_RUNTIME: ("runtime", "program_version", "verified_at"),
    SOURCE_DOC: ("url", "anchor", "verified_at"),
}

#: 各 kind 能拿到的最高判定强度（不可升级：`runtime`/`doc` 永远拿不到 `hard`）。
SOURCE_MAX_STRENGTH: Final[dict[str, str]] = {
    SOURCE_FILE: STRENGTH_HARD,
    SOURCE_RUNTIME: STRENGTH_DIFF,
    SOURCE_DOC: STRENGTH_DIFF,
}

#: 运行时视角的取值域。
RUNTIMES: Final[tuple[str, ...]] = ("node", "python")


def exit_code_for_verdict(verdict: str) -> int:
    """给定判定态返回本工具退出码。**唯一处**：``cli.py`` 只能调它，不许自己写映射。"""
    if verdict in NON_UNIQUE_VERDICTS:
        return EXIT_NON_UNIQUE
    if verdict in UNDECIDABLE_VERDICTS:
        return EXIT_UNDECIDABLE
    if verdict == UNAMBIGUOUS:
        return EXIT_OK
    raise ValueError(f"未知判定态: {verdict!r}（不在 contract.VERDICTS 内）")


def exit_code_for_attribution(attribution: str) -> int:
    """给定退出码归因返回本工具退出码。判据同 ``exit_code_for_verdict``。"""
    if attribution in NON_UNIQUE_ATTRIBUTIONS:
        return EXIT_NON_UNIQUE
    if attribution in (SIGNAL_KILLED, NORMAL_EXIT, SYSEXITS):
        return EXIT_OK
    raise ValueError(f"未知归因: {attribution!r}（不在 contract.ATTRIBUTIONS 内）")
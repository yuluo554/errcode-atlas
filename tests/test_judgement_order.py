"""判定顺序**逐行**锁死：``plan/03`` §2.2 的九行表 + §3.2 的六行表。

为什么按"行"而不是按"功能"组织测试：判定顺序是本项目最容易"被好心重排"的东西
—— 把 `128+n` 提到 `0` 前面、把 `64–78` 挪到 `NORMAL-EXIT` 后面，每条单看都像
无害的整理，但每动一次就换一批答案。所以**表有几行，这里就有几条测试**，
且每条测试的 docstring 直接写"对着哪一行"（改表忘改测试会立刻对不上）。

判据一律用**真编目**（``load()``）：小假编目证明不了"真数据上仍然按这个顺序"。
只有需要构造退化形态（域为空、信号表空）时才用假编目，且那种地方会明写理由。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from errcode_atlas import catalog as catalog_mod
from errcode_atlas import contract
from errcode_atlas.catalog import load
from errcode_atlas.explain import Query, explain
from errcode_atlas.exitcode import attribute

REPO_ROOT = Path(__file__).resolve().parents[1]


CATALOG = load()


def _q(text, platform=None, domain=None):
    return explain(Query.parse(text, platform, domain), CATALOG)


def _a(code, platform, catalog=None):
    return attribute(code, platform, catalog if catalog is not None else CATALOG)


# ══ plan/03 §2.2 判定顺序表（九行）══════════════════════════════════════════
# 序 1：数字 + 平台，命中 1 个 name → UNAMBIGUOUS
def test_row_1_number_with_platform_single_hit():
    """序 1 —— 数字 + 平台 + 该域该值只命中一个名字。"""
    result = _q("98", "linux", "errno")
    assert result.verdict == contract.UNAMBIGUOUS
    assert [c["name"] for c in result.candidates] == ["EADDRINUSE"]
    assert result.exit_code == 0


# 序 2：数字 + 平台，命中 ≥2 个 name → AMBIGUOUS-SAME-PLATFORM
def test_row_2_number_with_platform_multiple_names():
    """序 2 —— 同平台同域一数多名（Linux 6 = SIGABRT / SIGIOT，上游声明的历史别名）。"""
    result = _q("6", "linux", "signal")
    assert result.verdict == contract.AMBIGUOUS_SAME_PLATFORM
    assert sorted(c["name"] for c in result.candidates) == ["SIGABRT", "SIGIOT"]
    assert result.exit_code == 1
    # 绝不收敛到"更常见的那一个"：候选必须全列（plan/03 §2.4）
    assert len(result.candidates) == 2


def test_row_2_windows_python_same_numeric_two_names():
    """序 2 的第二份素材 —— Python 视角把 `EADDRINUSE` 与 `WSAEADDRINUSE` 都导出为 10048。

    这不是编造的用例：同一台机器上 `errno` 模块真的同时导出这两个名字。
    """
    result = _q("10048", "win32-python", "errno")
    assert result.verdict == contract.AMBIGUOUS_SAME_PLATFORM
    assert sorted(c["name"] for c in result.candidates) == ["EADDRINUSE", "WSAEADDRINUSE"]


# 序 3：数字 + 无平台，各平台命中集合不一致 或 某已覆盖平台没有 → AMBIGUOUS-CROSS-PLATFORM
def test_row_3_number_without_platform_divergent_set():
    """序 3 —— 未给平台的**数字**查询，各平台命中集合不一致。"""
    result = _q("11", None, "errno")
    assert result.verdict == contract.AMBIGUOUS_CROSS_PLATFORM
    assert result.per_platform["linux"] == ["EAGAIN", "EWOULDBLOCK"]
    assert result.per_platform["macos"] == ["EDEADLK"]
    assert result.exit_code == 1


def test_row_3_absent_platform_on_covered_domain_is_reported():
    """序 3 的第二半 —— "某已覆盖平台上没有这个值"也是分歧，且**必须进结构字段**。

    两个 win32 视角都覆盖 `signal` 域，但都没有 19 号；只说"各平台归因不一致"而不说
    缺了谁，消费方得自己反推 `covered_platforms` 才能补出这个事实。
    """
    result = _q("19", None, "signal")
    assert result.verdict == contract.AMBIGUOUS_CROSS_PLATFORM
    assert result.per_platform == {"linux": ["SIGSTOP"], "macos": ["SIGCONT"]}
    assert sorted(result.platform_absent_in) == ["win32-node", "win32-python"]


def test_row_3_uncovered_platform_is_not_counted_as_divergence():
    """序 3 的**分母纪律**：未覆盖该域的平台是"还没查"，不是"查过没有"。

    `node` 域不挂 `win32-python`；若把该平台算进分歧，`ERR_*` 的名字查询会凭空
    多出假歧义。判据 = "这个平台的缺席，是『我查过没有』还是『我还没查』？"
    """
    result = explain(Query.parse("ERR_AMBIGUOUS_ARGUMENT", None, "node"), CATALOG)
    # node 域覆盖三个平台、名字都在 → 一致；win32-python 不覆盖，不进分母
    assert result.verdict == contract.UNAMBIGUOUS
    assert set(result.per_platform) == {"linux", "macos", "win32-node"}
    assert "win32-python" not in result.per_platform
    assert result.platform_absent_in == ()


# 序 4：数字 + 无平台，已覆盖平台上集合一致且都存在 → UNAMBIGUOUS
def test_row_4_number_without_platform_agreeing():
    """序 4 —— 信号 11 在四个平台上都只有 SIGSEGV：一致，不构成歧义。"""
    result = _q("11", None, "signal")
    assert result.verdict == contract.UNAMBIGUOUS
    assert result.exit_code == 0
    assert {p: tuple(v) for p, v in result.per_platform.items()} == {
        p: ("SIGSEGV",) for p in contract.PLATFORMS
    }


# 序 5：名字 + 平台，该平台没有但别的平台有 → PLATFORM-ABSENT
def test_row_5_name_missing_on_platform_but_present_elsewhere():
    """序 5 —— `SIGSTKFLT` 只有 Linux 有（signal.h:27 = 16），macOS 原文里根本没有这个名字。"""
    result = _q("SIGSTKFLT", "macos", "signal")
    assert result.verdict == contract.PLATFORM_ABSENT
    assert result.platform_absent_in == ("macos",)
    assert result.per_platform == {"linux": 16}
    assert result.exit_code == 1


def test_row_5_node_domain_absent_on_python_view():
    """序 5 的第二份素材 —— `win32-python` 上查 `ERR_*` 是 `PLATFORM-ABSENT`，**不是** `UNKNOWN`。

    前者说"这个平台没有这套码"，后者说"我没查到"。这是本题的一等公民区分
    （`data/README.md` §2.3）。
    """
    absent = explain(Query.parse("ERR_AMBIGUOUS_ARGUMENT", "win32-python", None), CATALOG)
    unknown = explain(Query.parse("ERR_AMBIGUOUS_ARGUMENT", "macos", "errno"), CATALOG)
    assert absent.verdict == contract.PLATFORM_ABSENT
    assert absent.exit_code == 1
    assert unknown.verdict == contract.UNKNOWN
    assert unknown.exit_code == 3


# 序 6：名字 + 平台，该平台有此 name → UNAMBIGUOUS
def test_row_6_name_present_on_platform():
    """序 6 —— `ERR_AMBIGUOUS_ARGUMENT` 在 linux 上存在（node 域），且**没有数字码值**。"""
    result = _q("ERR_AMBIGUOUS_ARGUMENT", "linux", None)
    assert result.verdict == contract.UNAMBIGUOUS
    assert result.candidates[0]["value"] is None
    assert result.candidates[0]["domain"] == contract.DOMAIN_NODE


# 序 7：名字 + 无平台，全部已覆盖平台都有定义（取值可以不同）→ UNAMBIGUOUS
def test_row_7_name_without_platform_values_differ_but_unique():
    """序 7 —— `EAGAIN` 四平台都有定义，取值 11/35/11/11。**值不同不是歧义**。

    这条是 M1 实测踩到的口径冲突（`plan/06` G6）：问 EAGAIN 问的是"这个名字有没有
    定义"，答案唯一；只有问"这个**数字**是什么"才会因跨平台失去唯一性。
    """
    result = _q("EAGAIN", None, None)
    assert result.verdict == contract.UNAMBIGUOUS
    assert result.exit_code == 0
    assert result.per_platform == {"linux": 11, "macos": 35, "win32-node": 11, "win32-python": 11}
    assert any("不构成歧义" in note for note in result.notes)


# 序 8：名字 + 无平台，某已覆盖平台上没有定义 → PLATFORM-ABSENT
def test_row_8_name_without_platform_missing_somewhere():
    """序 8 —— `SIGBUS` 在 linux/macos 有（7/10），两个 win32 视角没有。"""
    result = _q("SIGBUS", None, "signal")
    assert result.verdict == contract.PLATFORM_ABSENT
    assert sorted(result.platform_absent_in) == ["win32-node", "win32-python"]
    assert result.per_platform == {"linux": 7, "macos": 10}
    assert result.exit_code == 1


def test_row_7_and_row_8_are_distinct():
    """序 7 与序 8 的分界 —— "各平台都有、值不同" vs "某个平台根本没有"。"""
    agree = _q("EAGAIN", None, None)
    missing = _q("SIGBUS", None, "signal")
    assert agree.verdict == contract.UNAMBIGUOUS
    assert missing.verdict == contract.PLATFORM_ABSENT
    assert agree.exit_code != missing.exit_code


# 序 9：任一形态，编目内完全无此值/名 → UNKNOWN（exit 3）
def test_row_9_unknown_both_shapes():
    """序 9 —— `UNKNOWN` 两种形态都要 exit 3：

    1. **越界值**：`63` 不在 linux 信号表内（上界 31）；
    2. **域内有条目但无此值**：`1 --domain exit`（exit 域有 15 条，1 不在其中）。
    """
    out_of_range = _q("63", "linux", "signal")
    in_domain_miss = _q("1", "linux", "exit")
    for result in (out_of_range, in_domain_miss):
        assert result.verdict == contract.UNKNOWN
        assert result.exit_code == 3
    assert out_of_range.exit_code != _q("6", "linux", "signal").exit_code


# ══ plan/03 §3.2 判定顺序表（六行）══════════════════════════════════════════
# 序 1：code < 0 或 > 255 → UNATTRIBUTABLE
@pytest.mark.parametrize("code", [-1, 256, 65535])
def test_exit_row_1_out_of_range(code):
    """序 1 —— 越界（含负值）。"""
    result = _a(code, "linux")
    assert result.attribution == contract.UNATTRIBUTABLE
    assert result.exit_code == 1


# 序 2：64 ≤ code ≤ 78 → SYSEXITS，标注"约定非标准"
def test_exit_row_2_sysexits_range():
    """序 2 —— 落在约定段即 `SYSEXITS`，并给该码的 sysexits 名。"""
    result = _a(64, "linux")
    assert result.attribution == contract.SYSEXITS
    assert result.sysexits_name == "EX_USAGE"
    assert any("约定非标准" in note for note in result.notes)
    assert result.exit_code == 0


def test_exit_row_2_beats_rows_3_and_5():
    """序 2 排在 3/5 之前是刻意的 —— 64–78 不许被判成 NORMAL-EXIT。"""
    assert _a(64, "linux").attribution == contract.SYSEXITS
    assert _a(63, "linux").attribution == contract.NORMAL_EXIT
    assert _a(79, "linux").attribution == contract.NORMAL_EXIT


# 序 3：code == 0 → NORMAL-EXIT
def test_exit_row_3_zero_is_normal_exit():
    """序 3 —— 0 = 成功。"""
    result = _a(0, "linux")
    assert result.attribution == contract.NORMAL_EXIT
    assert result.exit_code == 0


# 序 4：128 < code ≤ 128+max_signal 且 code-128 是该平台有效信号 → SIGNAL-KILLED
def test_exit_row_4_signal_killed_with_valid_n():
    """序 4 —— `128+9 = 137`，9 在 linux 信号表内 → `SIGNAL-KILLED(SIGKILL)`。"""
    result = _a(137, "linux")
    assert result.attribution == contract.SIGNAL_KILLED
    assert result.signal == 9
    assert result.signal_name == "SIGKILL"
    assert any("惯例非标准" in note for note in result.notes)
    assert result.exit_code == 0


def test_exit_row_4_same_code_different_signal_by_platform():
    """序 4 的可演示陷阱 —— `147` 在 linux 是 SIGSTOP(19)、在 macos 是 SIGCONT(19)。

    `plan/03` §3.3 明写"不得在代码里写死信号名"：这里两个平台叶子值不同，
    名字也只能从各自的编目里取。
    """
    linux = _a(147, "linux")
    macos = _a(147, "macos")
    assert (linux.signal, linux.signal_name) == (19, "SIGSTOP")
    assert (macos.signal, macos.signal_name) == (19, "SIGCONT")
    assert linux.signal_name != macos.signal_name


def test_exit_row_4_invalid_n_falls_through_to_unattributable():
    """序 4 的**硬纪律前半** —— `n` 不在该平台信号表内则 `128+n` 不成立。

    `win32-python` 的 signal 导出集合没有 9，于是同一个 137 在那里必须翻成
    `UNATTRIBUTABLE`。判据只能来自编目，不许代码里写死信号表。
    """
    result = _a(137, "win32-python")
    assert result.attribution == contract.UNATTRIBUTABLE
    assert result.exit_code == 1
    assert any("不是有效信号" in note for note in result.notes)


def test_exit_row_4_n_validity_comes_only_from_catalog():
    """信号表为空 → 137 必须不再成立（证明判据来自编目而不是代码常量）。"""
    empty = catalog_mod.Catalog()
    assert _a(137, "linux", empty).attribution == contract.UNATTRIBUTABLE


# 序 5：1 ≤ code ≤ 127 且不属于 64–78 → NORMAL-EXIT，其中 1 必须标注
def test_exit_row_5_one_is_unattributable_with_mandatory_note():
    """序 5 的例外 —— `exit 1` 是**通用失败**，必须 `UNATTRIBUTABLE` 且明写无特定语义。"""
    result = _a(1, "linux")
    assert result.attribution == contract.UNATTRIBUTABLE
    assert result.exit_code == 1
    joined = " ".join(result.notes)
    assert "通用失败" in joined
    assert "无特定语义" in joined
    assert result.signal is None and result.sysexits_name is None


def test_exit_row_5_other_in_range_is_normal_exit():
    """序 5 的正文 —— 2–63 与 79–127 是 `NORMAL-EXIT`（程序自定义语义）。"""
    for code in (2, 30, 63, 79, 127):
        assert _a(code, "linux").attribution == contract.NORMAL_EXIT
        assert _a(code, "linux").exit_code == 0


# 序 6：其余（含 128 本身）→ UNATTRIBUTABLE
def test_exit_row_6_rest_is_unattributable():
    """序 6 —— `128` 本身（`n=0` 不是信号）落在这里。"""
    result = _a(128, "linux")
    assert result.attribution == contract.UNATTRIBUTABLE
    assert result.exit_code == 1


# ══ 两张表的行数必须与文档一致（改表忘改测试会在这里红）══════════════════════
def test_documented_table_row_counts():
    """`plan/03` §2.2 是九行、§3.2 是六行 —— 行数变了就说明文档被改过。

    这不是"数表格行"的文字游戏：上面每条测试对着一个序，序数变了而测试没变，
    测试名字就会说谎。判据 = **行数**，因为它最便宜且不容易被措辞改动骗过。
    """
    text = (REPO_ROOT / "plan" / "03-模块详设.md").read_text(encoding="utf-8")

    def rows_of(heading: str, next_heading: str) -> int:
        start = text.index(heading)
        end = text.index(next_heading, start)
        return sum(
            1
            for line in text[start:end].split("\n")
            if line.startswith("|") and line.split("|")[1].strip().isdigit()
        )

    assert rows_of("### 2.2 判定顺序", "### 2.3") == 9, "§2.2 判定顺序表不再是九行"
    assert rows_of("### 3.2 判定顺序", "### 3.3") == 6, "§3.2 判定顺序表不再是六行"
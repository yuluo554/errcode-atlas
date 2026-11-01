"""模块③ 退出码归因：`exit 1` 与 `128+n` 有效性是两条硬纪律。

每张测试对着 ``plan/03`` §3.2 的一行 + ``plan/01`` §二 模块③ 的两条硬纪律。
"""

from __future__ import annotations

import pytest

from errcode_atlas import catalog as catalog_mod
from errcode_atlas import contract
from errcode_atlas.exitcode import attribute


def _source(line=1):
    return {"kind": "file", "file": "include/uapi/x.h", "line": line, "repo": "o/r", "ref": "abc"}


@pytest.fixture
def cat(tmp_path, write_catalog):
    """linux 有 SIGKILL=9 / SIGTERM=15 / SIGSEGV=11；macos 只有 SIGSTOP=17 / SIGKILL=9。

    **刻意让两个平台的信号表不同**：`128+19` 在 linux 上是 SIGSTOP、在 macos 上不是任何信号
    —— 这正是"必须先问平台"的可演示面。
    """
    payload = {
        "platforms": {
            "linux": [
                {"name": "SIGKILL", "domain": "signal", "value": 9, "source": _source(9)},
                {"name": "SIGSEGV", "domain": "signal", "value": 11, "source": _source(11)},
                {"name": "SIGTERM", "domain": "signal", "value": 15, "source": _source(15)},
                {"name": "SIGSTOP", "domain": "signal", "value": 19, "source": _source(19)},
            ],
            "macos": [
                {"name": "SIGKILL", "domain": "signal", "value": 9, "source": _source(9)},
                {"name": "SIGSTOP", "domain": "signal", "value": 17, "source": _source(17)},
            ],
        }
    }
    path = write_catalog(payload)
    return catalog_mod.load(path, tmp_path / "missing.manifest.json")


# ── 序 2：SYSEXITS（约定非标准）─────────────────────────────────────────────
@pytest.mark.parametrize("code", [64, 65, 70, 78])
def test_sysexits_range_is_sysexits(cat, code):
    result = attribute(code, "linux", cat)
    assert result.attribution == contract.SYSEXITS
    assert result.sysexits_name is not None
    assert any("约定非标准" in note for note in result.notes)
    assert result.exit_code == contract.EXIT_OK


def test_sysexits_beats_normal_exit_for_same_range(cat):
    """顺序 2 必须排在 3/5 之前：64–78 不许被判成 NORMAL-EXIT。"""
    assert attribute(64, "linux", cat).attribution == contract.SYSEXITS
    assert attribute(63, "linux", cat).attribution == contract.NORMAL_EXIT
    assert attribute(79, "linux", cat).attribution == contract.NORMAL_EXIT


# ── 序 3：NORMAL-EXIT 0 ────────────────────────────────────────────────────
def test_zero_is_normal_exit(cat):
    result = attribute(0, "linux", cat)
    assert result.attribution == contract.NORMAL_EXIT
    assert result.exit_code == contract.EXIT_OK


# ── 序 4：SIGNAL-KILLED（含惯例标注）───────────────────────────────────────
def test_137_on_linux_is_signal_killed_sigkill(cat):
    result = attribute(137, "linux", cat)
    assert result.attribution == contract.SIGNAL_KILLED
    assert result.signal == 9
    assert result.signal_name == "SIGKILL"
    assert any("惯例非标准" in note for note in result.notes)
    assert result.exit_code == contract.EXIT_OK


def test_same_number_attributes_to_different_signal_by_platform(cat):
    """`128+19 = 147`：linux 上是 SIGSTOP(19)，macos 上 19 不是信号 → UNATTRIBUTABLE。"""
    linux = attribute(147, "linux", cat)
    macos = attribute(147, "macos", cat)
    assert linux.attribution == contract.SIGNAL_KILLED
    assert linux.signal_name == "SIGSTOP"
    assert macos.attribution == contract.UNATTRIBUTABLE
    assert macos.exit_code == contract.EXIT_NON_UNIQUE


# ── 序 5：exit 1 硬纪律 ───────────────────────────────────────────────────
def test_exit_one_is_unattributable_on_every_platform(cat):
    for platform in ("linux", "macos"):
        result = attribute(1, platform, cat)
        assert result.attribution == contract.UNATTRIBUTABLE
        assert result.exit_code == contract.EXIT_NON_UNIQUE
        assert any("通用失败" in note for note in result.notes)


def test_exit_one_is_never_explained_as_specific_error(cat):
    """不得把 exit 1 强行解释成任何具体错误：notes 里不许出现"就是 X"式断言。"""
    result = attribute(1, "linux", cat)
    assert result.signal is None
    assert result.sysexits_name is None
    assert "无特定语义" in " ".join(result.notes)


# ── 128+n 有效性（硬纪律二）───────────────────────────────────────────────
def test_128_plus_n_with_invalid_n_is_unattributable(cat):
    """macos 只有 9 / 17 两个信号：`128+11` 的 n=11 无效 → UNATTRIBUTABLE。"""
    result = attribute(139, "macos", cat)
    assert result.attribution == contract.UNATTRIBUTABLE
    assert any("不是有效信号" in note for note in result.notes)


def test_128_itself_is_unattributable(cat):
    """`128+0` 的 n=0 不是信号 → 不成立。"""
    result = attribute(128, "linux", cat)
    assert result.attribution == contract.UNATTRIBUTABLE


def test_n_validity_comes_only_from_catalog(cat):
    """代码里不许写死信号表：信号表为空的 Catalog 上，137 必须不再成立。"""
    empty = catalog_mod.Catalog()
    assert attribute(137, "linux", empty).attribution == contract.UNATTRIBUTABLE
    assert attribute(137, "linux", cat).attribution == contract.SIGNAL_KILLED


# ── 序 1：越界 / 负值 / Windows 巨型码 ────────────────────────────────────
@pytest.mark.parametrize("code", [256, 300, -1])
def test_out_of_range_is_unattributable(cat, code):
    result = attribute(code, "linux", cat)
    assert result.attribution == contract.UNATTRIBUTABLE
    assert result.exit_code == contract.EXIT_NON_UNIQUE


def test_uint32_truncated_code_is_marked_truncated(cat):
    """`18446744072635809792 = 0xFFFFFFFF00000000`：截断后为 0。"""
    result = attribute(18446744072635809792, "win32-node", cat)
    assert result.truncated is True
    assert any("截断" in note for note in result.notes)


def test_truncated_code_keeps_original_value_in_result(cat):
    """结果里记的是**原值**（用户看到的那个数字），不是截断后的。"""
    original = 18446744072635809792
    result = attribute(original, "win32-node", cat)
    assert result.code == original


# ── 退出码语义可分（plan/04 §4 门槛）──────────────────────────────────────
def test_unattributable_and_unknown_use_different_exit_codes(cat):
    unatt = attribute(1, "linux", cat)
    assert unatt.exit_code == contract.EXIT_NON_UNIQUE
    assert unatt.exit_code != contract.EXIT_UNDECIDABLE


def test_attribution_order_is_locked(cat):
    """顺序写死：sysexits 段不许被 128+n 或 normal 抢走。"""
    assert attribute(78, "linux", cat).attribution == contract.SYSEXITS
    assert attribute(64, "linux", cat).attribution == contract.SYSEXITS
"""模块② 判定层：五态、判定顺序、不收敛。

每张测试对着 ``plan/03`` §2.2 的一行。关键纪律：``AMBIGUOUS-*`` 是**结果**不是失败。
"""

from __future__ import annotations

import pytest

from errcode_atlas import catalog as catalog_mod
from errcode_atlas import contract
from errcode_atlas.explain import Query, explain


def _source():
    return {"kind": "file", "file": "include/uapi/x.h", "line": 1, "repo": "o/r", "ref": "abc"}


def _entry(name, value, domain="errno", platform_source=None):
    return {
        "name": name,
        "domain": domain,
        "value": value,
        "source": platform_source or _source(),
        "description_zh": "t",
        "posix_ref": "<none>",
    }


@pytest.fixture
def cat(tmp_path, write_catalog):
    """一份小但**覆盖五态**的编目：

    * linux  errno 11=EAGAIN / 98=EADDRINUSE；signal 6=SIGABRT+SIGIOT（同值别名）
    * macos  errno 35=EAGAIN / 48=EADDRINUSE；signal 6 无 SIGABRT、无 SIGSTKFLT
    * win32-node errno 100=EADDRINUSE
    """
    payload = {
        "platforms": {
            "linux": [
                _entry("EAGAIN", 11),
                _entry("EADDRINUSE", 98),
                _entry("SIGABRT", 6, "signal"),
                _entry("SIGIOT", 6, "signal"),
                _entry("SIGKILL", 9, "signal"),
            ],
            "macos": [
                _entry("EAGAIN", 35),
                _entry("EADDRINUSE", 48),
                _entry("SIGSTOP", 17, "signal"),
            ],
            "win32-node": [_entry("EADDRINUSE", 100)],
            "win32-python": [_entry("EADDRINUSE", 10048)],
        }
    }
    path = write_catalog(payload)
    return catalog_mod.load(path, tmp_path / "missing.manifest.json")


def _run(cat, text, platform=None, domain=None):
    return explain(Query.parse(text, platform, domain), cat)


# ── 序 1：UNAMBIGUOUS（数字 + 平台，唯一命中）──────────────────────────────
def test_number_with_platform_single_hit_is_unambiguous(cat):
    result = _run(cat, "98", "linux")
    assert result.verdict == contract.UNAMBIGUOUS
    assert [c["name"] for c in result.candidates] == ["EADDRINUSE"]
    assert result.exit_code == contract.EXIT_OK


# ── 序 2：AMBIGUOUS-SAME-PLATFORM（同平台同域一数多名）─────────────────────
def test_number_with_two_names_is_same_platform_ambiguous(cat):
    result = _run(cat, "6", "linux", "signal")
    assert result.verdict == contract.AMBIGUOUS_SAME_PLATFORM
    assert [c["name"] for c in result.candidates] == ["SIGABRT", "SIGIOT"]
    assert result.exit_code == contract.EXIT_NON_UNIQUE
    assert result.distinguish  # 必须给出区分说明


def test_ambiguous_never_collapses_to_single_candidate(cat):
    """**绝不收敛**：不许因为"最常见"就只报一个（plan/03 §2.4）。"""
    result = _run(cat, "6", "linux", "signal")
    assert len(result.candidates) == 2


# ── 序 3/4：跨平台 ─────────────────────────────────────────────────────────
def test_number_without_platform_diverging_is_cross_platform_ambiguous(cat):
    result = _run(cat, "11")
    assert result.verdict == contract.AMBIGUOUS_CROSS_PLATFORM
    assert result.per_platform["linux"] == ["EAGAIN"]
    assert "macos" not in result.per_platform  # 11 在 macos 上没有
    assert result.exit_code == contract.EXIT_NON_UNIQUE


def test_number_without_platform_single_platform_still_counts(cat):
    """只有 linux 有 11 → 各平台命中集合只有一个值，但**缺失平台必须可见**。"""
    result = _run(cat, "11")
    assert "win32-node" not in result.per_platform


# ── 序 5：PLATFORM-ABSENT（名字在别处有、在这里没有）────────────────────────
def test_name_missing_on_platform_is_platform_absent(cat):
    result = _run(cat, "SIGSTOP", "macos", "signal")
    assert result.verdict == contract.UNAMBIGUOUS
    result2 = _run(cat, "SIGSTOP", "linux", "signal")
    assert result2.verdict == contract.PLATFORM_ABSENT
    assert result2.platform_absent_in == ("linux",)
    assert "macos" in result2.per_platform
    assert result2.exit_code == contract.EXIT_NON_UNIQUE


def test_platform_absent_is_not_unknown(cat):
    """PLATFORM-ABSENT 与 UNKNOWN 是两个语义（一等公民区分）。"""
    absent = _run(cat, "SIGSTOP", "linux", "signal")
    unknown = _run(cat, "SIGSTKFLT", "linux", "signal")
    assert absent.verdict == contract.PLATFORM_ABSENT
    assert unknown.verdict == contract.UNKNOWN
    assert unknown.exit_code == contract.EXIT_UNDECIDABLE
    assert absent.exit_code != unknown.exit_code


# ── 序 6/7：名字命中 / UNKNOWN ─────────────────────────────────────────────
def test_name_with_platform_hit_is_unambiguous(cat):
    result = _run(cat, "EADDRINUSE", "win32-python")
    assert result.verdict == contract.UNAMBIGUOUS
    assert result.candidates[0]["value"] == 10048


def test_out_of_catalog_number_is_unknown_and_exit_three(cat):
    result = _run(cat, "99999", "linux")
    assert result.verdict == contract.UNKNOWN
    assert result.exit_code == contract.EXIT_UNDECIDABLE


def test_unknown_is_distinguishable_from_ambiguous_by_exit_code(cat):
    unknown = _run(cat, "99999", "linux")
    ambiguous = _run(cat, "6", "linux", "signal")
    assert unknown.exit_code == contract.EXIT_UNDECIDABLE
    assert ambiguous.exit_code == contract.EXIT_NON_UNIQUE
    assert unknown.exit_code != ambiguous.exit_code


# ── 每条判定必须带出处（plan/01 §六 结论纪律）───────────────────────────────
def test_unambiguous_always_carries_sources(cat):
    result = _run(cat, "98", "linux")
    assert result.sources
    assert all(":" in label for label in result.sources)


def test_candidate_ordering_is_deterministic(cat):
    first = _run(cat, "6", "linux", "signal").as_dict()
    second = _run(cat, "6", "linux", "signal").as_dict()
    assert first == second


# ── 域自动探测 ─────────────────────────────────────────────────────────────
def test_domain_autodetect_finds_signal_when_errno_misses(cat):
    result = _run(cat, "9", "linux")  # errno 无 9，signal 有 SIGKILL
    assert result.verdict == contract.UNAMBIGUOUS
    assert result.candidates[0]["name"] == "SIGKILL"


# ── Windows 双视角不得合并 ─────────────────────────────────────────────────
def test_windows_views_are_distinct_platforms(cat):
    node = _run(cat, "EADDRINUSE", "win32-node")
    py = _run(cat, "EADDRINUSE", "win32-python")
    assert node.candidates[0]["value"] == 100
    assert py.candidates[0]["value"] == 10048
    assert node.candidates[0]["value"] != py.candidates[0]["value"]
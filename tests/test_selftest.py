"""自测入口与基准入口都要被真调（零调用点 = 空转）。

`selftest.run_selftest` 必须由 ``cli selftest`` 与测试**双方**真调；
`bench.run_bench` 的三种缺件态必须各报一句不同的提示（"0 分"与"没扫到"不同形）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from errcode_atlas import catalog as catalog_mod
from errcode_atlas import contract
from errcode_atlas.bench import run_bench
from errcode_atlas.selftest import run_selftest


def _source(line=1):
    return {"kind": "file", "file": "include/uapi/x.h", "line": line, "repo": "o/r", "ref": "abc"}


@pytest.fixture
def cat(tmp_path, write_catalog):
    payload = {
        "platforms": {
            "linux": [
                {"name": "SIGKILL", "domain": "signal", "value": 9, "source": _source(9)},
                {"name": "SIGABRT", "domain": "signal", "value": 6, "source": _source(6)},
                {"name": "SIGIOT", "domain": "signal", "value": 6, "source": _source(7)},
                {"name": "EAGAIN", "domain": "errno", "value": 11, "source": _source(11)},
            ],
            "macos": [
                {"name": "SIGKILL", "domain": "signal", "value": 9, "source": _source(9)},
            ],
        }
    }
    return catalog_mod.load(write_catalog(payload), tmp_path / "missing.manifest.json")


# ── selftest 被真调 ────────────────────────────────────────────────────────
def test_selftest_is_green_on_a_sane_catalog(cat):
    assert run_selftest(cat) == []


def test_selftest_is_also_called_by_the_cli(capsys):
    """`cli selftest` 必须真跑到它（否则就是零调用点）。"""
    from errcode_atlas import cli

    assert cli.main(["selftest"]) == contract.EXIT_OK
    assert "selftest:" in capsys.readouterr().out


def test_selftest_catches_broken_exit_code_mapping(monkeypatch):
    """注入故障：把"不可归因"的退出码改成 0 → 自测必须报出来。"""
    from errcode_atlas import contract as c

    monkeypatch.setattr(c, "EXIT_NON_UNIQUE", 0)
    empty = catalog_mod.Catalog()
    failures = run_selftest(empty)
    assert any("exit_codes" in line or "exit_one" in line for line in failures)


def test_selftest_catches_missing_gray_marker(monkeypatch, cat):
    """注入故障：把强制字样挪走 → 自测必须报出来（字样不靠人记得写）。"""
    from errcode_atlas import contract as c

    monkeypatch.setattr(c, "GRAY_MARKERS", ("绝不出现的字样",))
    failures = run_selftest(cat)
    assert any("gray_markers" in line for line in failures)


# ── bench 三态缺件各说各话 ────────────────────────────────────────────────
def test_bench_without_fixtures_reports_not_scanned(tmp_path, cat):
    messages: list[str] = []
    code = run_bench(cat, root=tmp_path / "nope", emit=messages.append)
    assert code == contract.EXIT_UNDECIDABLE
    assert any("0 个 case" in m for m in messages)


def test_bench_with_case_missing_expected_reports_which_file(tmp_path, cat):
    case = tmp_path / "c1"
    case.mkdir()
    (case / "INPUT.md").write_text("问：98 是什么\n", encoding="utf-8")
    messages: list[str] = []
    code = run_bench(cat, root=tmp_path, emit=messages.append)
    # 有 case 但一个也没跑成 → "没有证据"（3），不是"通过"（0）也不是"跑过且有差异"（1）
    assert code == contract.EXIT_UNDECIDABLE
    assert any("缺 expected.json" in m for m in messages)
    assert any("0 个 case" in m for m in messages)


def test_bench_with_case_missing_input_reports_which_file(tmp_path, cat):
    """缺 INPUT.md 的 case 也没跑成 → 同样是"没有证据"（3），但提示语必须不同。"""
    case = tmp_path / "c1"
    case.mkdir()
    (case / "expected.json").write_text("{}", encoding="utf-8")
    messages: list[str] = []
    code = run_bench(cat, root=tmp_path, emit=messages.append)
    assert code == contract.EXIT_UNDECIDABLE
    assert any("缺 INPUT.md" in m for m in messages)


def test_bench_passes_on_a_matching_case(tmp_path, cat):
    case = tmp_path / "c1"
    case.mkdir()
    (case / "INPUT.md").write_text("问：137 是什么\n", encoding="utf-8")
    (case / "expected.json").write_text(
        json.dumps(
            {
                "input": {"kind": "explain", "query": "6", "platform": "linux", "domain": "signal"},
                "verdict": contract.AMBIGUOUS_SAME_PLATFORM,
                "candidate_names": ["SIGABRT", "SIGIOT"],
                "exit_code": contract.EXIT_NON_UNIQUE,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    messages: list[str] = []
    code = run_bench(cat, root=tmp_path, emit=messages.append)
    assert code == contract.EXIT_OK, messages


def test_bench_fails_on_wrong_verdict(tmp_path, cat):
    case = tmp_path / "c1"
    case.mkdir()
    (case / "INPUT.md").write_text("x\n", encoding="utf-8")
    (case / "expected.json").write_text(
        json.dumps(
            {
                "input": {"kind": "explain", "query": "6", "platform": "linux", "domain": "signal"},
                "verdict": contract.UNAMBIGUOUS,
            }
        ),
        encoding="utf-8",
    )
    messages: list[str] = []
    code = run_bench(cat, root=tmp_path, emit=messages.append)
    assert code == contract.EXIT_NON_UNIQUE
    assert any("verdict 期望" in m for m in messages)


def test_bench_checks_exitcode_cases(tmp_path, cat):
    case = tmp_path / "c1"
    case.mkdir()
    (case / "INPUT.md").write_text("exit 137\n", encoding="utf-8")
    (case / "expected.json").write_text(
        json.dumps(
            {
                "input": {"kind": "exitcode", "code": 137, "platform": "linux"},
                "attribution": contract.SIGNAL_KILLED,
                "signal": 9,
                "signal_name": "SIGKILL",
                "exit_code": contract.EXIT_OK,
                "require_note_markers": ["惯例非标准"],
            }
        ),
        encoding="utf-8",
    )
    messages: list[str] = []
    code = run_bench(cat, root=tmp_path, emit=messages.append)
    assert code == contract.EXIT_OK, messages


def test_bench_rejects_unknown_input_kind(tmp_path, cat):
    case = tmp_path / "c1"
    case.mkdir()
    (case / "INPUT.md").write_text("x\n", encoding="utf-8")
    (case / "expected.json").write_text('{"input": {"kind": "guess"}}', encoding="utf-8")
    messages: list[str] = []
    run_bench(cat, root=tmp_path, emit=messages.append)
    assert any("不支持" in m for m in messages)
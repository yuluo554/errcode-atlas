"""CLI 出口：退出码映射的**唯一**验证点。

两条形态必须一致：``cli.main([...])`` 的返回值 与 子进程真实退出码
（`plan/03` §4.2 的最后一句）。``argparse`` 原生是 ``SystemExit(2)``，
本项目统一映射成 ``4`` —— 这条也要测，否则两个入口会漂。
"""

from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path

import pytest

from errcode_atlas import cli, contract

REPO_ROOT = Path(__file__).resolve().parents[1]


# ── main() 形态 ────────────────────────────────────────────────────────────
def test_version_exits_zero(capsys):
    assert cli.main(["--version"]) == 0
    assert "errcode-atlas" in capsys.readouterr().out


def test_help_exits_zero(capsys):
    assert cli.main(["--help"]) == 0
    capsys.readouterr()


def test_no_subcommand_is_usage_error(capsys):
    assert cli.main([]) == contract.EXIT_USAGE
    capsys.readouterr()


def test_unknown_subcommand_is_four_not_two(capsys):
    """argparse 原生 2；本项目必须是 4（plan/02 D5）。"""
    assert cli.main(["nosuch"]) == contract.EXIT_USAGE
    capsys.readouterr()


def test_win32_platform_alias_is_usage_error(capsys):
    code = cli.main(["explain", "98", "--platform", "win32"])
    captured = capsys.readouterr()
    assert code == contract.EXIT_USAGE
    assert "win32-node" in captured.err and "win32-python" in captured.err


def test_windows_alias_is_usage_error(capsys):
    assert cli.main(["explain", "98", "--platform", "windows"]) == contract.EXIT_USAGE
    capsys.readouterr()


def test_unknown_platform_is_usage_error(capsys):
    assert cli.main(["explain", "98", "--platform", "beos"]) == contract.EXIT_USAGE
    capsys.readouterr()


def test_exitcode_requires_platform(capsys):
    assert cli.main(["exitcode", "137"]) == contract.EXIT_USAGE
    capsys.readouterr()


def test_exitcode_non_integer_is_usage_error(capsys):
    assert cli.main(["exitcode", "abc", "--platform", "linux"]) == contract.EXIT_USAGE
    capsys.readouterr()


def test_build_check_on_empty_catalog_exits_zero(capsys):
    """M0 空编目是**合法初始态**：`build --check` 必须 0，并打印扫到了几个源文件。"""
    assert cli.main(["build", "--check"]) == contract.EXIT_OK
    out = capsys.readouterr().out
    assert "编目校验通过" in out


def test_explain_unknown_value_exits_three(capsys):
    assert cli.main(["explain", "99999", "--platform", "linux"]) == contract.EXIT_UNDECIDABLE
    capsys.readouterr()


def test_explain_json_output_is_parseable(capsys):
    import json

    assert cli.main(["explain", "99999", "--platform", "linux", "--json"]) == contract.EXIT_UNDECIDABLE
    payload = json.loads(capsys.readouterr().out)
    assert payload["verdict"] == contract.UNKNOWN


def test_error_json_carries_exit_code(capsys):
    import json

    code = cli.main(["exitcode", "137", "--platform", "win32", "--json"])
    assert code == contract.EXIT_USAGE
    payload = json.loads(capsys.readouterr().err)
    assert payload["exit_code"] == contract.EXIT_USAGE


# ── 子进程形态（真实退出码）────────────────────────────────────────────────
def _run_cli(*args: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        [sys.executable, "-m", "errcode_atlas", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


@pytest.mark.parametrize(
    "args,expected",
    [
        (("--version",), 0),
        (("--help",), 0),
        (("nosuch",), contract.EXIT_USAGE),
        (("explain", "98", "--platform", "win32"), contract.EXIT_USAGE),
        (("explain", "99999", "--platform", "linux"), contract.EXIT_UNDECIDABLE),
        (("build", "--check"), 0),
    ],
)
def test_subprocess_exit_codes_match_main(args, expected):
    """子进程退出码必须与 `main()` 返回值一致 —— 两条形态不许漂。"""
    proc = _run_cli(*args)
    assert proc.returncode == expected, f"{args} → {proc.returncode}（期望 {expected}）\n{proc.stderr}"


def test_cli_output_is_utf8_safe_on_ascii_console():
    """入口的 `_ensure_utf8_stdio()` 必须让中文输出在非 UTF-8 控制台也不炸。

    用 `errors=strict` 的 cp1252 桩复现 CI 的编码管道（本机 `py -X utf8` 会掩盖这个缺口）。
    """
    proc = subprocess.run(
        [sys.executable, "-m", "errcode_atlas", "build", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={
            **os.environ,
            "PYTHONPATH": str(REPO_ROOT / "src"),
            "PYTHONIOENCODING": "cp1252",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert "编目校验通过" in proc.stdout
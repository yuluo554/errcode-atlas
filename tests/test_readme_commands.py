"""README 命令反射：README 里写的每条 CLI 命令，parser 必须都认。

为什么这是"极低成本、直接抓得到"的一条（发布门纪律）：

* README 与代码是两份文件，没有任何门在对账"文档写的参数形态 parser 认不认"；
* 判据纯参数面 —— 不依赖任何真实数据，跑一次就是几十毫秒；
* **放行 ``--help`` / ``--version``**：argparse 的 help/version action 在 ``parse_args()``
  里直接 ``SystemExit(0)``，判据写成"任何 SystemExit 即红"会把用户面最正常的两条判红
  —— **``code != 0`` 才红**。

另一半同样重要：**抽命令的口径必须覆盖用户真会敲的主形态**。
只收 ``py -3.12 -m errcode_atlas`` 形态而漏掉装好后的裸命令 ``errcode-atlas``，
反射对账会"绿"，但用户那条从未被覆盖。
"""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"

#: 两种入口形态都必须被收到（否则只覆盖一半用户面）
INVOCATIONS = ("py -3.12 -m errcode_atlas", "errcode-atlas", "./.venv/Scripts/python.exe -m errcode_atlas")
SUBCOMMANDS = ("explain", "exitcode", "build", "selftest", "bench")

#: README 里出现的非 CLI 命令（工具脚本）—— 它们不走 argparse 的 CLI parser，
#: 由 ``tests/test_catalog_build.py`` / ``test_gates.py`` 各自覆盖。
NON_CLI_PREFIXES = ("py -3.12 tools/", "./.venv/Scripts/python.exe tools/")


def _code_blocks(text: str) -> list[str]:
    return re.findall(r"```(?:console|bash)?\n(.*?)```", text, re.DOTALL)


def _commands() -> list[tuple[str, list[str]]]:
    """抽出 README 里所有 CLI 命令，返回 ``(入口形态, argv)``。"""
    found: list[tuple[str, list[str]]] = []
    for block in _code_blocks(README.read_text(encoding="utf-8")):
        for raw in block.split("\n"):
            line = raw.strip().lstrip("$").strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(NON_CLI_PREFIXES):
                continue
            for invocation in INVOCATIONS:
                if line.startswith(invocation):
                    rest = line[len(invocation) :].strip()
                    tokens = shlex.split(rest) if rest else []
                    found.append((invocation, tokens))
                    break
    return found


def test_readme_commands_are_actually_extracted() -> None:
    """非空跑自证：一条都没抽到 = 判据是空的（README 换了写法？）。"""
    commands = _commands()
    assert commands, "README 里没抽到任何 CLI 命令 —— 抽取口径已经对不上了"


def test_readme_covers_both_entry_forms() -> None:
    """抽取口径必须同时覆盖"模块形态"与"装好后的裸命令形态"。"""
    forms = {invocation for invocation, _ in _commands()}
    assert any(" -m errcode_atlas" in f for f in forms), f"只抽到 {forms}"
    assert "errcode-atlas" in forms, f"README 没有裸命令形态（用户真会敲的那条）: {forms}"


def test_readme_covers_every_subcommand() -> None:
    """README 是本工具的用户面：四个模块 + 自测/基准都要有示例。"""
    mentioned = {
        tokens[0]
        for _, tokens in _commands()
        if tokens and not tokens[0].startswith("-")
    }
    missing = set(SUBCOMMANDS) - mentioned
    assert not missing, f"README 缺这些子命令的示例：{sorted(missing)}"


@pytest.mark.parametrize("invocation,tokens", _commands())
def test_parser_accepts_readme_command(invocation: str, tokens: list[str]) -> None:
    """逐条 ``parse_args``：``SystemExit`` 且 ``code != 0`` 才红。"""
    from errcode_atlas import cli

    parser = cli.build_parser()
    try:
        parser.parse_args(tokens)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        assert code == 0, f"`{invocation} {shlex.join(tokens)}` 被 parser 拒绝（exit {code}）"


def test_readme_commands_do_not_require_network() -> None:
    """README 命令里不许出现网络工具的调用（本项目纯本地、零上传）。"""
    text = README.read_text(encoding="utf-8")
    for forbidden in ("curl ", "wget ", "gh api", "pip install errcode-atlas"):
        assert forbidden not in text, f"README 出现联网命令：{forbidden}"


def test_readme_documents_the_precondition_for_rebuilding_catalog() -> None:
    """前置条件必须写进 README：否则解包树里跑不出编目（"生成物不入仓"那族缺陷）。"""
    text = README.read_text(encoding="utf-8")
    assert "tools/build_catalog.py" in text
    assert "PYTHONPATH=src" in text
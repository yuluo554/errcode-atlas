"""Agent Skill 入口 ``api.run()``：信封形态 + 与 ``cli.main`` 逐字节同源。

``plan/00`` §5 四格表把 Skill 形态的主入口点名到 ``api.py::run()``（K32）——
**点名了就必须有实物、有判据**，否则就是"文档点名、实物没有"那一族缺陷。

三条判据：

1. **同源**：``api.run(argv)`` 的两路文本必须与 ``cli.main(argv)`` 直接打印的**逐字节相同**
   —— 否则 Skill 读到的结论与 CLI 用户看到的不一致，而两边都"看起来在工作"。
2. **出口码不重算**：信封里的 ``exit_code`` 就是 ``cli.main`` 的返回值。这条挡的是
   "在 api 层再写一遍判定→退出码映射"（`plan/02` D5 唯一处的第二份真相源）。
3. **不打印**：``api.run()`` 调用期间 stdout/stderr 必须干净 —— 否则 Skill 侧会拿到
   两份输出（返回值一份、控制台一份），而哪份算数没有定义。
"""

from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout

import pytest

from errcode_atlas import api, cli, contract

#: 覆盖四个出口：0 / 1 / 3 / 4。出口码用**字面量**写期望，不写 ``contract.EXIT_*``
#: —— 用常量写期望值就是自我参照（常量本身改错时"实测"与"期望"一起错）。
CASES = [
    (["explain", "98", "--platform", "linux"], 0),
    (["explain", "11"], 1),  # AMBIGUOUS-CROSS-PLATFORM：有答案但不可唯一归因
    (["explain", "99999", "--platform", "linux"], 3),  # UNKNOWN：算不了
    (["explain", "98", "--platform", "win32"], 4),  # 别名被拒：用法错误
    (["exitcode", "137", "--platform", "linux"], 0),
    (["exitcode", "1", "--platform", "linux"], 1),
    (["build", "--check"], 0),
]


@pytest.mark.parametrize("argv,expected", CASES, ids=[c[0][0] + "-" + c[0][1] for c in CASES])
def test_api_exit_code_is_cli_main_return_value(argv: list[str], expected: int) -> None:
    """出口码**不重算**：信封里的码就是 ``cli.main`` 的返回值。"""
    result = api.run(argv)
    assert result.exit_code == expected, f"{argv} → {result.exit_code}（期望 {expected}）"


@pytest.mark.parametrize("argv,expected", CASES, ids=[c[0][0] + "-" + c[0][1] for c in CASES])
def test_api_text_is_byte_identical_to_cli_main(argv: list[str], expected: int) -> None:
    """两路文本与 ``cli.main`` 直接打印的逐字节相同（同源，不是"差不多"）。"""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        cli_code = cli.main(argv)
    result = api.run(argv)
    assert cli_code == result.exit_code, f"{argv}：两条路径的出口码漂了"
    assert result.stdout == out.getvalue(), f"{argv}：stdout 与 cli.main 不一致"
    assert result.stderr == err.getvalue(), f"{argv}：stderr 与 cli.main 不一致"


def test_api_does_not_print_to_real_stdio(capsys) -> None:
    """``api.run()`` 必须**不打印**：调用期间真实 stdout/stderr 干净。

    这条挡的是"顺手在 api 层 print 一句"——那样 Skill 侧会拿到两份输出。
    """
    before = capsys.readouterr()
    result = api.run(["explain", "98", "--platform", "linux"])
    after = capsys.readouterr()
    assert after.out == "" and after.err == "", (
        f"api.run() 往真实 stdio 打印了内容：out={after.out!r} err={after.err!r}"
    )
    assert result.stdout, "信封里没有 stdout —— 输出丢在中间了"
    assert before.out == "" and before.err == ""  # 判据本身非空跑


def test_api_error_goes_to_envelope_not_stdout() -> None:
    """错误进 ``stderr`` 那一栏，不是 stdout（与 CLI 的 ``plan/02`` D6 一致）。"""
    result = api.run(["explain", "98", "--platform", "beos"])
    assert result.exit_code == 4
    assert result.stdout == ""
    assert "errcode-atlas: " in result.stderr


def test_api_ok_property_only_means_unambiguous() -> None:
    """``ok`` 只在出口码 0 时为真 —— 它**不**替调用方解释 1 与 3 的差别。

    1（不可唯一归因）与 3（算不了）都是"非 0"，但它们是两种不同语义；
    信封只给码，语义的解释留给 ``data/README.md`` §5.1（唯一定义处）。
    """
    assert api.run(["explain", "98", "--platform", "linux"]).ok is True
    assert api.run(["explain", "11"]).ok is False
    assert api.run(["explain", "99999", "--platform", "linux"]).ok is False


def test_api_does_not_define_its_own_verdict_mapping() -> None:
    """AST 守门：``api.py`` 里不许出现"判定态 → 退出码"的分支。

    判据是"这个文件里有没有 ``if verdict == ...`` 那类比较" —— 有就是第二份真相源。
    `plan/02` D5：映射只在 ``contract.exit_code_for_*`` 一处，``cli.py`` 调它。
    """
    import ast
    from pathlib import Path

    path = Path(api.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    metric_names = set(contract.VERDICTS) | set(contract.ATTRIBUTIONS)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for operand in [node.left, *node.comparators]:
            if isinstance(operand, ast.Constant) and operand.value in metric_names:
                offenders.append(f"{path.name}: line {node.lineno} 比较了判定态字面量")
    assert not offenders, f"api.py 里出现了判定态分派（第二份真相源）：{offenders}"

"""Agent Skill 的 Python 级入口：``run(argv)`` → 信封（出口码 + 两路文本）。

**这一层刻意不做任何判定**。它只做三件事：把 argv 交给呈现层、把两路输出收进信封、
把出口码原样带出来。判定态与退出码的映射仍然只有一处（``contract.exit_code_for_*``，
由 ``cli.py`` 调用）—— 在这里再写一遍 ``if verdict == ...`` 就是造第二份真相源，
而那正是 ``tests/test_report.py`` 的 AST 守门在呈现层挡下的那族缺陷。

为什么需要这一层（而不是让 Skill 直接 shell 调 CLI）：Skill 侧要的是**结构化的两路文本
加一个整数**，而不是"解析别人打印的东西"。子进程方案要处理编码、换行、stderr 分离三件事，
每一次都可能把 ``--json`` 的字节口径弄歪；在同一个解释器里把 ``cli.main`` 的输出收进
信封，字节与 ``cli`` 自己的输出**逐字节相同**，不需要第二套解析。

``plan/00`` §5 四格表点名的就是本模块的 ``run()``（K32）。
"""

from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass
from typing import Sequence

from . import cli


@dataclass(frozen=True)
class Result:
    """一次调用的信封。字段与"用户会看到什么"一一对应，不多也不少。

    ``exit_code`` 是 ``cli.main`` 的返回值（已由契约映射算好），本层**不重算**。
    """

    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        """出口码 0 = 判定完成且可唯一归因。

        **非 0 不等于出错**：``1`` 是"有答案但不可唯一归因"（正确结论），``3`` 是"算不了"，
        ``4`` 才是用法错误。判据见 ``data/README.md`` §5.1 —— 这里只提供入口码的读数，
        不替调用方解释它的含义（解释含义就是第二份口径）。
        """
        return self.exit_code == 0


def run(argv: Sequence[str] | None = None) -> Result:
    """跑一次 CLI 调用并收信封。**不打印**任何东西，输出全在返回值里。

    ``argv`` 形态与 ``cli.main`` 完全一致（``["explain", "98", "--platform", "linux"]``）；
    省略时读 ``sys.argv``，与 ``python -m errcode_atlas`` 同义。

    异常不吞：``cli.main`` 已经把用法错误/编目缺失映射成出口码，真正漏出来的只有
    本层自己的缺陷 —— 那种时候让它抛，比包一层 ``except`` 更像"这里没坏"。
    """
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return Result(exit_code=code, stdout=out.getvalue(), stderr=err.getvalue())

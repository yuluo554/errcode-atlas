#!/usr/bin/env python3
"""脱敏门（发布前必跑，进 CI 的 layout job）。

为什么是"门"而不是一次性 grep（``plan/06`` R6）：

* 发布前必须 0 命中，发布**之后**任何一次改动都可能把本机路径带回来；
* 判据必须可跑红 —— 命中时逐行打印 ``文件:行: [规则] 原文``，不静默通过；
* **判据有几条，变异就做几组**（本门 4 条规则，``tools/verify_gates.py`` 逐组验红）。

三条实测口径（写规则前先读）：

1. **占位符必须放行**：``C:\\Users\\<user>`` / ``<repo>`` / ``<local-proxy>`` 是脱敏后的正确写法，
   判据用负向前瞻排除，否则"已脱敏"会被判成"未脱敏"。
2. **公开镜像不是私有代理**：``pypi.tuna.tsinghua.edu.cn`` 之类不在判据内；只认回环/私网地址。
3. **门要豁免自己**：本文件必须写出被判据禁止的字面量（规则本身）；豁免按**文件集合**显式列，
   并把豁免份数打进结论行。

扫描面 = "仓库内容"，不是"本地环境"：凡 ``.gitignore`` 声明的本地产物/环境目录，都必须在这里有对应项
（否则本地不红、CI 里建了那个 venv 就红）。名字随包名变的产物用**后缀规则**。

退出码：``0`` 零命中 / ``1`` 有命中 / ``2`` 用法错误。
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]

#: 自豁免面 = **文件集合**，不是单个文件名（项目里常有 .mjs 与 .py 两版门）。
SELF_EXEMPT = frozenset({"tools/check_desensitized.py"})

#: 不扫的目录。**必须与 ``.gitignore`` 的目录级忽略逐项对齐**（``tests/test_gate_alignment.py``
#: 双向断言）：被 ``.gitignore`` 忽略的目录**不可能是仓库内容**，所以跳过它藏不了任何东西；
#: 反过来漏掉一项，就是"本地绿、CI 建出该目录就红"那一族。
SKIP_DIRS = frozenset(
    {
        ".git",  # 目录形态；worktree 里是文件，靠下面的 name == ".git" 一起挡
        # ── 本项目自己的本地产物 ──
        ".mimosa",
        "_headers",
        "_private",
        ".errcode-atlas",
        "tmp",
        "_scratch",
        # ── 虚拟环境 / 构建产物 ──
        ".venv",
        ".venv-readme",
        "venv",
        "ENV",
        "env",
        "build",
        "dist",
        "dist-release",
        "release",
        "sdist",
        "wheels",
        "eggs",
        ".eggs",
        "develop-eggs",
        "downloads",
        "parts",
        "var",
        "lib",
        "lib64",
        # ── 测试 / 覆盖率 / 编辑器缓存 ──
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".cache",
        "__pycache__",
        "coverage",
        "htmlcov",
        ".hypothesis",
        ".tox",
        ".nox",
        ".tmp",
        "node_modules",
        ".vscode",
        ".idea",
    }
)
SKIP_SUFFIXES = (".egg-info", ".dist-info")
SKIP_EXTS = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".gz", ".exe",
        ".dll", ".pdf", ".woff", ".woff2", ".mp4", ".pyc",
    }
)

#: 四条规则。每条对应 ``tools/verify_gates.py`` 里的一组变异。
#:
#: ``allow`` 是**逐条规则的放行判据**（不是全局白名单）：命中的片段必须再过它一次才算违规。
#: 盘符路径那条正是靠它放行 ``C:\\Users\\<user>`` 这类脱敏后的正确写法 ——
#: 用纯正则的负向前瞻做不到（占位符不在盘符后面那一段，而在更深处），
#: 而放宽成"任意盘符 + 非空路径"又会把合法写法判红（本项目实测：``D:/somewhere/leaked``
#: 这样的真实泄露在窄正则下**永远抓不到**）。判别 = **"这条正则错过的那一类，我测过吗？"**
@dataclass(frozen=True)
class Rule:
    id: str
    pattern: re.Pattern[str]
    #: ``allow(line, match) -> True`` 表示"这个命中是脱敏后的合法写法"，放行。
    allow: Callable[[str, "re.Match[str]"], bool] = lambda _line, _m: False


def _placeholder_follows(line: str, match: "re.Match[str]") -> bool:
    """``C:\\Users\\<user>\\x`` 这类写法：路径在 ``<`` 处被正则截断，**后面紧跟占位符**。

    判据必须看"命中之后就接着 ``<…>``"，而不是"整行里出现过 ``<``" ——
    后者会让"真路径 + 别处的占位符"混在同一行时被整行放行（那才是真泄露）。
    """
    rest = line[match.end() :]
    return rest.startswith("<") and ">" in rest


RULES: tuple[Rule, ...] = (
    Rule(
        # 盘符绝对路径。**不限定顶层目录名**（限定就会漏 `D:/somewhere/…` 这类真泄露），
        # 改用 allow 放行含 `<...>` 占位符的脱敏写法。
        "absolute-session-path",
        re.compile(r"\b[A-Za-z]:[\\/](?:[^\s<>|]*[\\/])?[^\s<>|]*"),
        allow=_placeholder_follows,
    ),
    Rule(
        # Git Bash 形态 `/c/Users/<name>/…`（同样是占位符放行）
        "msys-user-path",
        re.compile(r"/[a-z]/Users/(?!<)[A-Za-z0-9._-]+/"),
    ),
    Rule(
        # 本机用户名（换机器要改这一行；别用环境实算 —— runner 上不叫这个）
        "host-username",
        re.compile(r"\bASUS\b"),
    ),
    Rule(
        # 回环代理端口；私网段同理：`\b192\.168\.\d+\.\d+:\d+\b`
        "loopback-proxy",
        re.compile(r"\b127\.0\.0\.1:\d{2,5}\b"),
    ),
)


def walk(directory: Path):
    for entry in sorted(directory.iterdir()):
        if entry.name == ".git":
            continue  # 目录形态与 worktree 文件形态一起挡
        if entry.is_dir():
            if entry.name in SKIP_DIRS or entry.name.endswith(SKIP_SUFFIXES):
                continue
            yield from walk(entry)
            continue
        if not entry.is_file():
            continue
        if entry.suffix in SKIP_EXTS:
            continue
        yield entry


def scan() -> tuple[list[str], int]:
    hits: list[str] = []
    scanned = 0
    for path in walk(ROOT):
        rel = path.relative_to(ROOT).as_posix()
        if rel in SELF_EXEMPT:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "\x00" in text:
            continue  # 二进制
        scanned += 1
        for lineno, line in enumerate(text.split("\n"), start=1):
            for rule in RULES:
                hit = rule.pattern.search(line)
                if hit is None or rule.allow(line, hit):
                    continue
                hits.append(f"{rel}:{lineno}: [{rule.id}] {line.strip()[:160]}")
    return hits, scanned


def main(argv: list[str] | None = None) -> int:
    unknown = [a for a in (argv if argv is not None else sys.argv[1:])]
    if unknown:
        sys.stderr.write(f"check-desensitized: unknown argument {unknown[0]}\n")
        return 2

    hits, scanned = scan()
    if hits:
        sys.stdout.write(
            f"脱敏门：{len(hits)} 处命中（扫了 {scanned} 个文本文件，豁免 {len(SELF_EXEMPT)} 份）\n"
        )
        for hit in hits:
            sys.stdout.write(f"FAIL  {hit}\n")
        return 1
    sys.stdout.write(
        f"脱敏门：扫了 {scanned} 个文本文件，0 命中（豁免 {len(SELF_EXEMPT)} 份）\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
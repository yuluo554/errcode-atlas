"""搬运层守门：`.gitignore` 声明的本地目录，必须 1:1 出现在脱敏门的 `SKIP_DIRS` 里。

为什么这是一条门而不是一句建议：脱敏门的扫描面是"仓库内容"，而 CI 步骤是有状态的管道。
`.gitignore` 里声明了某个本地目录、但门没跳过它 → **本地永远绿**（该目录在本地被忽略、
或干脆不存在），**CI 一旦建出该目录就红**（命中的还是它自带的文档示例）。这是实测过的一族。

判据两个方向都查（不是单向包含）：

* `.gitignore` 声明的目录 → 必须在 `SKIP_DIRS` 里（否则 CI 会红）；
* `SKIP_DIRS` 里的目录 → 必须能在 `.gitignore` 找到出处或被登记为"工具自带产物"（否则
  门在悄悄放宽扫描面，而没有任何东西会红）。

"工具自带产物"（如 `.git`、`__pycache__`、缓存目录）登记成显式集合，改动时要跟着改这里。
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GITIGNORE = REPO_ROOT / ".gitignore"

#: 工具自带产物：不需要 `.gitignore` 有对应行（git 本身 / 解释器缓存 / 门自己的临时产物）。
TOOL_OWNED = frozenset(
    {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".cache",
        ".tmp",
        "_scratch",
        "dist",
        "dist-release",
        "release",
        "build",
        "coverage",
        "node_modules",
        ".venv",
        ".venv-readme",
    }
)

#: `.gitignore` 里参加对账的形态：**目录级**忽略（`name/` 或 `/name/`）。
#: 纯文件名忽略（`*.tmp`）不参与 —— 它们不是"会被 CI 建出来的目录"。
DIR_IGNORE = re.compile(r"^/?(?P<name>[^\s#/*][^\s/]*)/$")


def _ignored_dirs() -> set[str]:
    names: set[str] = set()
    for raw in GITIGNORE.read_text(encoding="utf-8").split("\n"):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        match = DIR_IGNORE.match(line)
        if match:
            names.add(match.group("name"))
    return names


def _load_desens():
    path = REPO_ROOT / "tools" / "check_desensitized.py"
    name = "_gate_desens_for_alignment"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


def test_gitignore_declares_at_least_one_dir() -> None:
    """非空跑自证：一条目录级忽略都没读到 = 判据是空的。"""
    assert _ignored_dirs(), ".gitignore 里没解析到任何目录级忽略 —— 解析口径对不上了"


@pytest.mark.parametrize("name", sorted(_ignored_dirs() - TOOL_OWNED))
def test_every_gitignored_dir_is_skipped_by_desens_gate(name: str) -> None:
    """`.gitignore` 声明的本地目录必须被门跳过（否则 CI 会红、本地不会）。"""
    module = _load_desens()
    assert name in module.SKIP_DIRS, (
        f"`.gitignore` 忽略了 `{name}/`，但脱敏门的 SKIP_DIRS 没有它 —— "
        "CI 建出这个目录时会把里面自带的文档示例扫成命中"
    )


def test_desens_gate_does_not_skip_repository_content() -> None:
    """反方向：SKIP_DIRS 里每一项都必须有出处（`.gitignore` 或 TOOL_OWNED 登记）。"""
    module = _load_desens()
    unexplained = set(module.SKIP_DIRS) - _ignored_dirs() - TOOL_OWNED
    assert not unexplained, (
        f"这些目录被门跳过，但既不在 `.gitignore` 也没有登记为工具自带产物：{sorted(unexplained)}"
        " —— 门在悄悄放宽扫描面"
    )


#: 发布/构建产物目录：它们是**生成物**，必须同时满足两件事才不留缺口 ——
#: ① 被 `.gitignore` 封（`git add -A` 吞不进来）；② 被脱敏门跳过（不会把里面的示例扫成命中）。
PUBLISH_ARTIFACT_DIRS = ("dist-release", "dist", "build")


def test_publish_artifact_dirs_are_ignored_and_skipped() -> None:
    """**发布产物目录必须双向对齐**（M6 实测的真缺口）。

    本项目踩到的形态：`dist-release/` 早在脱敏门的 `SKIP_DIRS` 里，却**不在 `.gitignore`**。
    对齐测试只查了「gitignore → 门」一个方向，于是这个缺口两个方向都看不见 ——
    收尾时 `git add -A` 把 2.6 MB 的附件与回下载件一起提交了进去。
    附件是 tag 树的派生件、已在 Release 上；入库等于同一份内容存三遍。

    判据 = 「**生成物目录**两个方向都必须在」：既不能被 git 吞进来，也不能被门扫。
    """
    module = _load_desens()
    problems: list[str] = []
    declared = _ignored_dirs()
    for name in PUBLISH_ARTIFACT_DIRS:
        if name not in declared:
            problems.append(f"{name}/ 不在 `.gitignore` 的目录级忽略里（`git add -A` 会吞进去）")
        if name not in module.SKIP_DIRS:
            problems.append(f"{name}/ 不在脱敏门的 SKIP_DIRS 里（门会扫生成物）")
    assert not problems, "；".join(problems)


def test_release_attachments_are_not_tracked_in_git() -> None:
    """附件是 **tag 树的派生件**，不许入仓 —— 判据问的是 git 索引，不是磁盘。"""
    import subprocess

    proc = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        pytest.skip("不是 git 树（导出树里没有索引可比）—— 那正是『附件不入仓』的终态")
    tracked = [
        line
        for line in proc.stdout.split("\n")
        if line.strip()
        and (line.startswith("dist-release/") or line.endswith(".zip") or line == "SHA256SUMS")
    ]
    assert not tracked, (
        "这些发布产物进了 git 索引（应是本地产物，只在 Release 上）：\n" + "\n".join(tracked)
    )
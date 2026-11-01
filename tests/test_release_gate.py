"""发布门本身的测试：三档必须可跑、结论可读、且**红在正确的分支**上。

变异验证（``tools/verify_gates.py`` 的 R1–R7）覆盖"门会变红"；这里补的是另一半：

* 三档都能被程序调用（``--pre-tag`` / ``--offline`` / ``--online``），退出码语义与另两道门一致；
* 结论行**逐项**可读（"本轮实检 N 项 / 不适用 M 项"必须真打印，否则"全绿"与"什么都没查"同形）；
* 每个判据函数**单独**可红 —— 判据逻辑抽出来直测，不靠"整棵树的状态"偶然成立。
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "tools" / "check_release.py"


def _run(*args: str) -> subprocess.CompletedProcess:
    """**必须继承 os.environ**：只传 PYTHONPATH 会剪掉 SYSTEMROOT（见 test_gates.py 同款注释）。"""
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def _load():
    """动态加载工具模块（先登记进 ``sys.modules``，``@dataclass`` 才不会炸）。"""
    name = "_release_gate_under_test"
    spec = importlib.util.spec_from_file_location(name, GATE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


# ── 三档可跑 + 退出码语义 ────────────────────────────────────────────────────
@pytest.mark.parametrize("flag", ["--pre-tag", "--offline", "--online"])
def test_each_mode_is_runnable_and_reports_every_item(flag: str) -> None:
    """三档都必须**跑得完**（不崩），并打印逐项结论 + 计数行。

    ``--online`` 在本机可能因无远端而红 —— 那是正确结论，不是崩溃。
    判据只要求"退出码在 0/1 之内 + 结论可读"，不要求绿（绿与否取决于远端事实）。
    """
    proc = _run(flag)
    assert proc.returncode in (0, 1), proc.stdout + proc.stderr
    assert "发布门（" in proc.stdout, "没打印档位标题"
    assert "本轮实检" in proc.stdout, "缺非空跑自证计数行"
    assert "不适用" in proc.stdout, "缺『不适用均写明原因』的计数"
    assert "结论:" in proc.stdout


def test_unknown_argument_returns_usage_error() -> None:
    assert _run("--nope").returncode == 2


def test_no_mode_returns_usage_error() -> None:
    """三档是**必选一**（互斥组）：一个都不给 = 用法错误，不是"随便挑一档"。"""
    assert _run().returncode == 2


def test_modes_are_mutually_exclusive() -> None:
    assert _run("--pre-tag", "--offline").returncode == 2


def test_pre_tag_gate_is_green_on_current_tree() -> None:
    """tag 之前这一档在当前树上必须绿（留档已落盘、名字占用已记、版本两处相等）。"""
    proc = _run("--pre-tag")
    assert proc.returncode == 0, proc.stdout + proc.stderr


# ── 判据函数单独可红（不依赖整棵树的状态）────────────────────────────────────
def test_doc_check_rejects_missing_two_column_structure() -> None:
    module = _load()
    original = module.read
    try:
        module.CHECKS.clear()
        module.read = lambda rel: "## 一、tag 前事实\n\n| 实现 | 1 |\n| 实现 | 2 |\n| 实现 | 3 |\n"
        module.check_doc()
    finally:
        module.read = original
    verdicts = [c for c in module.CHECKS if c[0] == "RELEASE.DOC"]
    assert verdicts and not verdicts[-1][1]
    assert "两栏" in verdicts[-1][2], verdicts[-1][2]


def test_doc_check_rejects_all_noop_states() -> None:
    """三态表全是"不适用"时也必须红 —— 拿三态表当免票 = 什么都没表态。"""
    module = _load()
    original = module.read
    body = (
        "## 一、tag 前事实\n## 二、tag 后追加\n## 覆盖对账\n\n"
        "| 不适用 | a |\n| 不适用 | b |\n| 不适用 | c |\n"
    )
    try:
        module.CHECKS.clear()
        module.read = lambda rel: body
        module.check_doc()
    finally:
        module.read = original
    verdicts = [c for c in module.CHECKS if c[0] == "RELEASE.DOC"]
    assert verdicts and not verdicts[-1][1]
    assert "实现" in verdicts[-1][2], f"红是红了，但没点到『没有实现态』: {verdicts[-1][2]}"


def test_doc_check_rejects_multi_state_rows() -> None:
    """一行同时挂两态 = 没表态，必须红（这一支与"某态 0 行"是两个独立分支）。"""
    module = _load()
    original = module.read
    body = (
        "## 一、tag 前事实\n## 二、tag 后追加\n## 覆盖对账\n\n"
        "| 实现 待首推 | 两态同行 |\n| 实现 | b |\n| 不适用 | c |\n"
    )
    try:
        module.CHECKS.clear()
        module.read = lambda rel: body
        module.check_doc()
    finally:
        module.read = original
    verdicts = [c for c in module.CHECKS if c[0] == "RELEASE.DOC"]
    assert verdicts and not verdicts[-1][1]
    assert "多个标签" in verdicts[-1][2], verdicts[-1][2]


def test_self_reference_check_flags_sha_in_tag_before_column() -> None:
    """§一 里出现附件 sha256 必须红 —— 那是 tag 之后才知道的事实（K33）。"""
    module = _load()
    original = module.read
    sha = "0123456789abcdef" * 4
    body = f"## 一、tag 前事实\n\n附件 sha256: {sha}\n\n## 二、tag 后追加\n\n待追加\n"
    try:
        module.CHECKS.clear()
        module.read = lambda rel: body
        module.check_self_reference("v0.1.0")
    finally:
        module.read = original
    verdicts = [c for c in module.CHECKS if c[0] == "RELEASE.TREE"]
    assert verdicts and not verdicts[-1][1], verdicts
    assert "§一" in verdicts[-1][2], verdicts[-1][2]


def test_self_reference_check_allows_empty_skeleton() -> None:
    """阴性对照：骨架原样（§二 全是"待追加"）必须绿 —— 否则门会逼着提前填数字。"""
    module = _load()
    original = module.read
    body = "## 一、tag 前事实\n\n无自指值。\n\n## 二、tag 后追加\n\n| 附件 sha256 | 待追加 |\n"
    try:
        module.CHECKS.clear()
        module.read = lambda rel: body
        module.check_self_reference("v0.1.0")
    finally:
        module.read = original
    verdicts = [c for c in module.CHECKS if c[0] == "RELEASE.TREE"]
    assert verdicts and verdicts[-1][1], verdicts[-1][2]


def test_name_occupancy_check_requires_a_recheck_date() -> None:
    """名字核对记录必须**带日期** —— 否则分不清它和 `plan/06` §4.1 的旧快照。"""
    module = _load()
    original = module.read
    body = "## 一、tag 前事实\n\nGitHub 0 命中；PyPI 404。\n\n## 二、tag 后追加\n"
    try:
        module.CHECKS.clear()
        module.read = lambda rel: body
        module.check_name_occupancy()
    finally:
        module.read = original
    verdicts = [c for c in module.CHECKS if c[0] == "RELEASE.NAME"]
    assert verdicts and not verdicts[-1][1], verdicts
    assert "日期" in verdicts[-1][2], verdicts[-1][2]


def test_version_two_sources_must_agree() -> None:
    """版本两处不等 = 红（tag 名由它推出，两处漂移会让附件名与 tag 名错位）。"""
    module = _load()
    original = module.version_from_pyproject
    try:
        module.CHECKS.clear()
        module.version_from_pyproject = lambda: "9.9.9"
        module.check_version()
    finally:
        module.version_from_pyproject = original
    verdicts = [c for c in module.CHECKS if c[0] == "RELEASE.VERSION"]
    assert verdicts and not verdicts[-1][1], verdicts


def test_gate_never_uses_shell_true() -> None:
    """命令一律走字面量参数列表（``shell=False``）—— 判据是 AST，不是文本搜索。"""
    import ast

    tree = ast.parse(GATE.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "shell":
                    offenders.append(f"line {node.lineno}: shell={ast.dump(keyword.value)[:40]}")
    assert not offenders, f"check_release.py 出现了 shell= 参数：{offenders}"


def test_zip_comparison_detects_a_differing_byte(tmp_path: Path) -> None:
    """``compare_zip_to_tag`` 必须真比字节 —— 大小相同但内容不同的文件要被抓到。"""
    import zipfile

    module = _load()
    asset = tmp_path / "x.zip"
    with zipfile.ZipFile(asset, "w") as archive:
        archive.writestr("a.txt", "content-A\n")
    # 造一份与 tag 树"名字相同、字节不同"的清单，直接喂给比较函数的下半段
    original = module._tag_tree_files
    try:
        module._tag_tree_files = lambda tag: {"a.txt"}
        # `git cat-file blob v0.1.0:a.txt` 在真仓里读不到 —— 那一支会报"读不出来"，
        # 同样是红。为精确测"字节不同"这一支，这里让 cat-file 返回别的内容。
        real_run = module.run_cmd

        def fake_run(cmd, *, text=True):
            class _R:
                returncode = 0
                stdout = b"content-B\n"

            return _R()

        module.run_cmd = fake_run
        problems = module.compare_zip_to_tag("v0.1.0", asset)
        assert problems, "大小相同但字节不同，比较函数却说一致"
        assert any("字节" in p for p in problems), problems
    finally:
        module._tag_tree_files = original
        module.run_cmd = real_run
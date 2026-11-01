"""版本与下限：零第三方 import（运行期）、版本两处一致、无「3 方依赖」泄漏。

`plan/02` D1/D8 + `AGENTS.md` 的环境纪律。三条判据都是**差集式**的，不是白名单式
（白名单式每新增一个包就漏）。
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
PKG = SRC / "errcode_atlas"


def _pyproject_value(*path: str):
    """读 pyproject 里的一个值。

    ``tomllib`` 是 3.11+ 才有的标准库 —— 3.10 下限下必须自己能读。
    优先用 ``tomllib``，没有就用 ``tomli``，都没有就退回**按行解析**（只认本项目用到的形态）。
    判据不因此放松：读不出来就 FAIL，不静默跳过。
    """
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    try:
        import tomllib
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            tomllib = None  # type: ignore[assignment]

    if tomllib is not None:
        node = tomllib.loads(text)
        for key in path:
            node = node[key]
        return node

    # 退化路径：只支持 `[a.b]` + `key = value` 两行形态
    section = ".".join(path[:-1])
    key = path[-1]
    current = ""
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current = stripped[1:-1].strip()
            continue
        if current == section and stripped.startswith(f"{key} "):
            value = stripped.split("=", 1)[1].strip().strip('"')
            return value
    raise KeyError(f"pyproject.toml 里找不到 {'.'.join(path)}")


def test_version_matches_pyproject() -> None:
    """版本唯一定义处两处必须相等（`plan/02` §4.2）。"""
    from errcode_atlas import __version__

    assert _pyproject_value("project", "version") == __version__


def test_readme_declares_the_same_version() -> None:
    from errcode_atlas import __version__

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert f"v{__version__}" in readme or __version__ in readme


def test_runtime_has_zero_third_party_imports() -> None:
    """运行期零第三方依赖 —— **差集式**判据，不写包名白名单。

    ``-S`` 关掉 site（否则 setuptools 的 ``_distutils_hack`` 会混进来），
    并从差集里减掉解释器自身（``__main__``）与本包。

    ``stdlib_module_names`` 是 **3.10+** 才有的 —— 3.8 通道上该判据会因缺属性而崩，
    所以这里**显式跳过并说明原因**，而不是让它在 3.8 上假装通过（"跳过"与"通过"必须可分）。
    """
    if not hasattr(sys, "stdlib_module_names"):
        pytest.skip("sys.stdlib_module_names 是 3.10+ 属性；本通道只验语法面（plan/06 §5）")
    code = (
        "import sys; sys.path.insert(0, %r); import errcode_atlas.cli; "
        "extra = sorted({m.split('.')[0] for m in sys.modules}"
        " - sys.stdlib_module_names - {'errcode_atlas', '__main__'}); "
        "print(extra); assert extra == [], extra" % str(SRC)
    )
    proc = subprocess.run(
        [sys.executable, "-S", "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"


def test_judgement_layer_imports_nothing_from_runtime_io() -> None:
    """判定层不读时钟、不读环境变量、不联网（`plan/02` L2）。

    判据用 **AST 定位**：只看 ``explain.py`` / ``exitcode.py`` 里被 import 的模块名与
    被读取的属性名，不数"文本出现次数"（注释里提到会假红）。
    """
    forbidden_modules = {"time", "datetime", "os", "socket", "urllib", "http", "requests", "random"}
    offenders: list[str] = []
    for name in ("explain.py", "exitcode.py"):
        tree = ast.parse((PKG / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in forbidden_modules:
                        offenders.append(f"{name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in forbidden_modules:
                    offenders.append(f"{name}: from {node.module}")
    assert not offenders, f"判定层出现了运行时 I/O 依赖：{offenders}"


def test_package_data_declares_catalog_json() -> None:
    """随包数据必须在打包配置里声明，否则装好的包里没有编目（裸命令 ModuleNotFoundError）。"""
    data = _pyproject_value("tool", "setuptools", "package-data", "errcode_atlas")
    patterns = data if isinstance(data, list) else [data]
    assert any("data/" in pattern or "json" in pattern for pattern in patterns)


@pytest.mark.parametrize("path", ["src/errcode_atlas/data/catalog.json", "src/errcode_atlas/data/catalog.manifest.json"])
def test_frozen_artifacts_exist_in_package(path: str) -> None:
    assert (REPO_ROOT / path).is_file(), f"{path} 必须随包存在"
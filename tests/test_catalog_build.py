"""生成器冻结态：`tools/build_catalog.py --out` → `--check` 必须逐字节稳定。

三条判据（plan/04 §3）：

1. 双跑逐字节一致（确定性）；
2. `--check` 与仓库冻结件一致（冻结态未漂）；
3. 自检挂在 ``build()`` 的调用链上，不挂在 ``__main__``（`plan/05`「自检挂错位置」）。
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPO_ROOT / "tools" / "build_catalog.py"
FROZEN = REPO_ROOT / "src" / "errcode_atlas" / "data" / "catalog.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_catalog_mod", BUILD_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={
            **os.environ,
            "PYTHONPATH": str(REPO_ROOT / "src"),
            "PYTHONUTF8": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )


def test_check_passes_on_repo_frozen_artifact():
    proc = _run("--check")
    assert proc.returncode == 0, proc.stderr
    assert "一致" in proc.stderr


def test_check_reports_non_empty_scan():
    """空跑自证：结论行必须报出"读到了几个源文件"。"""
    proc = _run("--check")
    assert "个源文件" in proc.stderr
    assert " 0 个源文件" not in proc.stderr


def test_double_build_is_byte_identical(tmp_path):
    first = tmp_path / "a"
    second = tmp_path / "b"
    assert _run("--out", str(first)).returncode == 0
    assert _run("--out", str(second)).returncode == 0
    assert (first / "catalog.json").read_bytes() == (second / "catalog.json").read_bytes()
    assert (
        first / "catalog.manifest.json"
    ).read_bytes() == (second / "catalog.manifest.json").read_bytes()


def test_manifest_digest_matches_catalog(tmp_path):
    assert _run("--out", str(tmp_path)).returncode == 0
    from errcode_atlas.catalog import sha256_of_text

    body = (tmp_path / "catalog.json").read_text(encoding="utf-8")
    manifest = json.loads((tmp_path / "catalog.manifest.json").read_text(encoding="utf-8"))
    assert manifest["sha256"] == sha256_of_text(body)


def test_frozen_catalog_is_valid_json_and_loadable():
    from errcode_atlas.catalog import load

    catalog = load()
    assert catalog.schema_version >= 1
    assert isinstance(catalog.entry_count(), dict)


def test_entry_count_in_frozen_matches_actual_entries():
    """分母由构造算出，不与手写常量对账 —— 这里验"冻结件里那个数字确实是数出来的"。"""
    from errcode_atlas.catalog import load

    catalog = load()
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    assert frozen["entry_count"] == catalog.entry_count()


def test_self_check_is_on_build_chain():
    """自检必须能被 ``collect()`` 触发 —— 挂在 ``__main__`` 等于在门下从不执行。

    判据 = 把源目录指向空目录，`collect()` 应抛 `SourceError`（自检里那条"0 个源文件"）。
    """
    module = _load_module()
    original = module.SOURCES_DIR
    try:
        module.SOURCES_DIR = REPO_ROOT / "does-not-exist"
        with pytest.raises(module.SourceError):
            module.collect()
    finally:
        module.SOURCES_DIR = original


def test_usage_error_without_out_or_check_is_two():
    proc = _run()
    assert proc.returncode == 2


def test_missing_source_file_yields_three():
    module = _load_module()
    original = module.SOURCES_DIR
    try:
        module.SOURCES_DIR = REPO_ROOT / "does-not-exist"
        assert module.main(["--check"]) == 3
    finally:
        module.SOURCES_DIR = original
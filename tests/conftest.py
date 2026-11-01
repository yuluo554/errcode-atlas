"""测试夹具：让 `pytest` 在**没装包**的仓库树里也能 import 到 ``errcode_atlas``。

为什么需要它：本仓是 ``src`` 布局，未 ``pip install`` 时仓库根不在 ``sys.path`` 上。
CI 的每个 job 都会设 ``PYTHONPATH=src``；本文件让本地 ``py -3.12 -m pytest`` 也能跑，
**且不用装包**——这样"解包树里跑测试"这条路（无 ``.git``、无 site-packages）也成立。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
# `tests/` 无 `__init__.py` 布局：同目录的 helpers.py 需要 tests/ 本身在 sys.path 上
TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))


@pytest.fixture
def write_catalog(tmp_path):
    """造一份临时冻结编目，返回路径。**不写 manifest**（验"无 manifest 时不做摘要校验"）。"""

    def _write(payload: dict) -> Path:
        body = {
            "schema_version": 1,
            "generator_version": "test",
            "platforms": payload.get("platforms", {}),
        }
        path = tmp_path / "catalog.json"
        path.write_text(
            json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    return _write
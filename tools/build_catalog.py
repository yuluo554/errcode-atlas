"""生成侧：``data/catalog/*.yaml``（唯一编目真相源）→ 冻结 JSON（随包）。

**dev 侧工具**，需要 PyYAML；运行期只读它产出的 JSON（``plan/02`` D2）。
本文件只做形状变换 + 校验，**不做任何语义判定** —— 判定只在 ``src/errcode_atlas`` 里发生。

用法::

    py -3.12 tools/build_catalog.py --out src/errcode_atlas/data
    py -3.12 tools/build_catalog.py --check        # 与仓库冻结件逐字节比对

退出码：``0`` 一致 / ``1`` 不一致（逐条打印差异）/ ``2`` 用法错误 / ``3`` 源不可用。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from errcode_atlas import __version__, contract  # noqa: E402
from errcode_atlas.catalog import (  # noqa: E402
    CATALOG_PATH,
    MANIFEST_PATH,
    sha256_of_text,
)

SOURCES_DIR = REPO_ROOT / "data" / "catalog"
SCHEMA_VERSION = 1

#: 平台轴向 -> 源文件名。文件名与平台值分离：``win32-node.yaml`` 提供 ``win32-node`` 平台。
PLATFORM_FILES = {
    "linux": "linux.yaml",
    "macos": "macos.yaml",
    "win32-node": "win32-node.yaml",
    "win32-python": "win32-python.yaml",
}

#: 跨平台共享的域文件（不绑平台轴）。M2 落位。
SHARED_FILES = {
    "sysexits.yaml": "exit",
    "node-errors.yaml": "errno",
}


class SourceError(RuntimeError):
    """源不可用或结构非法。"""


def _require(yaml, path: Path) -> Any:  # noqa: ANN001
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SourceError(f"编目源不存在: {path.name}") from exc
    except yaml.YAMLError as exc:
        raise SourceError(f"{path.name} 不是合法 YAML: {exc}") from exc


def _validate_entry(raw: Any, path: Path, index: int) -> dict[str, Any]:
    from errcode_atlas.catalog import _validate_source  # 共用同一份出处契约

    where = f"{path.name}[{index}]"
    if not isinstance(raw, dict):
        raise SourceError(f"{where}: 条目必须是对象")
    for key in ("name", "domain", "value", "source"):
        if raw.get(key) in (None, ""):
            raise SourceError(f"{where}: 缺字段 {key}（无出处者不得入编目，记 data/gaps.md）")
    if raw["domain"] not in contract.DOMAINS:
        raise SourceError(f"{where}: domain={raw['domain']!r} 不在 {list(contract.DOMAINS)} 内")
    if not isinstance(raw["value"], int) or isinstance(raw["value"], bool):
        raise SourceError(f"{where}: value 必须是整数")
    try:
        _validate_source(raw["source"], where)
    except Exception as exc:  # CatalogError 与 SourceError 的统一出口
        raise SourceError(str(exc)) from exc
    return {
        "name": str(raw["name"]),
        "domain": str(raw["domain"]),
        "value": int(raw["value"]),
        "source": dict(raw["source"]),
        "description_zh": str(raw.get("description_zh", "")),
        "posix_ref": str(raw.get("posix_ref", "<none>")),
    }


def build(platforms: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """构造冻结编目。**只做形状**；索引由运行期 ``catalog.build_indexes`` 自建。"""
    entry_count: dict[str, int] = {domain: 0 for domain in contract.DOMAINS}
    for entries in platforms.values():
        for entry in entries:
            entry_count[entry["domain"]] = entry_count.get(entry["domain"], 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "generator_version": __version__,
        "entry_count": entry_count,
        "platforms": platforms,
    }


def _self_check(catalog: dict[str, Any], sources_read: int) -> None:
    """挂在 ``build()`` 的调用链上，不挂在 ``__main__``（plan/05「自检挂错位置」）。

    空跑自证：源文件数与条目数都要能被打印出来，且"读到 0 个源文件"是错误而不是合法终态。
    """
    if sources_read == 0:
        raise SourceError("一个编目源都没读到 —— 判据空跑（目录或文件名不对？）")
    declared = catalog["entry_count"]
    recomputed = {domain: 0 for domain in contract.DOMAINS}
    for entries in catalog["platforms"].values():
        for entry in entries:
            recomputed[entry["domain"]] += 1
    if declared != recomputed:
        raise SourceError(f"entry_count 与逐条计数不一致: {declared} vs {recomputed}")


def collect() -> tuple[dict[str, Any], dict[str, int]]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - dev extra 未装时的出口
        raise SourceError(
            "缺少 PyYAML：这是 dev 侧生成器的依赖，装 ./.venv/Scripts/python.exe -m pip install -e '.[dev]'"
        ) from exc

    platforms: dict[str, list[dict[str, Any]]] = {}
    stats = {"files": 0, "entries": 0}
    for platform, filename in PLATFORM_FILES.items():
        path = SOURCES_DIR / filename
        data = _require(yaml, path)
        stats["files"] += 1
        if data is None:  # 只有表头的合法初始态
            platforms[platform] = []
            continue
        if not isinstance(data, list):
            raise SourceError(f"{filename}: 顶层必须是数组")
        entries = [_validate_entry(raw, path, i) for i, raw in enumerate(data)]
        platforms[platform] = entries
        stats["entries"] += len(entries)

    catalog = build(platforms)
    _self_check(catalog, stats["files"])
    return catalog, stats


def _render(catalog: dict[str, Any]) -> tuple[str, str]:
    body = json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    manifest = {
        "schema_version": catalog["schema_version"],
        "generator_version": catalog["generator_version"],
        "entry_count": catalog["entry_count"],
        # 摘要按行尾归一后计算 —— 否则 git archive 导出树（CRLF）算出的摘要不同（plan/04 §3.1）
        "sha256": sha256_of_text(body),
    }
    return body, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build_catalog", description=__doc__)
    parser.add_argument("--out", help="输出目录（写 catalog.json + catalog.manifest.json）")
    parser.add_argument("--check", action="store_true", help="与仓库冻结件逐字节比对")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not args.out and not args.check:
        parser.print_usage()
        sys.stderr.write("build_catalog: 必须给 --out 或 --check\n")
        return 2

    try:
        catalog, stats = collect()
    except SourceError as exc:
        sys.stderr.write(f"build_catalog: {exc}\n")
        return 3

    body, manifest = _render(catalog)

    if args.check:
        if not CATALOG_PATH.is_file():
            sys.stderr.write(f"build_catalog: 冻结件不存在 {CATALOG_PATH.name}\n")
            return 1
        actual = CATALOG_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")
        if actual != body:
            sys.stderr.write(
                f"build_catalog: 冻结编目与源不一致（源 {stats['files']} 个文件 / "
                f"{stats['entries']} 条）\n"
            )
            for line in _diff_lines(actual, body):
                sys.stderr.write(line + "\n")
            return 1
        sys.stderr.write(
            f"build_catalog: 一致（读 {stats['files']} 个源文件 / {stats['entries']} 条条目；"
            f"条目分布 {catalog['entry_count']}）\n"
        )
        return 0

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "catalog.json").write_bytes(body.encode("utf-8"))
    (out_dir / "catalog.manifest.json").write_bytes(manifest.encode("utf-8"))
    sys.stderr.write(
        f"build_catalog: 写出 {out_dir.name}/catalog.json（{stats['files']} 个源文件 / "
        f"{stats['entries']} 条；条目分布 {catalog['entry_count']}）\n"
    )
    return 0


def _diff_lines(left: str, right: str) -> list[str]:  # pragma: no cover - 失败诊断
    import difflib

    return list(
        difflib.unified_diff(
            left.splitlines(), right.splitlines(), fromfile="冻结件", tofile="重新生成", lineterm=""
        )
    )[:40]


if __name__ == "__main__":
    raise SystemExit(main())
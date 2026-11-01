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

#: 跨平台共享的域文件（不绑平台轴）。**M2 接线完成**：``collect()`` 现在真读它们。
#:
#: 每条共享条目会在 manifest 里记 **`spread_to`**（挂到哪几个平台轴），并在冻结编目的
#: 每个平台下各出现一次 —— 因为判定层的索引是 `platform -> domain -> …` 的。
#:
#: **为什么必须是四个轴全挂**（K20）：`covered_platforms("exit")` 是这个域的**分母**。
#: 只挂一个轴 → 分母只有 1 个平台 → `explain 64 --domain exit` 未给平台时会判
#: `UNAMBIGUOUS`（假唯一）；而挂到别的平台时若漏了某个轴，那个平台会被算成
#: "查过、没有这个值" → 假 `PLATFORM-ABSENT`。sysexits 对四个平台的进程都成立，
#: 所以四个轴全挂才是事实，不是凑数。
SHARED_FILES = {
    "sysexits.yaml": "exit",
    "node-errors.yaml": "node",
}

#: 共享条目在冻结编目里**按平台重复计入** `entry_count` 会被看成"条目数暴涨"。
#: 所以 manifest 单列 `distinct_count`（按 `(domain, name)` 去重），`entry_count` 保持
#: "每个平台轴上各有多少条"的原语义 —— 两个分母各有用途，不许互相顶替。
SHARED_SPREAD: dict[str, tuple[str, ...]] = {
    "sysexits.yaml": contract.PLATFORMS,
    # Node 的 `ERR_*` 是 **Node 运行时**抛的码：Linux/macOS 上的 Node 也抛同一批码，
    # 但 Python 视角不会 —— 所以挂三个轴，`win32-python` 不挂。
    # 这不是"少挂了一个"，是"那个平台上根本没有这套码"（`PLATFORM-ABSENT` 的正确素材）。
    "node-errors.yaml": ("linux", "macos", "win32-node"),
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
    for key in ("name", "domain", "source"):
        if raw.get(key) in (None, ""):
            raise SourceError(f"{where}: 缺字段 {key}（无出处者不得入编目，记 data/gaps.md）")
    if raw["domain"] not in contract.DOMAINS:
        raise SourceError(f"{where}: domain={raw['domain']!r} 不在 {list(contract.DOMAINS)} 内")

    # `value` 的两种合法形态，**由域决定**（K23 的结构面）：
    #  * 无值域（`node`）：`ERR_*` 只有字符串码名，`value` 必须**缺省**；
    #  * 其余域：必须是非布尔的整数（不许 `"11"` 这类字符串，也不许 `True`）。
    if str(raw["domain"]) in contract.VALUELESS_DOMAINS:
        if raw.get("value") is not None:
            raise SourceError(
                f"{where}: domain={raw['domain']!r} 是无值域（只有名字），不许写 value"
            )
        value: int | None = None
    else:
        if not isinstance(raw["value"], int) or isinstance(raw["value"], bool):
            raise SourceError(f"{where}: value 必须是整数")
        value = int(raw["value"])

    try:
        _validate_source(raw["source"], where)
    except Exception as exc:  # CatalogError 与 SourceError 的统一出口
        raise SourceError(str(exc)) from exc
    return {
        "name": str(raw["name"]),
        "domain": str(raw["domain"]),
        "value": value,
        "source": dict(raw["source"]),
        "description_zh": str(raw.get("description_zh", "")),
        "posix_ref": str(raw.get("posix_ref", "<none>")),
    }


def build(
    platforms: dict[str, list[dict[str, Any]]],
    shared: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    """构造冻结编目。**只做形状**；索引由运行期 ``catalog.build_indexes`` 自建。

    ``shared`` 是 ``文件名 -> 挂到哪几个平台轴``（即 ``SHARED_SPREAD``）。
    传进来的 ``platforms`` 已含**展开后的**共享条目，所以这里不需要知道"哪条是共享的"。

    两个分母，各有用途，**不许互相顶替**：

    * ``entry_count``：**逐平台轴**计数 —— 回答"每个平台各有多少条"，与编目文件里
      实际写下的条目数一致（共享条目在四个轴各出现一次，就各计一次）；
    * ``distinct_count``：按 ``(domain, name)`` 去重 —— 回答"这个域一共收录了多少个
      不同的名字"。共享文件被重复展开时，前者会变大而后者不变；把它们混成一个数，
      "条目数 × 平台数"就会被当成"收录了这么多条"。
    """
    entry_count: dict[str, int] = {domain: 0 for domain in contract.DOMAINS}
    distinct: dict[str, set[tuple[str, str]]] = {domain: set() for domain in contract.DOMAINS}
    for entries in platforms.values():
        for entry in entries:
            entry_count[entry["domain"]] = entry_count.get(entry["domain"], 0) + 1
            distinct.setdefault(entry["domain"], set()).add((entry["domain"], entry["name"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "generator_version": __version__,
        "entry_count": entry_count,
        "distinct_count": {
            domain: len(names) for domain, names in sorted(distinct.items())
        },
        "shared_files": {
            name: list(spread) for name, spread in sorted((shared or {}).items())
        },
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
    # `distinct_count` 也不许是手写常量：这里按同一份数据重算一次。
    distinct: dict[str, set[str]] = {domain: set() for domain in contract.DOMAINS}
    for entries in catalog["platforms"].values():
        for entry in entries:
            distinct[entry["domain"]].add(entry["name"])
    recomputed_distinct = {domain: len(names) for domain, names in sorted(distinct.items())}
    if catalog.get("distinct_count") != recomputed_distinct:
        raise SourceError(
            f"distinct_count 与按 (domain, name) 去重的结果不一致: "
            f"{catalog.get('distinct_count')} vs {recomputed_distinct}"
        )


def collect() -> tuple[dict[str, Any], dict[str, int]]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - dev extra 未装时的出口
        raise SourceError(
            "缺少 PyYAML：这是 dev 侧生成器的依赖，装 ./.venv/Scripts/python.exe -m pip install -e '.[dev]'"
        ) from exc

    platforms: dict[str, list[dict[str, Any]]] = {}
    stats = {"files": 0, "entries": 0, "shared_entries": 0}
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

    # ── 共享文件（M2 接线：这里是原先"根本没读到"的那一步）────────────────────
    stats["shared_files"] = 0
    for filename, domain in SHARED_FILES.items():
        path = SOURCES_DIR / filename
        data = _require(yaml, path)
        stats["files"] += 1
        stats["shared_files"] += 1
        if not isinstance(data, list) or not data:
            raise SourceError(
                f"{filename}: 共享域文件读不到条目（{domain}）—— 空表会让该域的覆盖度归零"
            )
        shared_entries = [_validate_entry(raw, path, i) for i, raw in enumerate(data)]
        wrong = [e["name"] for e in shared_entries if e["domain"] != domain]
        if wrong:
            raise SourceError(
                f"{filename}: 这些条目的 domain 不是 {domain!r}（共享文件与域必须一一对应）: {wrong[:5]}"
            )
        spread = SHARED_SPREAD[filename]
        for platform in spread:
            platforms.setdefault(platform, []).extend(shared_entries)
        stats["shared_entries"] += len(shared_entries) * len(spread)

    stats["entries"] += stats["shared_entries"]
    # 传给 `build()` 的是 **`SHARED_SPREAD`**（文件名 -> 挂到哪几个平台轴），
    # 不是 `SHARED_FILES`（文件名 -> 域）。两者混用会让 manifest 记成
    # `{"sysexits.yaml": ["e","x","i","t"]}`（字符串被当成列表展开了）——
    # 本机实测过这一形态，由 `test_build_catalog_collects_shared_files` 抓住。
    catalog = build(platforms, SHARED_SPREAD)
    _self_check(catalog, stats["files"])
    return catalog, stats


def _render(catalog: dict[str, Any]) -> tuple[str, str]:
    body = json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    manifest = {
        "schema_version": catalog["schema_version"],
        "generator_version": catalog["generator_version"],
        "entry_count": catalog["entry_count"],
        # 共享文件按平台展开后，`entry_count` 会重复计入；这个数是**去重后**的真分母。
        "distinct_count": catalog["distinct_count"],
        "shared_files": catalog["shared_files"],
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
            f"条目分布 {catalog['entry_count']}；去重后 {catalog['distinct_count']}）\n"
        )
        return 0

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "catalog.json").write_bytes(body.encode("utf-8"))
    (out_dir / "catalog.manifest.json").write_bytes(manifest.encode("utf-8"))
    sys.stderr.write(
        f"build_catalog: 写出 {out_dir.name}/catalog.json（{stats['files']} 个源文件 / "
        f"{stats['entries']} 条；条目分布 {catalog['entry_count']}；"
        f"去重后 {catalog['distinct_count']}）\n"
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
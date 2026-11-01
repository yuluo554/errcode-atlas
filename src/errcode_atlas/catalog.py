"""编目装载层：唯一入口是 :func:`load`。

纪律（plan/03 §1.5）：

* 装载期 **fail-closed**：任何一条缺出处、`source.kind` 不认识、``kind: file`` 缺行号 ——
  直接 ``CatalogError``，不做"跳过一条继续"。
* 索引在**装载期一次建好**；判定层只做集合查询，不许二次扫描。
* 摘要按**行尾归一后**计算（``\\r\\n`` → ``\\n``）——否则 ``git archive`` 导出树（受
  ``core.autocrlf``）算出的摘要与仓库值不同，装好的包直接 exit 3（plan/04 §3.1）。
* 本层不 import 任何第三方库：运行期零依赖。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import contract

DATA_DIR = Path(__file__).resolve().parent / "data"
CATALOG_PATH = DATA_DIR / "catalog.json"
MANIFEST_PATH = DATA_DIR / "catalog.manifest.json"


class CatalogError(RuntimeError):
    """编目不可用：文件缺失 / 结构非法 / 摘要不符 / 出处不全。

    调用方必须把它映射成 ``contract.EXIT_UNDECIDABLE``（"算不了"），
    不得映射成 ``EXIT_NON_UNIQUE``（"有答案但不可归因"）——两者是不同语义。
    """


@dataclass(frozen=True)
class Entry:
    """一条编目记录。字段契约见 plan/03 §1.2。"""

    name: str
    domain: str
    value: int
    platform: str
    source: Mapping[str, Any]
    description_zh: str = ""
    posix_ref: str = "<none>"

    @property
    def strength(self) -> str:
        """判定强度：由 ``source.kind`` 决定，**不可升级**（plan/04 §2.2）。"""
        kind = str(self.source.get("kind", ""))
        return contract.SOURCE_MAX_STRENGTH.get(kind, contract.STRENGTH_GRAY)

    @property
    def source_label(self) -> str:
        """人读出处标签，**零外链**：``<相对路径>:<行号>`` 或 ``runtime:<程序> <版本>``。"""
        kind = self.source.get("kind")
        if kind == contract.SOURCE_FILE:
            return f"{self.source['file']}:{self.source['line']}"
        if kind == contract.SOURCE_RUNTIME:
            return f"runtime:{self.source['runtime']} {self.source['program_version']}"
        if kind == contract.SOURCE_DOC:
            return f"doc:{self.source['anchor']}"
        return "unknown-source"

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "domain": self.domain,
            "value": self.value,
            "platform": self.platform,
            "source": dict(self.source),
            "source_label": self.source_label,
            "strength": self.strength,
            "description_zh": self.description_zh,
            "posix_ref": self.posix_ref,
        }


@dataclass
class Catalog:
    """冻结编目的内存形态 + 三个索引。"""

    entries: tuple[Entry, ...] = ()
    schema_version: int = 1
    generator_version: str = "0.1.0"
    #: platform -> domain -> value -> 名字集合（同值多名 = AMBIGUOUS 的素材，合法）
    by_value: dict[str, dict[str, dict[int, tuple[str, ...]]]] = field(default_factory=dict)
    #: platform -> domain -> 名字 -> 值
    by_name: dict[str, dict[str, dict[str, int]]] = field(default_factory=dict)
    #: platform -> 该平台在编目里出现过的信号编号集合（``128+n`` 的 ``n`` 有效性判据）
    signals: dict[str, frozenset[int]] = field(default_factory=dict)

    # ── 查询面（判定层只用这几个，不许直接摸 entries）─────────────────────
    def names_at(self, platform: str, domain: str, value: int) -> tuple[str, ...]:
        return self.by_value.get(platform, {}).get(domain, {}).get(value, ())

    def value_of(self, platform: str, domain: str, name: str) -> int | None:
        return self.by_name.get(platform, {}).get(domain, {}).get(name)

    def platforms_with_name(self, domain: str, name: str) -> dict[str, int]:
        found: dict[str, int] = {}
        for platform in contract.PLATFORMS:
            value = self.value_of(platform, domain, name)
            if value is not None:
                found[platform] = value
        return found

    def signal_numbers(self, platform: str) -> frozenset[int]:
        return self.signals.get(platform, frozenset())

    def entry_for(self, platform: str, domain: str, name: str) -> Entry | None:
        for item in self.entries:
            if item.platform == platform and item.domain == domain and item.name == name:
                return item
        return None

    def entry_count(self) -> dict[str, int]:
        """**由构造算出**的分母，不是手写常量（plan/04 §3 的纪律）。"""
        counts: dict[str, int] = {domain: 0 for domain in contract.DOMAINS}
        for item in self.entries:
            counts[item.domain] = counts.get(item.domain, 0) + 1
        return counts

    def platforms(self) -> tuple[str, ...]:
        present = {item.platform for item in self.entries}
        return tuple(p for p in contract.PLATFORMS if p in present)

    def covered_platforms(self, domain: str) -> tuple[str, ...]:
        """该域**已编目覆盖**的平台。

        为什么需要它（plan/03 §2.2 序 3 的分母）：跨平台判歧义时，**没有该域任何条目的平台
        不进分母** —— 那是"第三态：未覆盖"，不是"该平台没有这个值"。
        把未覆盖当分歧会让编目半途时每条都判 `AMBIGUOUS-CROSS-PLATFORM`（假歧义）；
        反之若把未覆盖平台从分歧里完全忽略，`11`（只有 linux 有）就会被判成"各平台一致"（假唯一）。
        判据 = **"这个平台的缺席，是'我查过没有'，还是'我还没查'？"**——只有前者算分歧。
        """
        present = {
            item.platform for item in self.entries if item.domain == domain
        }
        return tuple(p for p in contract.PLATFORMS if p in present)


def normalize_newlines(text: str) -> str:
    """行尾归一 —— 摘要口径的唯一实现（plan/04 §3.1）。"""
    return text.replace("\r\n", "\n")


def sha256_of_text(text: str) -> str:
    return hashlib.sha256(normalize_newlines(text).encode("utf-8")).hexdigest()


# ── 装载期校验 ────────────────────────────────────────────────────────────────
def _require(entry: Mapping[str, Any], keys: Iterable[str], where: str) -> None:
    missing = [k for k in keys if entry.get(k) in (None, "")]
    if missing:
        raise CatalogError(f"{where}: 缺字段 {missing}")


def _validate_source(source: Any, where: str) -> dict[str, Any]:
    if not isinstance(source, dict):
        raise CatalogError(f"{where}: source 必须是对象（无出处者不得入编目，见 data/gaps.md）")
    kind = source.get("kind")
    if kind not in contract.SOURCE_KINDS:
        raise CatalogError(
            f"{where}: source.kind={kind!r} 不在 {list(contract.SOURCE_KINDS)} 内"
        )
    _require(source, contract.SOURCE_REQUIRED_FIELDS[kind], f"{where}: source[{kind}]")
    if kind == contract.SOURCE_FILE:
        path = str(source["file"])
        if path.startswith("/") or ":" in path:
            raise CatalogError(f"{where}: source.file 必须是仓库内相对路径，实得 {path!r}")
        line = source["line"]
        if not isinstance(line, int) or line <= 0:
            raise CatalogError(f"{where}: source.line 必须是正整数，实得 {line!r}")
    if kind == contract.SOURCE_RUNTIME:
        if source["runtime"] not in contract.RUNTIMES:
            raise CatalogError(
                f"{where}: source.runtime={source['runtime']!r} 不在 {list(contract.RUNTIMES)} 内"
            )
    if kind == contract.SOURCE_DOC:
        if not str(source["url"]).startswith("https://"):
            raise CatalogError(f"{where}: source.url 必须是 https，实得 {source['url']!r}")
    return dict(source)


def _validate_entry(raw: Any, index: int, platform: str) -> Entry:
    where = f"catalog.json[{index}]"
    if not isinstance(raw, dict):
        raise CatalogError(f"{where}: 条目必须是对象")
    _require(raw, ("name", "domain", "value", "source"), where)
    if raw["domain"] not in contract.DOMAINS:
        raise CatalogError(f"{where}: domain={raw['domain']!r} 不在 {list(contract.DOMAINS)} 内")
    if not isinstance(raw["value"], int):
        raise CatalogError(f"{where}: value 必须是整数，实得 {raw['value']!r}")
    source = _validate_source(raw["source"], where)
    return Entry(
        name=str(raw["name"]),
        domain=str(raw["domain"]),
        value=int(raw["value"]),
        platform=platform,
        source=source,
        description_zh=str(raw.get("description_zh", "")),
        posix_ref=str(raw.get("posix_ref", "<none>")),
    )


def build_indexes(entries: Iterable[Entry]) -> tuple[dict, dict, dict]:
    """三索引的唯一构造实现。**生成侧刻意不共享它**（plan/02 §1.2）。"""
    by_value: dict[str, dict[str, dict[int, list[str]]]] = {}
    by_name: dict[str, dict[str, dict[str, int]]] = {}
    signals: dict[str, set[int]] = {}

    for entry in entries:
        # (platform, domain, name) 出现两个不同的 value 是硬错；
        # (platform, domain, value) 出现多个 name 是合法的（别名）。
        seen = by_name.setdefault(entry.platform, {}).setdefault(entry.domain, {})
        if entry.name in seen and seen[entry.name] != entry.value:
            raise CatalogError(
                f"{entry.platform}/{entry.domain}/{entry.name}: "
                f"重复定义且数值不同（{seen[entry.name]} vs {entry.value}）"
            )
        seen[entry.name] = entry.value
        by_value.setdefault(entry.platform, {}).setdefault(entry.domain, {}).setdefault(
            entry.value, []
        ).append(entry.name)
        if entry.domain == "signal":
            signals.setdefault(entry.platform, set()).add(entry.value)

    frozen_value = {
        platform: {
            domain: {value: tuple(sorted(names)) for value, names in values.items()}
            for domain, values in domains.items()
        }
        for platform, domains in by_value.items()
    }
    frozen_signals = {platform: frozenset(values) for platform, values in signals.items()}
    return frozen_value, by_name, frozen_signals


def load(catalog_path: Path | None = None, manifest_path: Path | None = None) -> Catalog:
    """装载冻结编目。**唯一入口** —— 别处不许自己 ``json.load``。"""
    catalog_path = catalog_path or CATALOG_PATH
    manifest_path = manifest_path or MANIFEST_PATH

    if not catalog_path.is_file():
        raise CatalogError(
            f"编目不存在: {catalog_path.name}（随包数据缺失 —— 重新构建或重装）"
        )
    text = catalog_path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:  # pragma: no cover - 结构损坏时的出口
        raise CatalogError(f"编目不是合法 JSON: {exc}") from exc

    if manifest_path.is_file():
        manifest_text = manifest_path.read_text(encoding="utf-8")
        manifest = json.loads(manifest_text)
        expected = manifest.get("sha256")
        actual = sha256_of_text(text)
        if expected and expected != actual:
            raise CatalogError(
                f"编目摘要不符（manifest={expected[:12]}… 实测={actual[:12]}…）："
                "随包数据被改动或行尾未归一（见 plan/04 §3.1）"
            )

    raw_platforms = payload.get("platforms")
    if not isinstance(raw_platforms, dict):
        raise CatalogError("catalog.json 顶层缺 platforms 对象")

    entries: list[Entry] = []
    for platform, raw_entries in raw_platforms.items():
        if platform not in contract.PLATFORMS:
            raise CatalogError(
                f"catalog.json: 平台 {platform!r} 不在 {list(contract.PLATFORMS)} 内"
            )
        if not isinstance(raw_entries, list):
            raise CatalogError(f"catalog.json[{platform}]: 必须是数组")
        for index, raw in enumerate(raw_entries):
            entries.append(_validate_entry(raw, index, platform))

    by_value, by_name, signals = build_indexes(entries)

    return Catalog(
        entries=tuple(entries),
        schema_version=int(payload.get("schema_version", 1)),
        generator_version=str(payload.get("generator_version", "0.1.0")),
        by_value=by_value,
        by_name=by_name,
        signals=signals,
    )


def load_or_raise(catalog_path: Path | None = None) -> "Catalog":
    """同 :func:`load`，仅作为 CLI 侧的语义化别名，便于 AST 守门收窄 import 面。"""
    return load(catalog_path)
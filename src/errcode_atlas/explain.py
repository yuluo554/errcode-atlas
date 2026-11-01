"""模块② 数字→语义判定（招牌模块）。

纯函数层：**不读时钟、不读环境变量、不联网、不做格式化**（plan/02 L2）。
判定顺序写死在 :func:`explain` 的分支里，测试逐行对应 plan/03 §2.2 的表。

最重要的纪律：``AMBIGUOUS-*`` / ``PLATFORM-ABSENT`` 是**正确的判定结果**，不是失败态。
绝不因为"最常见的那一个"就收敛成一个答案 —— 那是本题要取代的行为。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import contract
from .catalog import Catalog, Entry


@dataclass(frozen=True)
class Query:
    """一次查询的输入形状。"""

    text: str
    kind: str  # "number" | "name"
    number: int | None
    name: str | None
    platform: str | None
    domain: str | None

    @classmethod
    def parse(cls, text: str, platform: str | None, domain: str | None) -> "Query":
        raw = text.strip()
        if not raw:
            raise ValueError("查询为空")
        if raw.lstrip("-").isdigit():
            return cls(raw, "number", int(raw), None, platform, domain)
        return cls(raw, "name", None, raw, platform, domain)


@dataclass(frozen=True)
class Explanation:
    """判定结果。**结果对象级**真值 —— fixtures 的 expected.json 存的就是它的字段。"""

    verdict: str
    query: dict[str, Any]
    candidates: tuple[dict[str, Any], ...] = ()
    distinguish: str = ""
    platform_absent_in: tuple[str, ...] = ()
    per_platform: dict[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()

    @property
    def exit_code(self) -> int:
        return contract.exit_code_for_verdict(self.verdict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "query": self.query,
            "candidates": list(self.candidates),
            "distinguish": self.distinguish,
            "platform_absent_in": list(self.platform_absent_in),
            "per_platform": self.per_platform,
            "notes": list(self.notes),
            "sources": list(self.sources),
        }


def _query_dict(query: Query) -> dict[str, Any]:
    return {
        "kind": query.kind,
        "text": query.text,
        "value": query.number,
        "name": query.name,
        "platform": query.platform,
        "domain": query.domain,
    }


def _candidate(entry: Entry) -> dict[str, Any]:
    return {
        "name": entry.name,
        "value": entry.value,
        "platform": entry.platform,
        "domain": entry.domain,
        "source_label": entry.source_label,
        "strength": entry.strength,
    }


def _valueless(domains: tuple[str, ...]) -> bool:
    """探测范围内**只有**无值域吗（`node`）。

    判据是"探测范围里有没有任何有值域"，不是"当前这个域是不是无值域的" ——
    名字形态会给出一串域，其中任一有值，`None` 的含义就要按"值"解释。
    """
    return bool(domains) and all(d in contract.VALUELESS_DOMAINS for d in domains)


def _domains_for(query: Query) -> tuple[str, ...]:
    """域缺省时的探测序（plan/03 §2.1）。

    * 数字形态：先 ``errno`` 再 ``signal`` —— **数字永远不探测 ``exit`` / ``node``**：
      `exit` 是进程退出码，与 errno 号没有同一性；`node` 根本没有数字。把某条 errno
      数值顺手拿去解释成退出码，正是本题要取代的"看起来答得很像"。
    * 名字形态：``errno`` / ``signal`` / ``node`` / ``exit``。``node`` 排在 ``exit`` 前
      （`ERR_*` 有 `ERR_` 前缀，而 `EX_*` 也带下划线，靠前缀区分不如靠域序可靠），
      ``exit`` 排最后 —— 它的名字（`EX_USAGE` 等）与系统常量名不冲突，放最后不影响。
    """
    if query.domain:
        return (query.domain,)
    if query.kind == "number":
        return (contract.DOMAIN_ERRNO, contract.DOMAIN_SIGNAL)
    return (
        contract.DOMAIN_ERRNO,
        contract.DOMAIN_SIGNAL,
        contract.DOMAIN_NODE,
        contract.DOMAIN_EXIT,
    )


def explain(query: Query, catalog: Catalog) -> Explanation:
    """判定顺序见 plan/03 §2.2 —— 与那里的九行表逐行对应，**不许重排**。

    序 7（名字 + 无平台 + 值发散 → `UNAMBIGUOUS`）与序 8（名字 + 无平台 + 某平台没有
    → `PLATFORM-ABSENT`）是 M2 补上的分界：前者答"这个名字有没有定义"，后者答
    "哪个平台根本没有"。两者都不是失败态。
    """
    if query.kind == "number":
        return _explain_number(query, catalog)
    return _explain_name(query, catalog)


# ── 数字形态 ────────────────────────────────────────────────────────────────
def _explain_number(query: Query, catalog: Catalog) -> Explanation:
    assert query.number is not None
    domains = _domains_for(query)
    notes = _maybe_gray_notes(domains)

    # 序 1/2：给了平台 —— 同平台同域内一数多名 = AMBIGUOUS-SAME-PLATFORM
    if query.platform:
        hits = [
            catalog.entry_for(query.platform, domain, name)
            for domain in domains
            for name in catalog.names_at(query.platform, domain, query.number)
        ]
        hits = [entry for entry in hits if entry is not None]
        if not hits:
            return _unknown(query)
        if len(hits) == 1:
            entry = hits[0]
            return Explanation(
                verdict=contract.UNAMBIGUOUS,
                query=_query_dict(query),
                candidates=(_candidate(entry),),
                notes=notes,
                sources=(entry.source_label,),
            )
        ordered = sorted(hits, key=lambda e: (e.value, e.name))
        return Explanation(
            verdict=contract.AMBIGUOUS_SAME_PLATFORM,
            query=_query_dict(query),
            candidates=tuple(_candidate(e) for e in ordered),
            distinguish=(
                "同平台同域内一个数字对应多个常量名；这些名字在该平台上不可区分，"
                "按上游声明区分，不得任选其一冒充唯一答案"
            ),
            notes=notes,
            sources=tuple(e.source_label for e in ordered),
        )

    # 序 3/4：没给平台 —— 逐平台列值。
    # **分母 = 该域已覆盖的平台**（``catalog.covered_platforms``）：未覆盖的平台是"还没查"，
    # 不是"查过没有"；把它算进分歧会造出假歧义，把它完全忽略又会把"只有 linux 有"
    # 判成"各平台一致"（假唯一）。两者都是本工具最贵的错。
    per_platform: dict[str, Any] = {}
    uncovered: list[str] = []
    # 逐平台收：跨域探测时把多个域的名字并起来（去重排序），键始终是**平台**
    # —— 报告要回答的是"这个数字在各平台是什么"，不是"这个数字在各平台各域是什么"。
    for domain in domains:
        for platform in catalog.covered_platforms(domain):
            for name in catalog.names_at(platform, domain, query.number):
                bucket = per_platform.setdefault(platform, [])
                if name not in bucket:
                    bucket.append(name)
        for platform in contract.PLATFORMS:
            if platform not in catalog.covered_platforms(domain) and platform not in uncovered:
                uncovered.append(platform)
    for platform, names in per_platform.items():
        per_platform[platform] = sorted(names)

    if not per_platform:
        return _unknown(query)

    # 缺席平台（该域已覆盖、但这个值上没有名字）与命中平台一起进分歧判定：
    # 命中集合不一致 → 跨平台歧义；"有的平台有、有的平台没有"同样是不一致。
    covered = {p for domain in domains for p in catalog.covered_platforms(domain)}
    absent_keys = sorted(covered - set(per_platform))
    distinct = {tuple(names) for names in per_platform.values()}
    if len(distinct) > 1 or absent_keys:
        return Explanation(
            verdict=contract.AMBIGUOUS_CROSS_PLATFORM,
            query=_query_dict(query),
            per_platform=per_platform,
            distinguish=(
                "未指定平台，且各平台对该数字的归因不一致"
                + (f"（{', '.join(absent_keys)} 上没有这个值）" if absent_keys else "")
                + "；逐平台列值，必须用 --platform 指定后才有唯一答案"
            ),
            notes=notes
            + (("未覆盖平台不计入分歧：" + ", ".join(uncovered),) if uncovered else ()),
        )
    only_names = next(iter(distinct))
    labels: list[str] = []
    for platform in per_platform:
        for domain in domains:
            for name in only_names:
                entry = catalog.entry_for(platform, domain, name)
                if entry is not None:
                    labels.append(entry.source_label)
    return Explanation(
        verdict=contract.UNAMBIGUOUS,
        query=_query_dict(query),
        candidates=tuple({"name": name} for name in only_names),
        per_platform=per_platform,
        distinguish="各平台归因一致；未给平台不构成歧义",
        notes=notes + ("各平台归因一致（platforms_agree）",),
        sources=tuple(labels),
    )


# ── 名字形态 ────────────────────────────────────────────────────────────────
def _explain_name(query: Query, catalog: Catalog) -> Explanation:
    assert query.name is not None
    domains = _domains_for(query)

    if query.platform:
        for domain in domains:
            entry = catalog.entry_for(query.platform, domain, query.name)
            if entry is not None:
                return Explanation(
                    verdict=contract.UNAMBIGUOUS,
                    query=_query_dict(query),
                    candidates=(_candidate(entry),),
                    notes=_maybe_gray_notes((domain,)),
                    sources=(entry.source_label,),
                )
        # 序 5：该平台没有，但别的平台有 —— PLATFORM-ABSENT（与 UNKNOWN 是两个语义）
        elsewhere: dict[str, int | None] = {}
        for domain in domains:
            elsewhere.update(catalog.platforms_with_name(domain, query.name))
        if elsewhere:
            has_value = any(value is not None for value in elsewhere.values())
            return Explanation(
                verdict=contract.PLATFORM_ABSENT,
                query=_query_dict(query),
                platform_absent_in=(query.platform,),
                per_platform=dict(sorted(elsewhere.items())),
                distinguish=(
                    f"{query.name} 在 {query.platform} 上不存在；"
                    f"在 {', '.join(sorted(elsewhere))} 上存在"
                    + ("且取值不同 —— " if has_value else "（该域只有名字、没有数字码值）—— ")
                    + "这是平台缺失，不是编目查不到"
                ),
            )
        return _unknown(query)

    # 未给平台：逐平台列值；任何一个平台缺失即 PLATFORM-ABSENT
    present: dict[str, int | None] = {}
    for domain in domains:
        present.update(catalog.platforms_with_name(domain, query.name))
    if not present:
        return _unknown(query)
    missing = tuple(p for p in catalog.platforms() if p not in present)
    if missing:
        return Explanation(
            verdict=contract.PLATFORM_ABSENT,
            query=_query_dict(query),
            platform_absent_in=missing,
            per_platform=dict(sorted(present.items())),
            distinguish=(
                f"{query.name} 在 {', '.join(missing)} 上不存在；"
                "要求全平台归因时必须先说清缺哪个平台"
            ),
        )
    return Explanation(
        verdict=contract.UNAMBIGUOUS,
        query=_query_dict(query),
        per_platform=dict(sorted(present.items())),
        notes=_agree_notes(domains),
    )


def _agree_notes(domains: tuple[str, ...]) -> tuple[str, ...]:
    """"各平台一致"那句说明**按域形态分叉**。

    无值域（`node`）没有数字可言，"取值可能不同"在它上面是**假话** ——
    `ERR_*` 只有名字，四个平台查到的都是同一个名字。叙述与数据不符时，
    读者会以为工具在报一个它没有的信息。
    """
    if _valueless(domains):
        return (
            "各平台均有定义；该域只有错误码名、没有数字码值，"
            "因此不存在跨平台取值差异（跨平台可达性仍逐平台列出）",
        )
    return ("各平台均有定义；取值可能不同，跨平台取值差异不构成歧义",)


def _unknown(query: Query) -> Explanation:
    return Explanation(
        verdict=contract.UNKNOWN,
        query=_query_dict(query),
        distinguish="编目内无此值（可能为私有/自定义错误码，或尚未覆盖）",
    )


def _maybe_gray_notes(domains: tuple[str, ...]) -> tuple[str, ...]:
    """`gray` 强度条目的措辞强制（plan/04 §2.3）—— 由 bench 断言字样存在，不靠人记得写。"""
    notes: list[str] = []
    if "exit" in domains:
        notes.append("128+n 归因是 POSIX 惯例非标准（即惯例而非标准）")
    return tuple(notes)
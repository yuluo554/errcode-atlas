"""M2 解析棒：两份共享域编目的**独立复核**。

判据刻意与 ``tools/extract_catalog.py`` **分开实现**（同 M1 的理由）：抽取器自己解析一遍
再自己断言等于自证，只能证明"代码没被改坏"，证明不了"数值对原文没抄错"。
所以这里也换三条独立通路：

1. **正则通读原文**：直接扫 ``_headers/sysexits.html`` 与 ``node-errors.html``，
   把 ``(名字, 码值, 段锚)`` 抽出来，与入仓 YAML 逐条对账；
2. **语义钉死**：K20（共享条目覆盖全部应覆盖平台）、K22（`exit` 判定不依赖编目）、
   K23（`node` 不许混进 errno 域）逐条断言；
3. **索引面**：判定层不许二次扫描 —— 用 AST 与行为两条判据。

依赖 ``_headers/``（`.gitignore` 封的本地原料）。原料不在时这些测试**显式 skip 并说明原因**，
不做"跳过当通过"。
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from errcode_atlas import catalog as catalog_mod
from errcode_atlas import contract
from errcode_atlas.catalog import load
from errcode_atlas.explain import Query, explain
from errcode_atlas.exitcode import SYSEXITS_NAMES, attribute

REPO_ROOT = Path(__file__).resolve().parents[1]
HEADERS = REPO_ROOT / "_headers"
CATALOG_DIR = REPO_ROOT / "data" / "catalog"
EXPLAIN_SRC = REPO_ROOT / "src" / "errcode_atlas" / "explain.py"
EXITCODE_SRC = REPO_ROOT / "src" / "errcode_atlas" / "exitcode.py"


def _headers_available() -> bool:
    return (HEADERS / "SOURCES.json").is_file()


pytestmark = pytest.mark.skipif(
    not _headers_available(),
    reason="本机原料 _headers/ 不存在（.gitignore 封）。跑 tools/fetch_sources.py --out _headers 后可验",
)


def _catalog():
    return load()


# ══ 通路 1：原文逐条对账 ════════════════════════════════════════════════════
#: 手册页每一项：`<dt id="EX_*"><a …><code …>EX_*</code></a>\n    (NN)</dt>`。
#: 两处细节都会让正则"匹配出 0 条"（本机实测各踩了一次）：
#:   · `<a>` 里面**还套着 `<code>`** —— 用 `[^<]*</a>` 当锚会匹配不到；
#:   · 码值与名字之间**有换行与缩进**。
#: 抽取器那边是独立写法，所以这里红只说明"这条通路没在验"，不是"数据错了"。
SYSEXITS_ITEM = re.compile(
    r'<dt id="(EX_[A-Z_0-9]+)"><a[^>]*>.*?</a>\s*\((\d+)\)</dt>'
)

#: Node 页每一项：`<section><h4><code>NAME</code>` 后跟 `class=mark id=<锚>`。
NODE_ITEM = re.compile(
    r"<section><h4><code>([A-Za-z][A-Za-z0-9_]*)</code>" r"<span><a id=[a-z0-9_]+></a></span>" r"<span><a class=mark id=([a-z0-9_]+)\s"
)


def _sysexits_raw() -> list[tuple[str, int]]:
    text = (HEADERS / "sysexits.html").read_text(encoding="utf-8")
    return [(name, int(value)) for name, value in SYSEXITS_ITEM.findall(text)]


def _node_raw() -> list[tuple[str, str]]:
    text = (HEADERS / "node-errors.html").read_text(encoding="utf-8")
    return [(name, fragment) for name, fragment in NODE_ITEM.findall(text)]


def test_sysexits_raw_has_fifteen_entries_64_to_78() -> None:
    """原文自证：15 条，码值 **连续 64–78**。

    这条钉的是"原文规模"本身 —— 它红了说明上游页面改了，而不是"我们的代码坏了"。
    两件事要分开报，否则"页面改版"会被当成"抽取 bug"来查。
    """
    raw = _sysexits_raw()
    assert len(raw) == 15, f"sysexits 页应有 15 条，实得 {len(raw)}"
    assert sorted(value for _, value in raw) == list(range(64, 79)), (
        "sysexits 码值不是连续 64–78"
    )


def test_every_sysexits_entry_is_in_catalog_with_same_value() -> None:
    """逐条对账：原文的每个 ``EX_*`` 与码值，必须与编目一致（一条不差、一个不改）。"""
    catalog = _catalog()
    raw = dict(_sysexits_raw())
    got = {
        entry.name: entry.value
        for entry in catalog.entries
        if entry.domain == "exit"
    }
    # 共享文件挂在四个轴上 → 每个名字出现四次，值必须都一样（下面那条断言管这个）
    distinct = {}
    for entry in catalog.entries:
        if entry.domain == "exit":
            distinct.setdefault(entry.name, set()).add(entry.value)
    wrong = {name: values for name, values in distinct.items() if values != {raw.get(name)}}
    assert not wrong, f"这些 exit 条目的码值与原文不符: {wrong}"
    assert set(distinct) == set(raw), (
        f"exit 域与原文不一致：仅编目 {sorted(set(distinct) - set(raw))}；"
        f"仅原文 {sorted(set(raw) - set(distinct))}"
    )
    assert got, "exit 域一条都没读到 —— 判据空跑"


def test_node_raw_and_catalog_agree_name_for_name() -> None:
    """Node 页 **435 节全部入编目**（383 现行 + 52 弃用），名字与段锚逐条一致。

    ``legacy`` 也在内：弃用不等于用户看不到。
    """
    raw = _node_raw()
    assert len(raw) == 435, f"Node 页应有 435 节，实得 {len(raw)}"

    distinct = {}
    for entry in _catalog().entries:
        if entry.domain == "node":
            distinct.setdefault(entry.name, set()).add(str(entry.source["anchor"]))
    assert set(distinct) == {name for name, _ in raw}, (
        f"node 域与原文不一致：仅编目 {sorted(set(distinct) - {n for n, _ in raw})[:5]}；"
        f"仅原文 {sorted({n for n, _ in raw} - set(distinct))[:5]}"
    )
    anchors = {entry.name: entry.source["anchor"] for entry in _catalog().entries if entry.domain == "node"}
    wrong = {name: anchors[name] for name, fragment in raw if anchors.get(name) != f"#{fragment}"}
    assert not wrong, f"这些条目的段锚与原文不符: {list(wrong.items())[:5]}"


def test_legacy_node_codes_are_marked_in_description() -> None:
    """弃用小节的码必须在释义里点名它是 legacy —— 用户拿到它要能立刻知道已被弃用。

    计数口径：共享条目挂在 3 个平台轴上，所以**按名字去重**后应是 52，
    逐平台计应是 52 × 3。两个数都要对，否则可能是"标记数对了但挂错轴"、
    或者"轴对了但标记重复写入"。名字是同一个（同一个源文件展开），所以去重即可。
    """
    entries = [entry for entry in _catalog().entries if entry.domain == "node"]
    flagged = {
        entry.name
        for entry in entries
        if "Legacy Node.js error codes" in entry.description_zh
    }
    assert len(flagged) == 52, f"legacy 去重后应为 52，实得 {len(flagged)}"
    assert len([e for e in entries if "Legacy Node.js error codes" in e.description_zh]) == 52 * 3, (
        "legacy 条目逐平台计数应为 52 × 3"
    )
    assert all(entry.description_zh for entry in entries), "有 node 条目释义为空"


# ══ 通路 2a：K20 —— 共享条目必须覆盖到"它真正成立"的全部平台 ═══════════════
def test_sysexits_covers_all_four_platforms() -> None:
    """**K20**：`exit` 域的分母必须是四个平台。

    这不是"随便挂满"：分母是跨平台判定的分母，只挂一个轴会让
    `covered_platforms("exit")` 缩成一个平台，凭空造出三个假 `PLATFORM-ABSENT`。
    2026-11-01 实测过这一形态（M1 的 `exit` 域是 0 条，分母是空集）。
    """
    catalog = _catalog()
    assert catalog.covered_platforms("exit") == contract.PLATFORMS
    for platform in contract.PLATFORMS:
        assert catalog.value_of(platform, "exit", "EX_USAGE") == 64, f"{platform} 上 EX_USAGE 不是 64"


def test_node_domain_covers_three_platforms_not_python_view() -> None:
    """`node` 域挂三个轴，**不挂 `win32-python`** —— 那是事实，不是漏了。

    `ERR_*` 是 Node 运行时抛的码：Linux/macOS 上的 Node 也抛同一批，
    Python 视角不抛。`win32-python` 上查它必须是 `PLATFORM-ABSENT`，
    不能是 `UNKNOWN`（那会把"这个平台没有这套码"说成"我没查到"）。
    """
    catalog = _catalog()
    assert catalog.covered_platforms("node") == ("linux", "macos", "win32-node")

    result = explain(Query.parse("ERR_AMBIGUOUS_ARGUMENT", "win32-python", None), catalog)
    assert result.verdict == contract.PLATFORM_ABSENT
    assert result.platform_absent_in == ("win32-python",)

    unknown = explain(Query.parse("ERR_NOT_A_REAL_CODE_XYZ", "linux", "node"), catalog)
    assert unknown.verdict == contract.UNKNOWN, "不存在的码名必须是 UNKNOWN，不是 PLATFORM-ABSENT"


def test_shared_entries_do_not_fake_cross_platform_ambiguity() -> None:
    """**K20 的反面**：共享条目在四个轴上取值相同，不该被判成 `AMBIGUOUS-CROSS-PLATFORM`。

    这是"分母变大"最容易引入的假歧义：同一个 `EX_USAGE` 在四个平台都是 64，
    `explain EX_USAGE --domain exit` 必须 `UNAMBIGUOUS`。
    """
    result = explain(Query.parse("EX_USAGE", None, "exit"), _catalog())
    assert result.verdict == contract.UNAMBIGUOUS, (
        f"共享条目被误判成跨平台歧义：{result.verdict} / {result.per_platform}"
    )
    assert result.per_platform == {platform: 64 for platform in contract.PLATFORMS}


# ══ 通路 2b：K22 —— exit 判定不依赖编目是否存在 ═════════════════════════════
def test_exit_attribution_works_on_empty_catalog() -> None:
    """**K22**：编目里一条 `exit` 都没有时，`64–78` 仍必须判 `SYSEXITS`。

    判定只看区间；编目只提供"这个名字存在"的事实。把二者绑死会让"编目丢了"
    变成"约定段失效" —— 那是两种完全不同的故障。
    """
    empty = catalog_mod.Catalog()
    for code in (64, 70, 78):
        result = attribute(code, "linux", empty)
        assert result.attribution == contract.SYSEXITS, f"{code} 在空编目上没判成 SYSEXITS"
        assert result.sysexits_name == SYSEXITS_NAMES[code]
        assert result.exit_code == contract.EXIT_OK
        assert any("约定非标准" in note for note in result.notes)
        assert result.sources == (), "空编目上不该凭空给出处"


def test_exit_attribution_carries_source_when_catalog_has_it() -> None:
    """编目在时有出处（`kind: doc` 的段锚）—— 「每条判定必须带出处」这条纪律的落法。"""
    result = attribute(64, "linux", _catalog())
    assert result.attribution == contract.SYSEXITS
    assert result.sources == ("doc:#EX_USAGE",)


def test_code_table_and_catalog_are_two_copies_that_agree() -> None:
    """`SYSEXITS_NAMES`（判定用）与 `sysexits.yaml`（报告用）是两份副本，必须双向一致。

    为什么不是"只留一份"：判定不许依赖编目（K22），所以代码内表必须在；
    而出处必须是编目（报告要带锚），所以编目也必须在。两份就必然有漂移风险，
    这条断言就是那个风险的门。
    """
    catalog = _catalog()
    from_catalog = {
        entry.name: entry.value
        for entry in catalog.entries
        if entry.domain == "exit" and entry.platform == "linux"
    }
    from_code = {name: value for value, name in SYSEXITS_NAMES.items()}
    assert from_catalog == from_code, (
        f"代码内表与编目不一致：仅代码 {sorted(set(from_code.items()) - set(from_catalog.items()))}；"
        f"仅编目 {sorted(set(from_catalog.items()) - set(from_code.items()))}"
    )


# ══ 通路 2c：K23 —— ERR_* 不许混进 OS errno 域 ═══════════════════════════════
def test_err_codes_are_not_in_errno_domain() -> None:
    """**K23**：`ERR_*` 是 Node 自己抛的码名，与 OS errno 无映射关系。

    混进 `errno` 域会让 `explain 100` 之类开始编造 —— 因为那些条目没有数字值可索引，
    它们要么被塞进假数值，要么让 `errno` 域的"一数多名"判定从根上失真。
    """
    catalog = _catalog()
    offenders = [
        entry.name
        for entry in catalog.entries
        if entry.domain == "errno" and entry.name.startswith("ERR_")
    ]
    assert not offenders, f"这些 ERR_* 混进了 errno 域: {offenders[:10]}"

    # 反向：node 域里不许出现 OS errno 的名字（EAGAIN 之类）
    errno_names = {
        entry.name for entry in catalog.entries if entry.domain == "errno"
    }
    leaked = [
        entry.name
        for entry in catalog.entries
        if entry.domain == "node" and entry.name in errno_names
    ]
    assert not leaked, f"这些名字同时出现在 errno 与 node 域: {leaked[:10]}"


def test_err_codes_have_no_numeric_value() -> None:
    """无值域的条目不写 `value`（写了个数字就是在假装它有数字码）。"""
    for entry in _catalog().entries:
        if entry.domain in contract.VALUELESS_DOMAINS:
            assert entry.value is None, f"{entry.name} 是无值域条目却带了 value={entry.value}"


def test_loader_rejects_value_on_valueless_domain(tmp_path, write_catalog):
    """装载期 fail-closed：给 `node` 条目写个数字码必须直接报错（不许静默收下）。"""
    payload = {
        "platforms": {
            "linux": [
                {
                    "name": "ERR_FAKE",
                    "domain": "node",
                    "value": 42,
                    "source": {"kind": "doc", "url": "https://x.invalid/d", "anchor": "#a",
                               "verified_at": "2026-11-01"},
                }
            ]
        }
    }
    path = write_catalog(payload)
    with pytest.raises(catalog_mod.CatalogError, match="无值域"):
        catalog_mod.load(path, tmp_path / "missing.manifest.json")


def test_err_code_number_lookup_does_not_bleed_into_node_domain() -> None:
    """`explain 100 --platform win32-node` 不该因为 node 域存在而多出候选。"""
    catalog = _catalog()
    with_node = explain(Query.parse("100", "win32-node", None), catalog).as_dict()
    without_node = explain(Query.parse("100", "win32-node", "errno"), catalog).as_dict()
    assert with_node["verdict"] == without_node["verdict"]
    numeric_names = [c["name"] for c in with_node["candidates"]]
    assert not any(name.startswith("ERR_") for name in numeric_names)


# ══ 通路 2d：K21 —— kind: doc 的出处契约 ════════════════════════════════════
def test_every_shared_entry_uses_doc_source_with_https_and_anchor() -> None:
    """**K21**：`kind: doc` 的条目 `url` 必须 https、`anchor` 非空、强度不是 hard。"""
    checked = 0
    for entry in _catalog().entries:
        if entry.domain not in ("exit", "node"):
            continue
        checked += 1
        assert entry.source["kind"] == contract.SOURCE_DOC, f"{entry.name} 的出处不是 doc"
        assert str(entry.source["url"]).startswith("https://"), f"{entry.name} 的 url 不是 https"
        assert str(entry.source["anchor"]).startswith("#"), f"{entry.name} 的 anchor 不是段锚"
        assert entry.strength == contract.STRENGTH_DIFF, f"{entry.name} 的 doc 出处拿到了 hard"
    assert checked > 0, "一条共享条目都没检查到 —— 判据空跑"


def test_loader_rejects_doc_source_with_http(tmp_path, write_catalog):
    """`doc` 出处的 url 必须是 https —— 装载期就挡，不留到报告期。"""
    payload = {
        "platforms": {
            "linux": [
                {
                    "name": "EX_FAKE",
                    "domain": "exit",
                    "value": 99,
                    "source": {"kind": "doc", "url": "http://x.invalid/d", "anchor": "#a",
                               "verified_at": "2026-11-01"},
                }
            ]
        }
    }
    path = write_catalog(payload)
    with pytest.raises(catalog_mod.CatalogError, match="https"):
        catalog_mod.load(path, tmp_path / "missing.manifest.json")


# ══ 通路 3：索引在装载期一次建好，判定层无二次扫描 ═════════════════════════
def test_indexes_are_built_at_load_time() -> None:
    """`covered_platforms` / `entry_for` 必须查表，不许每次重扫 `entries`。

    判据是**行为面**的：装载后把 `entries` 清空，查询面必须仍然答得出来。
    这比"看代码里有没有 for 循环"可靠 —— 后者换个写法就绕过（比如生成器表达式）。
    """
    catalog = _catalog()
    assert catalog.covered_platforms("exit") == contract.PLATFORMS

    catalog.entries = ()
    assert catalog.covered_platforms("exit") == contract.PLATFORMS, (
        "entries 清空后 covered_platforms 就空了 —— 说明它在扫 entries，不是查表"
    )
    assert catalog.entry_for("linux", "exit", "EX_USAGE") is not None, (
        "entries 清空后 entry_for 就查不到了 —— 说明它在扫 entries，不是查表"
    )
    assert catalog.names_at("linux", "signal", 9), "names_at 应当查表"
    assert catalog.value_of("linux", "errno", "EAGAIN") == 11


def test_judgement_layer_has_no_entries_scan() -> None:
    """AST 守门：`explain.py` / `exitcode.py` 里不许出现对 `.entries` 的遍历。"""
    offenders: list[str] = []
    for path in (EXPLAIN_SRC, EXITCODE_SRC):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.For, ast.comprehension)):
                continue
            target = node.iter
            if (
                isinstance(target, ast.Attribute)
                and target.attr == "entries"
            ):
                offenders.append(f"{path.name}: line {node.lineno} 遍历了 entries")
    assert not offenders, f"判定层出现二次扫描：{offenders}"


# ══ UNKNOWN 的两种形态（HANDOFF-M2 §三 第 7 条）════════════════════════════
@pytest.mark.parametrize(
    "text,platform,domain,note",
    [
        ("99999", "linux", "exit", "越界值"),
        ("1", "linux", "exit", "域内有条目、但没有这个值"),
        ("EX_USAGE", "linux", "node", "名字在别的域、不在这个域"),
        ("ERR_NOT_A_REAL_CODE_XYZ", "linux", None, "名字在所有域都没有"),
    ],
)
def test_unknown_paths_both_shapes_exit_three(text, platform, domain, note) -> None:
    """`UNKNOWN` 有两种形态，**两种都必须 exit 3**：

    1. 越界值（`99999`）；
    2. **域内有条目、但没有这个值**（`1 --domain exit`：exit 域有 15 条，1 不在其中）。

    第二种是 M2 才第一次成立的形态 —— `exit` 域为空时，所有值都是"越界"，
    两种形态根本无从区分。
    """
    result = explain(Query.parse(text, platform, domain), _catalog())
    assert result.verdict == contract.UNKNOWN, f"{note}：判成了 {result.verdict}"
    assert result.exit_code == contract.EXIT_UNDECIDABLE


def test_exit_domain_has_entries_so_unknown_second_shape_is_meaningful() -> None:
    """上面那条的前提：`exit` 域**必须有**条目，否则第二种形态退化成"越界"。"""
    catalog = _catalog()
    assert catalog.entry_count()["exit"] > 0
    assert 1 not in set().union(
        *[
            set(catalog.by_value.get(platform, {}).get("exit", {}))
            for platform in contract.PLATFORMS
        ] or [set()]
    ), "exit 域里不该有 1 —— 有的话第二条用例就不是「有域无值」了"


# ══ SHARED_FILES 接线（原先 collect() 根本不读它）═══════════════════════════
def test_build_catalog_collects_shared_files() -> None:
    """`build_catalog.collect()` 必须真读到共享文件（M1 时它是空接线）。

    判据 = 冻结件里存在 `exit` / `node` 域的条目，且 manifest 记了它们挂到哪些平台。
    """
    import json

    frozen = json.loads(
        (REPO_ROOT / "src" / "errcode_atlas" / "data" / "catalog.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (REPO_ROOT / "src" / "errcode_atlas" / "data" / "catalog.manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert frozen["entry_count"]["exit"] > 0, "exit 域还是 0 条 —— 共享文件没被读到"
    assert frozen["entry_count"]["node"] > 0, "node 域还是 0 条 —— 共享文件没被读到"
    assert manifest["shared_files"]["sysexits.yaml"] == list(contract.PLATFORMS)
    assert manifest["shared_files"]["node-errors.yaml"] == ["linux", "macos", "win32-node"]


def test_entry_count_and_distinct_count_are_different_denominators() -> None:
    """`entry_count`（逐平台）与 `distinct_count`（去重）**必须分开记**。

    共享文件按平台展开后，`entry_count` 会重复计入；把两个数混成一个，
    "条目数 × 平台数"就会被当成"收录了这么多条"。分母各有用处，不许互相顶替。
    """
    catalog = _catalog()
    per_platform = catalog.entry_count()
    distinct = catalog.distinct_count()

    assert per_platform == catalog.entry_count()  # 由构造算出
    assert distinct["node"] == 435, f"node 去重后应是 435，实得 {distinct['node']}"
    assert distinct["exit"] == 15, f"exit 去重后应是 15，实得 {distinct['exit']}"
    # node 挂 3 个轴、exit 挂 4 个轴 —— 逐平台计数正是去重数的整数倍
    assert per_platform["node"] == distinct["node"] * 3
    assert per_platform["exit"] == distinct["exit"] * 4
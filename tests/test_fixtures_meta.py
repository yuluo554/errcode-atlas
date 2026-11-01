"""基准语料自身的判据：**形状、来源、覆盖度**。

`bench` 验的是"结果对不对"；本文件验的是"语料本身是否够格"——两者缺一都会让
"全绿"变成空话：

* 只要 case 少到只覆盖一种判定态，`bench` 也会全绿（因为它只比对存在的 case）；
* 只要 `expected.json` 缺 `source`，"真值从哪来"就无从复核（K24 的落地判据）；
* 只要某条 `expected.json` 是 `explain` 的输出回填，`bench` 就**恒绿**（结构性失效）。
  第三条无法自动抓（那是逻辑问题，不是形状问题），所以**形状判据 + 人工 review**
  才是完整的一道门 —— 这里的断言保证"回填过的东西至少看得出没有来源"。

覆盖度门槛的数值一律引用 `data/README.md` §4，本文件不复述（写第二份副本没有门在对账）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from errcode_atlas import contract
from errcode_atlas.catalog import load

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "fixtures"
DATA_README = REPO_ROOT / "data" / "README.md"

#: 真编目 —— 覆盖度判据要查"这个值在该域到底有没有"，不能只看 case 自己怎么声明。
CATALOG = load()


def _cases() -> list[Path]:
    if not FIXTURES.is_dir():
        return []
    return sorted(p for p in FIXTURES.iterdir() if p.is_dir())


CASES = _cases()


# ── 非空跑自证（"0 个 case"不能与"全过"同形）───────────────────────────────
def test_fixtures_are_not_empty():
    """`fixtures/` 一个 case 都没有时，下面所有判据都是空跑 —— 先挡住这个形态。"""
    assert CASES, "fixtures/ 下 0 个 case：覆盖度判据全部空跑（bench 也会因此返回 3）"


# ── 每 case 的形状 ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_case_has_both_files(case: Path):
    """每 case 必须有 `INPUT.md` 与 `expected.json`（`plan/04` §1.3）。"""
    assert (case / "INPUT.md").is_file(), f"{case.name}: 缺 INPUT.md"
    assert (case / "expected.json").is_file(), f"{case.name}: 缺 expected.json"


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_expected_declares_source(case: Path):
    """**K24 的落地判据**：`expected.json` 必须写 `source`（真值从哪来）。

    没有这一栏，`expected.json` 与"随手抄的实现输出"在形状上不可区分 ——
    而后者会让 `bench` 恒绿。K24 无法自动判"不是回填"，但能自动判"说不出来源"。
    """
    payload = json.loads((case / "expected.json").read_text(encoding="utf-8"))
    source = payload.get("source")
    assert source and isinstance(source, str) and len(source.strip()) >= 8, (
        f"{case.name}: expected.json 缺 source，或 source 太短（无法复核真值来源）"
    )


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_input_md_writes_the_question_and_the_source(case: Path):
    """`INPUT.md` 必须同时写"用户会怎么问"与来源 —— 来源先写、真值后写（K24 的顺序）。"""
    text = (case / "INPUT.md").read_text(encoding="utf-8")
    assert "## 用户会怎么问" in text, f"{case.name}: INPUT.md 没写用户提问"
    assert "## 来源" in text, f"{case.name}: INPUT.md 没写来源（K24 要求先写来源）"


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_expected_input_matches_known_kind(case: Path):
    """`input.kind` 只认 `explain` / `exitcode`（bench 也这么判，这里前置挡一道）。"""
    payload = json.loads((case / "expected.json").read_text(encoding="utf-8"))
    kind = payload.get("input", {}).get("kind")
    assert kind in ("explain", "exitcode"), f"{case.name}: input.kind={kind!r} 不在白名单内"


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_expected_verdict_or_attribution_is_contract_value(case: Path):
    """真值里的判定态 / 归因必须是契约集合内的值（拼错一个字母就等于放过一条假真值）。"""
    payload = json.loads((case / "expected.json").read_text(encoding="utf-8"))
    if payload["input"]["kind"] == "explain":
        assert payload.get("verdict") in contract.VERDICTS, (
            f"{case.name}: verdict 不在 contract.VERDICTS 内"
        )
    else:
        assert payload.get("attribution") in contract.ATTRIBUTIONS, (
            f"{case.name}: attribution 不在 contract.ATTRIBUTIONS 内"
        )


# ── 覆盖度：五态各 ≥2 / UNKNOWN 与 UNAMBIGUOUS 各 ≥3 ───────────────────────
def _all() -> list[dict]:
    """全部 case 的 expected（一次读盘，供下面的覆盖度断言共用）。"""
    return [json.loads((c / "expected.json").read_text(encoding="utf-8")) for c in CASES]


def _explain_cases() -> list[dict]:
    out = []
    for case in CASES:
        payload = json.loads((case / "expected.json").read_text(encoding="utf-8"))
        if payload["input"]["kind"] == "explain":
            out.append(payload)
    return out


def _verdict_counts() -> dict[str, int]:
    counts = {verdict: 0 for verdict in contract.VERDICTS}
    for payload in _explain_cases():
        counts[payload["verdict"]] = counts.get(payload["verdict"], 0) + 1
    return counts


@pytest.mark.parametrize("verdict", contract.VERDICTS)
def test_every_verdict_has_at_least_two_cases(verdict: str):
    """**五态各 ≥2 例**（`data/README.md` §4「判定态」行）。"""
    counts = _verdict_counts()
    assert counts[verdict] >= 2, f"{verdict} 只有 {counts[verdict]} 例（门槛 ≥2）：{counts}"


@pytest.mark.parametrize("verdict", [contract.UNKNOWN, contract.UNAMBIGUOUS])
def test_high_bar_verdicts_have_at_least_three_cases(verdict: str):
    """`UNKNOWN` 与 `UNAMBIGUOUS` 的门槛是 **≥3**（§4 同行的后半句）。"""
    counts = _verdict_counts()
    assert counts[verdict] >= 3, f"{verdict} 只有 {counts[verdict]} 例（门槛 ≥3）：{counts}"


# ── UNKNOWN 两形态（M2 才成立的那一条）────────────────────────────────────
def test_unknown_has_both_shapes():
    """`UNKNOWN` 的两种形态各至少一例（§4「`UNKNOWN` 两形态」行）。

    * 形态一 = **越界值**：数字大到该域不可能有（如信号 63）；
    * 形态二 = **域内有条目但无此值**：`exit` 域有 15 条、`1` 不在其中。

    判据不能只看"给了 domain" —— `signal` 域也有条目，`63 --domain signal` 既是
    "给了域"又是"越界"。真正的形态二要求**这个值不在该域的取值集合里，而该域本身非空**，
    且值落在该域已知上界之内（否则还是越界形态）。M3 变异验证当场抓到过：只判 `domain`
    非空时，把形态二的 domain 换成 `signal`，判据仍绿 —— 那是假门。
    """
    unknowns = [p for p in _explain_cases() if p["verdict"] == contract.UNKNOWN]
    assert len(unknowns) >= 2, "UNKNOWN 少于 2 例，两形态无从区分"

    never_seen: list[str] = []
    in_domain_miss: list[str] = []
    for payload in unknowns:
        spec = payload["input"]
        domain = spec.get("domain")
        query = str(spec.get("query", ""))
        if not domain or not query.lstrip("-").isdigit():
            continue
        value = int(query)
        numbers: set[int] = set()
        for platform in CATALOG.covered_platforms(domain):
            for bucket in CATALOG.by_value.get(platform, {}).get(domain, {}):
                numbers.add(bucket)
        if not numbers:
            never_seen.append(f"{query} --domain {domain}（该域一条都没有）")
        elif value not in numbers and value <= max(numbers):
            # 值落在该域已知取值区间内、但确实没有它 → 形态二
            in_domain_miss.append(f"{query} --domain {domain}（域内 {len(numbers)} 个值，不含它）")
        elif value in numbers:
            # 该域**确实有这个值**，却又声明 UNKNOWN —— 真值本身错了（bench 也会红）
            never_seen.append(f"{query} --domain {domain}（该域**有**这个值，UNKNOWN 声明站不住）")
        else:
            never_seen.append(f"{query} --domain {domain}（超出该域上界 {max(numbers)}）")

    assert in_domain_miss, (
        "UNKNOWN 缺「域内有条目但无此值」这一形态（§4 强制项）。"
        f"现有 UNKNOWN case 全落在越界形态：{never_seen}"
    )


# ── 跨平台分叉点全覆盖（§1.2 五个信号点 + §1.1 三个 Windows 数值点）───────
@pytest.mark.parametrize("number", ["7", "10", "17", "19", "20", "30"])
def test_signal_fork_points_have_a_cross_platform_case(number: str):
    """信号分叉数字（§1.2）各至少一例 **跨平台** case（未给平台、各平台不同）。

    16 不在本表里：它的分叉形态是"macOS **根本没有** `SIGSTKFLT`"，那是
    `PLATFORM-ABSENT`（名字查询），不是"同一数字两平台不同"（数字查询）——
    两种分叉各由下面两条测试分管，混在一起会要求一个不存在的用例形态。
    """
    hits = [
        p
        for p in _explain_cases()
        if p["input"].get("query") == number
        and p["input"].get("platform") is None
        and p["input"].get("domain") == "signal"
    ]
    assert hits, f"信号 {number} 没有跨平台 case（分叉点必须各留一例）"


def test_sigstkflt_fork_has_platform_absent_case():
    """`SIGSTKFLT` 的分叉形态：linux 有（16）、macOS **没有** → `PLATFORM-ABSENT`。"""
    hits = [
        p
        for p in _explain_cases()
        if p["input"].get("query") == "SIGSTKFLT"
        and p["verdict"] == contract.PLATFORM_ABSENT
    ]
    assert hits, "缺 SIGSTKFLT 在 macOS 上 PLATFORM-ABSENT 的 case"


@pytest.mark.parametrize("name", ["EADDRINUSE", "ECONNREFUSED", "ETIMEDOUT"])
def test_windows_dual_view_numeric_points_are_covered(name: str):
    """三个 Windows 数值差异点（§1.1 E4/E5）各要两个视角的 case。

    判据比的是**两个视角确实各自出过一次**，而不是"名字出现过"——只写一个视角
    等于把本题最硬的事实（同一台机器两个数值）抹平。真值里若带 `candidate_values`，
    还要比它俩不相等。

    **字段名是 `candidate_values`，不是 `value`**（M4 改）：`value` 那版 `bench` 不比对，
    写了等于没写；现在同一份字段既进 `bench` 断言、也进本判据。M4 当场验到过这一点 ——
    字段一改名，本测试的 `payload.get("value")` 静默变 `None`，判据退化成"两个视角都有
    case 就行"，**是靠"改完先看它会不会松"抓到的**。
    """
    values: dict[str, int | None] = {}
    for case in CASES:
        payload = json.loads((case / "expected.json").read_text(encoding="utf-8"))
        spec = payload["input"]
        if spec["kind"] != "explain" or spec.get("query") != name:
            continue
        if spec.get("platform") in ("win32-node", "win32-python"):
            reported = payload.get("candidate_values")
            values[spec["platform"]] = reported[0] if reported else None

    assert "win32-node" in values, f"{name} 缺 win32-node 视角的 case"
    assert "win32-python" in values, f"{name} 缺 win32-python 视角的 case"
    node, python = values["win32-node"], values["win32-python"]
    assert node is not None and python is not None, (
        f"{name} 的两个视角 case 没有声明 `candidate_values` —— 双视角数值无从复核"
    )
    assert node != python, f"{name} 两个视角的 case 值是同一个（{node}）—— 双视角事实被抹平"


# ── 不可归因集（§3 强制项）────────────────────────────────────────────────
def test_unattributable_exit_one_is_present():
    """`exit 1` 必须有 case 且真值就是 `UNATTRIBUTABLE`（`plan/01` §二 模块③ 硬纪律）。"""
    hits = [
        p
        for p in _all()
        if p["input"]["kind"] == "exitcode"
        and p["input"]["code"] == 1
        and p["attribution"] == contract.UNATTRIBUTABLE
    ]
    assert hits, "缺 exit 1 → UNATTRIBUTABLE 的 case"


def test_128_plus_n_invalid_case_is_present():
    """`128+n` 的 `n` 无效必须有专门 case（`n` 不在该平台信号表 → `UNATTRIBUTABLE`）。"""
    hits = [
        p
        for p in _all()
        if p["input"]["kind"] == "exitcode"
        and p.get("attribution") == contract.UNATTRIBUTABLE
        and "不是有效信号" in " ".join(p.get("require_note_markers") or [])
    ]
    assert hits, "缺「128+n 的 n 无效」case（M3 DoD 的强制项）"


def test_all_fifteen_sysexits_codes_are_covered():
    """`sysexits` 64–78 **全部 15 条**各一例（§4「sysexits」行）。"""
    codes = {
        p["input"]["code"]
        for p in _all()
        if p["input"]["kind"] == "exitcode" and p.get("attribution") == contract.SYSEXITS
    }
    assert codes == set(range(64, 79)), (
        f"sysexits 覆盖不完整：缺 {sorted(set(range(64, 79)) - codes)}"
    )


# ── 门槛数值必须与 data/README §4 同在（防"本文件自己编门槛"）──────────────
def test_coverage_thresholds_are_stated_in_data_readme():
    """覆盖度门槛只许有一份 —— `data/README.md` §4。

    本文件只引用它；如果 §4 那段被删了，这里的门槛就成了"测试自己编的数"。
    判据 = §4 仍在、含"判定态"与"两形态"两行，且 M4 的三个规模门槛（30 / 435）同现。
    """
    text = DATA_README.read_text(encoding="utf-8")
    assert "## 4. 覆盖度口径" in text, "data/README 的 §4 覆盖度口径不见了"
    section = text[text.index("## 4. 覆盖度口径") :]
    assert "判定态" in section
    assert "两形态" in section
    assert "30 个公共常量" in section, "§4 的 errno 门槛（三平台 × 30 个公共常量）不见了"
    assert "435" in section, "§4 的 Node 门槛（页面全部 435 节）不见了"


# ── M4 规模门槛（data/README §4 的三行 ⬜ 在此变成可跑红的判据）───────────
#: 这三条的**数字**全部现算：常量集从真编目取、信号集从真编目取，本文件不另存一份名单
#: —— 存了就会出现"编目改了而语料门槛不动"的第二份真相。
ERRNO_MIN_COMMON = 30


def _errno_common_names() -> set[str]:
    """四轴都有的 errno 常量名（= §4 里"公共常量"的可算定义）。"""
    per_axis = {}
    for platform in contract.PLATFORMS:
        per_axis[platform] = {
            name for name, _value in CATALOG.by_name.get(platform, {}).get("errno", {}).items()
        }
    return set.intersection(*(per_axis[p] for p in contract.PLATFORMS))


@pytest.mark.parametrize("platform", contract.PLATFORMS)
def test_errno_three_platforms_cover_thirty_common_constants(platform: str):
    """**errno 三平台 × ≥30 个公共常量**（§4「errno」行）。

    "公共常量" = 四轴都定义了的 errno 名（从**真编目**现算，不写死名单）。
    每个平台至少要被 §4 门槛条数个这样的常量**以数字查询 + 显式平台**覆盖到 ——
    名字查询不算：那验的是"名字在不在"，不是"这个平台上这个数字是什么"。
    """
    common = _errno_common_names()
    assert len(common) >= ERRNO_MIN_COMMON, (
        f"编目四轴公共 errno 常量只有 {len(common)} 个（< {ERRNO_MIN_COMMON}）—— 门槛本身不成立"
    )
    covered: set[str] = set()
    for payload in _explain_cases():
        spec = payload["input"]
        if spec.get("platform") != platform or spec.get("domain") != "errno":
            continue
        query = str(spec.get("query", ""))
        if not query.lstrip("-").isdigit():
            continue
        for name in payload.get("candidate_names") or []:
            if name in common:
                covered.add(name)
    assert len(covered) >= ERRNO_MIN_COMMON, (
        f"{platform} 的 errno 公共常量只覆盖了 {len(covered)} 个（门槛 {ERRNO_MIN_COMMON}）："
        f"{sorted(covered)}"
    )


@pytest.mark.parametrize("platform", ["linux", "macos"])
def test_signals_cover_every_catalog_define(platform: str):
    """**信号两平台 × 全部 `#define SIG*`**（§4「信号」行）：编目里每一条都要有 case。"""
    catalog_names = set(CATALOG.by_name.get(platform, {}).get("signal", {}))
    assert len(catalog_names) >= 30, f"{platform} 编目信号只有 {len(catalog_names)} 条"
    covered = {
        str(p["input"].get("query"))
        for p in _explain_cases()
        if p["input"].get("platform") == platform and p["input"].get("domain") == "signal"
    }
    missing = sorted(catalog_names - covered)
    assert not missing, f"{platform} 有 {len(missing)} 条信号没有 case：{missing}"


def test_node_covers_every_catalog_section():
    """**Node 435 节逐条**（§4「Node 错误码」行）：编目里每个名字都要有 case。

    判据从真编目现算条目数（不写 435），但门槛值必须与 §4 同现
    （`test_coverage_thresholds_are_stated_in_data_readme` 管那一半）。
    """
    catalog_names = set(CATALOG.by_name.get("linux", {}).get("node", {}))
    assert len(catalog_names) == 435, (
        f"编目 node 域应有 435 个名字（§4），实得 {len(catalog_names)}"
    )
    covered = {
        str(p["input"].get("query"))
        for p in _explain_cases()
        if p["input"].get("domain") == "node"
    }
    missing = sorted(catalog_names - covered)
    assert not missing, f"有 {len(missing)} 条 Node 错误码没有 case：{missing[:10]}"


def test_legacy_node_codes_name_legacy_in_their_source():
    """**弃用的 52 条要点名 legacy**（§4「Node 错误码」行后半句）。

    判据 = 每条 legacy 码的 case 的 `source` 里出现 `Legacy` —— 只说"有 case"不够：
    用户拿到弃用码必须能立刻看出它是 legacy（`tests/test_catalog_m2.py` 管编目那一侧，
    本判据管语料这一侧的落点）。
    """
    legacy = {
        name
        for name in CATALOG.by_name.get("linux", {}).get("node", {})
        if "Legacy Node.js error codes" in (CATALOG.entry_for("linux", "node", name).description_zh)
    }
    assert len(legacy) == 52, f"编目 legacy 码应为 52 条，实得 {len(legacy)}"
    silent = [
        p["case"]
        for p in _explain_cases()
        if str(p["input"].get("query")) in legacy
        and "Legacy" not in str(p.get("source", ""))
    ]
    assert not silent, f"这些 legacy 码的 case 没有点名 legacy：{silent[:10]}"


def test_unambiguous_cases_outnumber_ambiguous_ones():
    """**同值同义压过歧义样本**（`plan/HANDOFF-M4.md` §三 第 3 条的反向样本门槛）。

    语料若系统性偏向"歧义"，`bench` 全绿也证明不了"不该歧义时不歧义"。判据：
    `UNAMBIGUOUS` 的 case 数必须**多于** `AMBIGUOUS-*` 之和。两边都从语料现数，
    不写死比例 —— 写死会随铺量立刻过期。
    """
    counts = _verdict_counts()
    ambiguous = counts[contract.AMBIGUOUS_SAME_PLATFORM] + counts[contract.AMBIGUOUS_CROSS_PLATFORM]
    assert counts[contract.UNAMBIGUOUS] > ambiguous, (
        f"语料偏向歧义：UNAMBIGUOUS {counts[contract.UNAMBIGUOUS]} 例 ≤ "
        f"AMBIGUOUS-* {ambiguous} 例（反向样本压不过歧义样本）"
    )
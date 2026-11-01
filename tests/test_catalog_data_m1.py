"""M1 数据先行：599 条编目的**独立复核**。

这份测试的判据刻意与 ``tools/extract_catalog.py`` **分开实现**：抽取器自己解析一遍再自己断言
等于自证，只能证明"代码没被改坏"，证明不了"数值对原文没抄错"。所以这里换三条独立通路：

1. **正则通读原文**：不开预处理器，直接把 ``_headers/*.h`` 里所有 ``#define E*/SIG*`` 的
   ``(名字, 值, 行号)`` 抽出来，与入仓 YAML 逐条对账（``source.line`` 指过去必须真是那一行）。
2. **文档锚点对照**：``data/README.md`` §1.1/§1.2 里写死的**分叉点数值**逐点断言 ——
   包括 ``SIGSTKFLT`` 在 macOS 上不存在（`PLATFORM-ABSENT` 的证据源头）。
3. **运行时再读一次**：本机 Node / Python 再读一次常量表，与 YAML 的 ``runtime`` 条目比。
   运行时条目没有行号，唯一能验的就是"再跑一次还一样"。

关键纪律：**期望值写字面量**（``7`` / ``10``），不写被测数据结构的字段引用 —— 否则把编目改错时
"实测"与"期望"一起错（HANDOFF-M0 §四 K12 的同一类自我参照）。

依赖 ``_headers/``（`.gitignore` 封的本地原料）。原料不在时这些测试**显式 skip 并说明原因**，
不做"跳过当通过"—— skip 的判据在 ``test_headers_present`` 里报出来。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from errcode_atlas import contract
from errcode_atlas.catalog import load

REPO_ROOT = Path(__file__).resolve().parents[1]
HEADERS = REPO_ROOT / "_headers"
CATALOG_DIR = REPO_ROOT / "data" / "catalog"

DEFINE = re.compile(r"^\s*#\s*define\s+(E[A-Z0-9_]+|SIG[A-Z0-9]+)\s+(\S+)")


def _headers_available() -> bool:
    return (HEADERS / "SOURCES.json").is_file()


pytestmark = pytest.mark.skipif(
    not _headers_available(),
    reason="本机原料 _headers/ 不存在（.gitignore 封）。跑 tools/fetch_sources.py --out _headers 后可验",
)


def _raw_defines(filename: str) -> list[tuple[str, str, int]]:
    """原文里所有 ``#define E*/SIG*`` 的 (名字, 值文本, 行号) —— **不做预处理器求值**。"""
    path = HEADERS / filename
    rows: list[tuple[str, str, int]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = DEFINE.match(line)
        if match:
            rows.append((match.group(1), match.group(2), line_no))
    return rows


def _catalog():
    return load()


# ── 原料在位自证（防止整份测试因为缺原料而"静默全跳"）───────────────────────
def test_headers_present() -> None:
    """skipif 会让整份文件静默跳过；这里显式确认原料真在，且清单里 5 份都对得上。"""
    manifest = json.loads((HEADERS / "SOURCES.json").read_text(encoding="utf-8"))
    assert len(manifest["sources"]) == 5
    for item in manifest["sources"]:
        assert (HEADERS / item["dest"]).is_file(), f"原料缺失: {item['dest']}"


# ── 通路 1：出处行号必须指得到那一行 ───────────────────────────────────────
def test_every_file_entry_line_points_at_its_own_define() -> None:
    """**最核心的一条**：每条 ``kind: file`` 的 ``source.line`` 上去，必须就是那个常量。

    这是"每条数值带出处"从口号变成判据的地方：把某条的 ``line`` 改错一位，这里立刻红。
    """
    cache: dict[str, list[str]] = {}
    wrong: list[str] = []
    checked = 0
    for entry in _catalog().entries:
        source = entry.source
        if source.get("kind") != contract.SOURCE_FILE:
            continue
        name = Path(str(source["file"])).name
        key = str(source["file"])
        if key not in cache:
            # 上游路径 -> 本机缓存文件名（清单里 dest 与上游 path 的对应）
            cache[key] = (HEADERS / f"{_header_id_for(key)}.h").read_text(encoding="utf-8").splitlines()
        lines = cache[key]
        line_no = int(source["line"])
        text = lines[line_no - 1] if 0 < line_no <= len(lines) else ""
        match = DEFINE.match(text)
        checked += 1
        if not match or match.group(1) != entry.name:
            wrong.append(f"{entry.platform}/{entry.name}@{name}:{line_no} -> {text.strip()[:60]!r}")

    assert checked > 0, "一条 file 条目都没检查到 —— 判据空跑"
    assert not wrong, f"{len(wrong)} 条的出处行号指错了行:\n" + "\n".join(wrong[:10])


def _header_id_for(upstream_path: str) -> str:
    mapping = {
        "include/uapi/asm-generic/errno-base.h": "linux-errno-base",
        "include/uapi/asm-generic/errno.h": "linux-errno",
        "include/uapi/asm-generic/signal.h": "linux-signal",
        "bsd/sys/errno.h": "macos-errno",
        "bsd/sys/signal.h": "macos-signal",
    }
    return mapping[upstream_path]


# ── 通路 1b：原文里"该有的名字"必须都进了编目 ──────────────────────────────
def test_linux_errno_base_covers_all_34_raw_defines() -> None:
    """Linux errno 基础段原文有 34 条 ``#define E*``（`data/README.md` §1.1 E1），必须全录。"""
    raw = {name for name, _, _ in _raw_defines("linux-errno-base.h")}
    assert len(raw) == 34, f"原文基础段应有 34 条，实得 {len(raw)}"
    got = {
        entry.name
        for entry in _catalog().entries
        if entry.platform == "linux" and entry.domain == "errno"
    }
    assert raw <= got, f"基础段这些没进编目: {sorted(raw - got)}"


def test_macos_errno_raw_distinct_names_are_all_present() -> None:
    """xnu `bsd/sys/errno.h` 原文 120 行 ``#define E*`` / **119 个不同名字**（E3 的 119）。

    120 而非 119 的唯一原因是 ``EOPNOTSUPP`` 出现两次（第 156 行非 UNIX03 分支、第 253 行
    UNIX03 分支）—— 用户态默认环境只取后者。这条断言把"119"这个文档数字钉在原文上。
    """
    rows = _raw_defines("macos-errno.h")
    names = [name for name, _, _ in rows]
    assert len(rows) == 120
    assert len(set(names)) == 119, "EOPNOTSUPP 是唯一的重复定义；数字变了说明原文口径变了"

    got = {
        entry.name
        for entry in _catalog().entries
        if entry.platform == "macos" and entry.domain == "errno"
    }
    # 内核内部的伪错误（KERNEL 分支）本就不属于用户态 errno，不该在编目里
    kernel_only = {
        "ERESTART",
        "EJUSTRETURN",
        "ERECYCLE",
        "EREDRIVEOPEN",
        "EKEEPLOOKING",
        "EDATALESS",
        "ECVCERORR",
        "ECVPERORR",
        "EQSUSPENDED",
        "EQCONGESTED",
    }
    assert not (kernel_only & got), f"内核伪错误混进了用户态编目: {sorted(kernel_only & got)}"
    missing = set(names) - kernel_only - got
    # 非 UNIX03 分支的 EOPNOTSUPP 不在编目里是**对的**（用户态取 102 那条），单独排除
    assert not missing, f"这些用户态 errno 没进编目: {sorted(missing)}"


def test_macos_eopnotsupp_takes_the_unix03_value() -> None:
    """``EOPNOTSUPP`` 在 macOS 用户态是 **102**（UNIX03 分支），不是 45（非 UNIX03 分支）。

    45 是 ``ENOTSUP``。两个名字同平台不同值 —— 把这条抄成 45 会让 `EOPNOTSUPP` 与 `ENOTSUP`
    在这个平台上"看起来"同值，跨平台对账就此失真。
    """
    catalog = _catalog()
    assert catalog.value_of("macos", "errno", "EOPNOTSUPP") == 102
    assert catalog.value_of("macos", "errno", "ENOTSUP") == 45


# ── 通路 2：文档里的分叉点逐点对照 ─────────────────────────────────────────
@pytest.mark.parametrize(
    "name,linux_value,macos_value",
    [
        ("SIGBUS", 7, 10),
        ("SIGSTOP", 19, 17),
        ("SIGCHLD", 17, 20),
        ("SIGUSR1", 10, 30),
    ],
)
def test_documented_signal_fork_points(name, linux_value, macos_value) -> None:
    """`data/README.md` §1.2 列的五个分叉点（`SIGSTKFLT` 单列，下面那条测）。"""
    catalog = _catalog()
    assert catalog.value_of("linux", "signal", name) == linux_value
    assert catalog.value_of("macos", "signal", name) == macos_value
    assert linux_value != macos_value, "分叉点表的两个值不该相等，否则这条用例本身失效"


def test_sigstkflt_exists_on_linux_and_absent_on_macos() -> None:
    """`SIGSTKFLT` 是 `PLATFORM-ABSENT` 的证据源头：linux 16，macos **没有**。

    注意"没有"是**结构性缺失**，不是"没查到" —— 所以它不出现在 `data/gaps.md` 的未录行里，
    而是由判定层答 `PLATFORM-ABSENT`。
    """
    catalog = _catalog()
    assert catalog.value_of("linux", "signal", "SIGSTKFLT") == 16
    assert catalog.value_of("macos", "signal", "SIGSTKFLT") is None
    assert 16 in catalog.signal_numbers("linux")
    assert 16 in catalog.signal_numbers("macos"), "macos 的 16 号是 SIGURG，占位但不叫 SIGSTKFLT"


@pytest.mark.parametrize(
    "name,node_value,python_value",
    [
        ("EADDRINUSE", 100, 10048),
        ("ECONNREFUSED", 107, 10061),
        ("ETIMEDOUT", 138, 10060),
    ],
)
def test_windows_two_views_keep_different_numbers(name, node_value, python_value) -> None:
    """`data/README.md` §1.1 E4/E5：**同一台机器**上 Node 与 Python 的数值不同。

    这三个是文档点名的最硬事实。若谁"顺手"把两个文件合并成一个 windows，
    这条会同时红两处 —— 且数值差异本身也消失。
    """
    catalog = _catalog()
    assert catalog.value_of("win32-node", "errno", name) == node_value
    assert catalog.value_of("win32-python", "errno", name) == python_value
    assert node_value != python_value


def test_eagain_diverges_across_platforms() -> None:
    """`data/README.md` §5.2 举的跨平台歧义样本：`EAGAIN` = 11 / 35 / 11 / 11。"""
    catalog = _catalog()
    assert catalog.value_of("linux", "errno", "EAGAIN") == 11
    assert catalog.value_of("macos", "errno", "EAGAIN") == 35
    assert catalog.value_of("win32-node", "errno", "EAGAIN") == 11


# ── 通路 3：运行时条目再读一次 ──────────────────────────────────────────────
def _node_errno() -> dict[str, int]:
    proc = subprocess.run(
        ["node", "-e", "process.stdout.write(JSON.stringify(require('os').constants.errno))"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip("node 不可用，跳过运行时再读")
    return json.loads(proc.stdout)


def _python_errno() -> dict[str, int]:
    import errno as errno_module

    return {
        name: value
        for name, value in vars(errno_module).items()
        if name.isupper() and isinstance(value, int) and not isinstance(value, bool)
    }


def test_win32_node_entries_match_live_node() -> None:
    live = _node_errno()
    catalog = _catalog()
    recorded = {
        entry.name: entry.value
        for entry in catalog.entries
        if entry.platform == "win32-node" and entry.domain == "errno"
    }
    assert recorded == live, "win32-node 的 errno 条目与本机 Node 实读不一致（版本变了？）"


def test_win32_python_entries_match_live_python() -> None:
    live = _python_errno()
    catalog = _catalog()
    recorded = {
        entry.name: entry.value
        for entry in catalog.entries
        if entry.platform == "win32-python" and entry.domain == "errno"
    }
    assert recorded == live, "win32-python 的 errno 条目与本机 Python 实读不一致"


def test_runtime_entries_never_claim_hard_strength() -> None:
    """`kind: runtime` 永远拿不到 `hard`（`plan/04` §2.2 的强度不可升级）。

    这条不只是"字段对"：它保证报告里 Windows 条目的措辞不会冒充头文件原文。
    """
    for entry in _catalog().entries:
        if entry.platform.startswith("win32-"):
            assert entry.strength == contract.STRENGTH_DIFF, f"{entry.name} 强度跑到了 {entry.strength}"
            assert "runtime:" in entry.source_label


def test_file_entries_all_reach_hard_strength() -> None:
    """反过来：能指到行号的必须都是 `hard`，否则说明 kind 被写错。"""
    for entry in _catalog().entries:
        if entry.platform in ("linux", "macos"):
            assert entry.strength == contract.STRENGTH_HARD, f"{entry.name} 强度是 {entry.strength}"


# ── 编目冻结面：YAML 源是唯一真相源，JSON 是派生物 ─────────────────────────
def test_every_yaml_entry_has_complete_source_block() -> None:
    """YAML 源里每条都要有完整 ``source`` —— fail-closed 的前置条件（装载期会再验一次）。"""
    import yaml

    total = 0
    for path in sorted(CATALOG_DIR.glob("*.yaml")):
        entries = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(entries, list), f"{path.name} 顶层不是数组"
        assert entries, f"{path.name} 是空的 —— M1 之后不该再有空编目"
        for item in entries:
            total += 1
            assert item.get("source"), f"{path.name}/{item.get('name')}: 缺 source"
            assert item.get("description_zh"), f"{path.name}/{item.get('name')}: 缺 description_zh"
            kind = item["source"]["kind"]
            assert kind in contract.SOURCE_KINDS
            for key in contract.SOURCE_REQUIRED_FIELDS[kind]:
                assert item["source"].get(key) not in (None, ""), (
                    f"{path.name}/{item.get('name')}: source[{kind}] 缺 {key}"
                )
    assert total > 500, f"编目条目数 {total} 太少（M1 门槛：三平台 errno 各 ≥30 + 信号全录）"


def test_coverage_thresholds_from_data_readme() -> None:
    """`data/README.md` §4 的覆盖度门槛，逐条对编目实际条目数断言。

    门槛是**文档定的**，所以这里的数字是抄文档的字面量 —— 编目缩水时它会红，
    而不会随编目自动放宽。
    """
    catalog = _catalog()
    counts: dict[tuple[str, str], int] = {}
    for entry in catalog.entries:
        key = (entry.platform, entry.domain)
        counts[key] = counts.get(key, 0) + 1

    # errno：三平台 × 至少 30 个公共常量（Windows 两视角各算一个平台）
    for platform in contract.PLATFORMS:
        assert counts.get((platform, "errno"), 0) >= 30, f"{platform} 的 errno 不足 30 条"

    # 信号：两平台 × 全部 #define SIG*
    assert counts.get(("linux", "signal"), 0) >= 31, "linux 信号少于 31 条"
    assert counts.get(("macos", "signal"), 0) >= 30, "macos 信号少于 30 条"


def test_no_duplicate_name_with_conflicting_value() -> None:
    """同平台同域同名的两个不同值是硬错（`plan/03` §1.5）。装载期会抛，这里再从数据面确认。"""
    catalog = _catalog()
    for platform in catalog.platforms():
        for domain in contract.DOMAINS:
            for name, value in catalog.by_name.get(platform, {}).get(domain, {}).items():
                assert catalog.value_of(platform, domain, name) == value


def test_sources_are_relative_paths_not_local_caches() -> None:
    """出处必须是**上游仓库路径**，不能是本地 `_headers/` 缓存路径 —— 否则出处对读者无意义。"""
    for entry in _catalog().entries:
        if entry.source.get("kind") != contract.SOURCE_FILE:
            continue
        path = str(entry.source["file"])
        assert "_headers" not in path, f"{entry.name} 的出处写成了本地缓存路径: {path}"
        assert not path.startswith("/")
        assert ":" not in path


def test_ref_is_a_pinned_commit_sha() -> None:
    """`source.ref` 必须钉 commit sha（`plan/04` §5「头文件随内核版本漂移」的处置）。

    写分支名（`master`/`main`）等于没钉 —— 上游一动，出处就指向别的内容。
    """
    for entry in _catalog().entries:
        if entry.source.get("kind") != contract.SOURCE_FILE:
            continue
        ref = str(entry.source["ref"])
        assert re.fullmatch(r"[0-9a-f]{40}", ref), f"{entry.name} 的 ref 不是完整 sha: {ref}"


# ── 抽取器本身：--check 必须与仓库一致（防"手改 YAML"）──────────────────────
def test_extractor_reproduces_committed_yaml() -> None:
    """重跑抽取器 → 与仓库里的 4 份 YAML 逐字节一致。

    这条是"能重跑出它"的直接判据（`plan/04` §1.2）。手改 YAML 中任何一个数值或行号，这里红。
    """
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "extract_catalog.py"), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


def test_fetch_sources_check_passes_on_local_headers() -> None:
    """已取件与 `SOURCES.json` 的 sha256 对账 —— 防"本地原料被手改后下游悄悄漂"。

    `_headers/` 是本机缓存（不入仓），所以这条只在有原料时跑（文件级 skipif 已保证）。
    """
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "fetch_sources.py"), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


# ── 出处字段必须钉死成"事实"，不能是"本次运行的环境" ─────────────────────
def test_runtime_program_version_is_pinned_not_current_interpreter() -> None:
    """`program_version` 必须是常量，不能取 `sys.executable` 报的版本。

    **本项目实测过的真缺陷**：首版用 `sys.executable -c 'print(platform.python_version())'`
    取版本，于是 `py -3.8 tools/extract_catalog.py --check` 把 `program_version` 写成
    `3.8.8`，而仓库里那份是 `3.12.10` —— 数值全对，`--check` 却报"YAML 被手改"。
    更糟的是它会把"换通道跑一次检查"变成"改一次数据"。

    判据 = **"这个字段是某天在某机器上实读的事实，还是本次运行的环境？"** —— 前者必须常量。
    """
    catalog = _catalog()
    python_versions = {
        str(entry.source["program_version"])
        for entry in catalog.entries
        if entry.source.get("runtime") == "python"
    }
    assert python_versions == {"3.12.10"}, f"win32-python 的 program_version 不唯一: {python_versions}"

    node_versions = {
        str(entry.source["program_version"])
        for entry in catalog.entries
        if entry.source.get("runtime") == "node"
    }
    assert node_versions == {"v24.15.0"}, f"win32-node 的 program_version 不唯一: {node_versions}"


def test_runtime_verified_at_is_an_iso_date() -> None:
    """`kind: runtime` 必填 `verified_at`，且必须是 ISO 日期（`plan/04` §2.1 的 fail-closed 项）。"""
    for entry in _catalog().entries:
        if entry.source.get("kind") != contract.SOURCE_RUNTIME:
            continue
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(entry.source["verified_at"])), (
            f"{entry.name}: verified_at 不是 ISO 日期"
        )
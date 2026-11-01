#!/usr/bin/env python3
"""两道门的变异验证：逐组制造故障 → 断言门变红 → 还原 → 复绿。

这是"门绿 ≠ 门在验东西"的可跑证据（``AGENTS.md`` 末节）。纪律五条：

1. **判据有几条，变异就覆盖几条**。任一组"改错了门仍绿" = 假门，按"修探针不放宽断言"处理。
2. **靶子锚既有事实**（某份文件的某一行、某张表的某格），**不锚"某个里程碑还没完成"** ——
   后者随进度必死。
3. **每组建模都要断言字节真的变了**（``assert updated != original``），否则分支退化成 no-op
   时变异会静默变绿。
4. **阳性对照**：建模**之前**先跑一次两道门，必须绿 —— 否则"红"分不清是变异造成的还是本来就红。
5. **三态分开计**：``CAUGHT`` / ``MISSED`` / ``ERROR``（靶子漂了）；只有 CAUGHT 算通过，
   阴性对照（``expect_green``）单独计。

还原策略 = **整仓文本快照**。变异只碰文本文件，还原时把快照写回、并删掉快照里没有的多余文件，
所以"删除类"变异也能精确复原。

退出码：``0`` 全部符合预期 / ``1`` 有组不符 / ``2`` 用法错误。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

SNAPSHOT_DIRS = ("plan", "tools", "tests", "data", "docs", "fixtures")
SNAPSHOT_FILES = ("README.md", "AGENTS.md", "pyproject.toml", ".gitattributes", ".gitignore")
SKIP_DIR_NAMES = frozenset({"__pycache__", ".pytest_cache", "build", "dist"})

LAYOUT = ("tools/check_sprint_layout.py",)
DESENS = ("tools/check_desensitized.py",)
#: 发布门用 **offline 档**做靶：它是"留档结构 + 本地附件"的全量面，不联网也能跑红。
#: （``--pre-tag`` 只跑结构那一半，``--online`` 要远端 —— 靶子选中间那档最划算。）
RELEASE = ("tools/check_release.py", "--offline")
ALL_GATES = (LAYOUT, DESENS, RELEASE)


@dataclass(frozen=True)
class Mutation:
    group: str
    target: str  # "layout" | "desens"
    check_id: str  # 期望在门的结论里出现的判据名（或脱敏门的规则名）
    apply: Callable[[], None]
    expect_green: bool = False  # True = 阴性对照，门应保持绿


# ── 快照 ────────────────────────────────────────────────────────────────────
def snapshot() -> dict[str, str]:
    state: dict[str, str] = {}

    def add(path: Path) -> None:
        rel = path.relative_to(ROOT).as_posix()
        try:
            state[rel] = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            pass

    for name in SNAPSHOT_FILES:
        path = ROOT / name
        if path.is_file():
            add(path)
    for name in SNAPSHOT_DIRS:
        base = ROOT / name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if path.is_file():
                add(path)
    return state


def restore(state: dict[str, str]) -> None:
    for rel, text in state.items():
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    # 删掉快照里没有、但本轮变异可能新建的文件
    current = snapshot()
    for rel in set(current) - set(state):
        (ROOT / rel).unlink(missing_ok=True)


# ── 编辑原语（每处替换都断言"恰好一处"，防靶子漂移）─────────────────────────
def replace_once(rel: str, old: str, new: str) -> Callable[[], None]:
    def apply() -> None:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        count = text.count(old)
        if count != 1:
            raise RuntimeError(f"{rel}: 靶子出现 {count} 次，期望 1 次（靶子漂了，先修靶子）")
        updated = text.replace(old, new, 1)
        assert updated != text, f"{rel}: 替换后字节没变"
        path.write_text(updated, encoding="utf-8")

    return apply


def append_line(rel: str, text: str) -> Callable[[], None]:
    def apply() -> None:
        path = ROOT / rel
        original = path.read_text(encoding="utf-8")
        path.write_text(original + text, encoding="utf-8")
        assert path.read_text(encoding="utf-8") != original

    return apply


def delete_file(rel: str) -> Callable[[], None]:
    def apply() -> None:
        path = ROOT / rel
        assert path.is_file(), f"{rel}: 不存在，删除类变异的靶子已漂"
        path.unlink()

    return apply


def edit_status(rel: str, milestone: int, new_cell: str) -> Callable[[], None]:
    """改某份状态副本里某个里程碑的状态格。**只改一处副本** —— 这正是 STATUS 判据要抓的故障。"""

    def apply() -> None:
        path = ROOT / rel
        lines = path.read_text(encoding="utf-8").split("\n")
        hits = [i for i, line in enumerate(lines) if line.startswith(f"| M{milestone} |")]
        if len(hits) != 1:
            raise RuntimeError(f"{rel}: M{milestone} 状态行命中 {len(hits)} 条，期望 1 条")
        idx = hits[0]
        cells = lines[idx].split("|")
        cells[-2] = f" {new_cell} "
        updated = "|".join(cells)
        assert updated != lines[idx], f"{rel}: 状态格没变（靶子已过期？）"
        lines[idx] = updated
        path.write_text("\n".join(lines), encoding="utf-8")

    return apply


def edit_ledger_stale() -> None:
    """把台账里**最后一根棒**（裸 clone 可复现，属 M6）那一行改成 `⬜ 待 M0 复核`。

    为什么锚这一行、而不是锚某个"还没做完的里程碑"（K11）：

    首版锚的是字面量 ``⬜ 待 M1``，M1 翻 ✅ 时台账按纪律一起翻转，靶子当场消失 → 本组 ERROR。
    这是 K11 的同一类坑在台账上复发：**靶子不能锚"某个里程碑还没完成"**。
    现在的做法 = 按**行内容**（`裸 clone 可复现`，它属于最后一棒，最先落位、最后翻转）
    定位那一行，再把它的状态格写成"待 M0" —— M0 是**永远 ✅** 的里程碑，
    所以无论进度走到哪一棒，"待 M0" 都必然落在已 ✅ 里程碑名下，判据恒可触发。
    """

    path = ROOT / "plan/00-README总览.md"
    lines = path.read_text(encoding="utf-8").split("\n")
    needle = "裸 clone 可复现"
    hits = [i for i, line in enumerate(lines) if line.startswith("|") and needle in line]
    if len(hits) != 1:
        raise RuntimeError(f"台账靶子不见了（`{needle}` 命中 {len(hits)} 行，期望 1 行，先修靶子）")
    idx = hits[0]
    cells = lines[idx].split("|")
    cells[-2] = " ⬜ 待 M0 复核 "
    updated = "|".join(cells)
    assert updated != lines[idx], "台账状态格没变（靶子已过期？）"
    lines[idx] = updated
    path.write_text("\n".join(lines), encoding="utf-8")


# ── 变异清单：布局门 10 组 + 脱敏门 5 组 ─────────────────────────────────────
def build_mutations() -> list[Mutation]:
    return [
        # ═══ 布局门 ═══════════════════════════════════════════════════════════
        Mutation("L1-files", "layout", "LAYOUT.FILES",
                 delete_file("plan/06-交付对标与决策.md")),
        Mutation("L2-binding", "layout", "LAYOUT.BINDING_HEAD",
                 replace_once("plan/00-README总览.md",
                              "布局门：`py -3.12 tools/check_sprint_layout.py`",
                              "布局门：`py -3.12 tools/run-layout.py`")),
        Mutation("L3-sections", "layout", "LAYOUT.SECTIONS",
                 replace_once("plan/06-交付对标与决策.md", "## 2. 风险登记", "## 2. 风险")),
        Mutation("L4-doc-tools-missing", "layout", "LAYOUT.DOC_TOOLS",
                 append_line("plan/02-架构与技术选型.md", "\n\n见 `tools/does_not_exist.py`。\n")),
        # L4b stale 分支：登记项属于已 ✅ 的里程碑 → 必须变红。
        # 靶子必须是**文档点名 + 实物不存在 + 登记在已 ✅ 里程碑**三者同时成立 ——
        # 只改登记表不行：`build_catalog.py` 实物在位，判据在 `is_file()` 那一步就 `continue` 了
        # （本项目实测：首版靶子这么写，门恒绿，看起来像假门，实际是靶子没咬住 stale 分支）。
        Mutation("L4b-doc-tools-stale", "layout", "LAYOUT.DOC_TOOLS",
                 _register_stale_tool()),
        Mutation("L5-status", "layout", "LAYOUT.STATUS",
                 edit_status("plan/05-里程碑与发布.md", 0, "⬜")),
        Mutation("L6-handoffs-missing", "layout", "LAYOUT.HANDOFFS",
                 delete_file("plan/HANDOFF-M0.md")),
        Mutation("L6b-handoffs-section", "layout", "LAYOUT.HANDOFFS",
                 replace_once("plan/HANDOFF-M0.md",
                              "## 二、当前事实·状态不变量（下一棒动手前必须知道）",
                              "## 二、背景")),
        # L6c：**当前里程碑的入口缺失**分支。这是首版门漏掉的那一半 ——
        # 首版只遍历 `done`，于是"上一棒做完却没给下一棒留入口"门照旧全绿
        # （本项目实测：M1 收尾后 HANDOFF-M2.md 不存在，门报"2 份交接单齐 全绿"）。
        # 靶子 = 删掉**当前在做的里程碑**的入口（= 最小 ⬜ 那个的 HANDOFF），
        # 不锚具体编号：随进度推进自动指向新的当前棒，不会像 L4b 那样漂。
        Mutation("L6c-handoffs-current-missing", "layout", "LAYOUT.HANDOFFS",
                 _delete_current_handoff()),
        # L6d：**超前入口**分支（给还没到的里程碑预写入口 = 给没跑的棒编记录）。
        Mutation("L6d-handoffs-lookahead", "layout", "LAYOUT.HANDOFFS",
                 _create_lookahead_handoff()),
        # 靶子必须落在**缺口列本身**（首格）。首版把 `M0` 写进"内容"列 → 判据读的是缺口列，
# 门正确地没报，看起来像假门 —— 实际是靶子瞄错了列（这一类只有变异验证能抓出来）。
        Mutation("L7-gaps", "layout", "LAYOUT.GAPS",
                 replace_once("plan/06-交付对标与决策.md",
                              "| G2 | 编目真实条目数 |",
                              "| G2（M0 遗留） | 编目真实条目数 |")),
        Mutation("L8-ledger", "layout", "LAYOUT.LEDGER", edit_ledger_stale),
        Mutation("L9-release", "layout", "LAYOUT.RELEASE",
                 _flip_m6_done()),
        Mutation("L10-negative", "layout", "LAYOUT.STATUS",
                 append_line("plan/00-README总览.md",
                             "\n> 当前状态：M0 完成，M6 未开工，未验证项保持 ⬜。\n"),
                 expect_green=True),
        # ═══ 脱敏门 ═══════════════════════════════════════════════════════════
        # 变异样本**在运行时拼出来**，本文件自身因此不含被禁字面量 ——
        # 这样它不需要进 `SELF_EXEMPT`（脱敏门的自豁免面越窄，越能证明门在扫真内容）。
        Mutation("D1-absolute-path", "desens", "absolute-session-path",
                 append_line("README.md", _probe_absolute_path())),
        Mutation("D2-msys-path", "desens", "msys-user-path",
                 append_line("README.md", _probe_msys_path())),
        Mutation("D3-host-username", "desens", "host-username", _host_username()),
        Mutation("D4-loopback", "desens", "loopback-proxy",
                 append_line("README.md", _probe_loopback())),
        Mutation("D5-negative-placeholder", "desens", "absolute-session-path",
                 append_line("README.md", _probe_placeholder()),
                 expect_green=True),
        # ═══ 发布门（--offline 档）═══════════════════════════════════════════════
        # 靶子锚**留档的既有事实**（两栏标题 / 覆盖对账小节 / 三态行 / 力一的名字行），
        # 不锚"还没到的发布步骤" —— 「tag 打了没有」随进度变，而这几样在 tag 前后都在。
        Mutation("R1-doc-missing", "release", "RELEASE.DOC",
                 delete_file("plan/RELEASE-M6.md")),
        Mutation("R2-column", "release", "RELEASE.DOC",
                 replace_once("plan/RELEASE-M6.md", "## 二、tag 后追加", "## 二、收尾")),
        Mutation("R3-coverage", "release", "RELEASE.DOC",
                 replace_once("plan/RELEASE-M6.md", "### 1.4 覆盖对账", "### 1.4 对账表")),
        Mutation("R4-name", "release", "RELEASE.NAME",
                 _strip_recheck_date()),
        Mutation("R5-self-ref", "release", "RELEASE.TREE",
                 _append_self_ref_to_head()),
        Mutation("R6-states", "release", "RELEASE.DOC",
                 _make_all_states_noop()),
        Mutation("R6b-multi-state", "release", "RELEASE.DOC",
                 _make_one_row_two_states()),
        Mutation("R7-negative", "release", "RELEASE.DOC",
                 append_line("plan/RELEASE-M6.md", "\n> 追加一句与判据无关的说明。\n"),
                 expect_green=True),
    ]


def _probe_absolute_path() -> str:
    drive, sep = "D", ":"
    return f"\n<!-- mutation: {drive}{sep}/somewhere/leaked -->\n"


def _probe_msys_path() -> str:
    return "\n<!-- mutation: /" + "c/Users/someone/x -->\n"


def _probe_loopback() -> str:
    return "\n<!-- mutation: 127." + "0.0.1:7897 -->\n"


def _probe_placeholder() -> str:
    return "\n<!-- mutation: C:" + "\\Users\\<user>\\x -->\n"


def _strip_recheck_date() -> Callable[[], None]:
    """把 §一 里的复核日期整片抹掉 —— ``RELEASE.NAME`` 必红。

    这一组咬的是**"名字占用记录没带日期"**这个分支：没有日期，就没法把它和 ``plan/06`` §4.1
    的旧快照区分开，判据也就失去意义。只删日期、保留 PyPI/404/GitHub 三个词 ——
    这样红的必然是日期那一条，不会与别的分支混在一起。
    """

    def apply() -> None:
        path = ROOT / "plan" / "RELEASE-M6.md"
        text = path.read_text(encoding="utf-8")
        head, sep, tail = text.partition("## 二、")
        assert sep, "留档里找不到 `## 二、` 分栏 —— 靶子漂了"
        stripped = re.sub(r"20\d{2}-\d{2}-\d{2}", "某日", head)
        assert stripped != head, "§一 里没有日期可抹（靶子已过期？）"
        path.write_text(stripped + sep + tail, encoding="utf-8")

    return apply


def _append_self_ref_to_head() -> Callable[[], None]:
    """把附件 sha256 形态的值塞进 §一（tag 前事实）—— ``RELEASE.TREE`` 必红。

    值**运行时拼出来**（本文件自身因此不含 64 位 hex 字面量，不必为本组开豁免）。
    """

    def apply() -> None:
        path = ROOT / "plan" / "RELEASE-M6.md"
        text = path.read_text(encoding="utf-8")
        head, sep, tail = text.partition("## 二、")
        assert sep, "留档里找不到 `## 二、` 分栏 —— 靶子漂了"
        digest = "sha256: " + "0123456789abcdef" * 4
        updated = head + f"\n> 附件 sha256（变异注入）: {digest}\n\n" + sep + tail
        assert updated != text
        path.write_text(updated, encoding="utf-8")

    return apply


def _make_all_states_noop() -> Callable[[], None]:
    """把三态行**全部**改成「不适用」或「待首推」→ `RELEASE.DOC` 必红。

    咬的是「**没有任何一条实现**」这一支：拿三态表当免票（什么都写"不适用/待首推"）
    是这类留档最经济的作弊路径 —— 条数够、两栏齐、表看着满，但一句实话没有。

    首版这一组同时改"全挂同一态 + 一行挂两态"，M6 收尾时判据分支演进到
    「至少一条实现 + 一行只挂一个态」之后，**只改前者恰好落在合法区间**（全挂实现 = 合法
    终态），于是本组 MISSED。处置不是放宽判据，而是**按判据分支拆成两组**：
    这里咬"没有实现态"，`R6b` 咬"一行挂多态"。
    """

    def apply() -> None:
        path = ROOT / "plan" / "RELEASE-M6.md"
        text = path.read_text(encoding="utf-8")
        updated = text.replace("| 实现 |", "| 不适用 |")
        assert updated != text, "三态列没变（靶子已过期？留档里已经没有『实现』行了）"
        path.write_text(updated, encoding="utf-8")

    return apply


def _make_one_row_two_states() -> Callable[[], None]:
    """让一条三态行同时挂两个标签 → `RELEASE.DOC` 必红（一行只能表一个态）。

    与 `R6` 是两个独立分支：留档完全可以"有实现行、条数够"，但若某行写着
    「实现 待首推」，那等于没表态 —— 这一支只有本组能咬到。
    """

    def apply() -> None:
        path = ROOT / "plan" / "RELEASE-M6.md"
        text = path.read_text(encoding="utf-8")
        updated = text.replace("| 实现 |", "| 实现 待首推 |", 1)
        assert updated != text, "没有『实现』行可改（靶子已过期？）"
        path.write_text(updated, encoding="utf-8")

    return apply


def _register_stale_tool() -> Callable[[], None]:
    """造一个真实的 stale 登记：文档点名 ``tools/not_yet.py``（实物不存在），
    且 ``PENDING_TOOLS`` 把它登记在**已 ✅ 的 M0** 名下 → stale 分支必红。

    **靶子不在 ``PENDING_TOOLS`` 的真实条目上插一行**（首版这么写）：
    真实条目会随进度按纪律被删掉（M1 删 `fetch_sources.py` 那行、M6 删 `check_release.py`
    那行），于是本组在那一棒必然 ERROR —— 那不是门坏了，是**靶子绑了仓库进度**（K11 同一族）。
    现在的做法 = **把整张表换成合成表**（只留 `not_yet.py -> M0`）：M0 永远 ✅，
    所以"文档点名 + 实物不存在 + 登记在已 ✅ 里程碑"这三件事恒成立。
    """

    def apply() -> None:
        path = ROOT / "tools/check_sprint_layout.py"
        text = path.read_text(encoding="utf-8")
        anchor = "PENDING_TOOLS: dict[str, int] = {"
        assert text.count(anchor) == 1, "PENDING_TOOLS 定义行漂了（靶子锚不住）"
        # 把 `= {` 之后到下一个空行之前的内容整体换成合成登记
        start = text.index(anchor) + len(anchor)
        end = text.find("\n#", start)
        assert end > start, "PENDING_TOOLS 之后没有 `#` 注释行 —— 切片边界漂了"
        updated = text[:start] + '\n    "tools/not_yet.py": 0,\n}\n' + text[end:]
        assert updated != text
        path.write_text(updated, encoding="utf-8")
        doc = ROOT / "plan/02-架构与技术选型.md"
        doc.write_text(
            doc.read_text(encoding="utf-8") + "\n\n见 `tools/not_yet.py`。\n",
            encoding="utf-8",
        )

    return apply


def _milestone_states() -> dict[int, str]:
    """从 ``plan/00`` 的里程碑表读 ``{编号: 状态格}`` —— 变异靶子从**事实**取，不写死编号。"""
    lines = (ROOT / "plan/00-README总览.md").read_text(encoding="utf-8").split("\n")
    states: dict[int, str] = {}
    for line in lines:
        match = re.match(r"^\|\s*M(\d+)\s*\|", line)
        if not match:
            continue
        cells = line.split("|")
        states[int(match.group(1))] = cells[-2].strip()
    return states


def _is_done(cell: str) -> bool:
    return "✅" in cell


def _current_milestone() -> int | None:
    states = _milestone_states()
    pending = sorted(k for k, cell in states.items() if not _is_done(cell))
    return pending[0] if pending else None


def _insert_synthetic_milestones(count: int) -> list[int]:
    """在 ``plan/00`` 状态表里临时插 ``count`` 行合成里程碑（状态 ⬜、号比现有最大值大）。

    返回插入的编号（升序）。还原由 harness 的整树快照负责。

    **为什么必须能"没有未完成里程碑"时也造得出来**（M6 末棒实测）：
    ``L6c`` / ``L6d`` 首版都断言"存在未完成的里程碑"，于是全仓打完最后一棒时两组一起
    ERROR —— 那不是门坏了，是**变异靶子把仓库进度绑进了判据**。合成行不造假：
    被测的是门的"当前入口缺失"与"超前入口"两个分支，不是仓库状态。
    """
    path = ROOT / "plan" / "00-README总览.md"
    lines = path.read_text(encoding="utf-8").split("\n")
    states = _milestone_states()
    if not states:
        raise RuntimeError("plan/00 里没有里程碑行（靶子锚不住）")
    anchor = max(
        i for i, line in enumerate(lines) if re.match(r"^\|\s*M\d+\s*\|", line)
    )
    highest = max(states)
    inserted = [highest + k for k in range(1, count + 1)]
    new_lines = [
        f"| M{k} | 变异注入的合成里程碑（本组用完即还原） | — | ⬜ |" for k in inserted
    ]
    lines[anchor + 1 : anchor + 1] = new_lines
    path.write_text("\n".join(lines), encoding="utf-8")
    return inserted


def _delete_current_handoff() -> Callable[[], None]:
    """删掉**当前在做的里程碑**的入口文件 —— 门必须报"上一棒没留入口"。

    当前里程碑已不存在（末棒打完）时，先合成一个；**并且故意不建它的入口** ——
    那正是本组要的靶子（门应报"当前在做的里程碑缺入口"）。
    """

    def apply() -> None:
        current = _current_milestone()
        if current is None:
            _insert_synthetic_milestones(1)
            current = _current_milestone()
        if current is None:  # pragma: no cover - 合成之后不可能仍为空
            raise RuntimeError("合成之后仍没有当前里程碑（靶子构造失败）")
        rel = f"plan/HANDOFF-M{current}.md"
        path = ROOT / rel
        if path.is_file():
            path.unlink()
        # 门必须**真的**找不到它：不建就是"上一棒没留入口"的精确形态

    return apply


def _create_lookahead_handoff() -> Callable[[], None]:
    """给**还早的**里程碑预写入口 —— 门必须报"超前入口"。

    找"比当前里程碑更晚、状态仍是 ⬜"的号；一个都没有（末棒已打完 / 只剩当前那一根）时，
    用 ``_insert_synthetic_milestones`` 造两个：一个当"当前"，一个当"未来"。
    判据看的是"状态 ⬜ 且不是当前里程碑的编号有没有入口文件"，合成的第二行刚好是它的靶子。
    """

    def apply() -> None:
        current = _current_milestone()
        states = _milestone_states()
        far = [k for k, cell in sorted(states.items()) if not _is_done(cell) and k != current]
        if not far:
            if current is None:
                inserted = _insert_synthetic_milestones(2)
                current, far = inserted[0], [inserted[1]]
            else:
                far = _insert_synthetic_milestones(1)
        rel = f"plan/HANDOFF-M{far[-1]}.md"
        if (ROOT / rel).is_file():
            raise RuntimeError(f"{rel} 本来就存在 —— 靶子已漂（先确认它确实不该有）")
        (ROOT / rel).write_text(
            "# 超前入口（变异注入）\n\n"
            "当前进度 当前事实 待办 既定口径 环境坑 DoD 命令速查\n",
            encoding="utf-8",
        )

    return apply


def _flip_m6_done() -> Callable[[], None]:
    """把**发布里程碑**翻成 ✅ 但**删掉留档** → 状态一致，`LAYOUT.RELEASE` 必红。

    靶子随进度自适应的两态：

    * **发布里程碑尚未 ✅**（M6 在做）：两处副本同时翻 ✅ + 删留档。
      单翻状态而不删留档是**合法终态**（M6 实测首版因此 MISSED —— 门正确地绿了）。
    * **发布里程碑已 ✅**（末棒打完）：翻状态已无变化，靶子改为"删留档 + 保留 ✅" ——
      这正是 `LAYOUT.RELEASE` 要抓的分支：**已 ✅ 却没有收尾记录**。
    """
    import check_sprint_layout as layout  # noqa: PLC0415 - 与门的配置同源，不写死编号

    def apply() -> None:
        release = ROOT / "plan" / f"RELEASE-M{layout.RELEASE_MILESTONE}.md"
        assert release.is_file(), "留档不存在 —— 抓不到「已 ✅ 但无记录」这个分支"
        release.unlink()
        states = _milestone_states()
        target = layout.RELEASE_MILESTONE
        if not _is_done(states.get(target, "")):
            edit_status("plan/00-README总览.md", target, "✅")()
            edit_status("plan/05-里程碑与发布.md", target, "✅")()

    return apply


def _host_username() -> Callable[[], None]:
    """本机用户名由规则表本身给出，变异从同一处取，避免两处漂移。"""
    sys.path.insert(0, str(ROOT / "tools"))
    import check_desensitized as gate  # noqa: PLC0415

    pattern = next(rule.pattern for rule in gate.RULES if rule.id == "host-username")
    sample = pattern.pattern.replace(r"\b", "").replace("\\", "")
    return append_line("README.md", f"\n<!-- mutation: {sample} -->\n")


# ── 执行 ────────────────────────────────────────────────────────────────────
GATE_BY_TARGET = {"layout": LAYOUT, "desens": DESENS, "release": RELEASE}


def run_gate(argv: tuple[str, ...]) -> tuple[int, str]:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        [PY, *argv], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=env
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if args:
        sys.stderr.write(f"verify_gates: unknown argument {args[0]}\n")
        return 2

    baseline = snapshot()

    # 阳性对照：建模之前三道门必须绿
    # （发布门用 --offline 档：它是"留档结构 + 本地附件"的全量面，不联网也能跑红）
    for gate in ALL_GATES:
        code, out = run_gate(gate)
        if code != 0:
            sys.stdout.write(f"FAIL  阳性对照：{' '.join(gate)} 本来就红（rc={code}）\n{out}\n")
            return 1

    results: list[tuple[str, str, str]] = []  # (group, status, detail)
    for mutation in build_mutations():
        gate = GATE_BY_TARGET[mutation.target]
        try:
            mutation.apply()
            code, out = run_gate(gate)
        except Exception as exc:  # noqa: BLE001 - 靶子漂了要可读，不可中断
            results.append((mutation.group, "ERROR", f"变异没能施加：{exc}"))
            restore(baseline)
            continue

        restore(baseline)

        if mutation.expect_green:
            ok = code == 0
            results.append(
                (mutation.group, "CAUGHT" if ok else "MISSED",
                 "阴性对照：门按预期保持绿" if ok else f"阴性对照失败：门变红了（rc={code}）")
            )
            continue

        if code == 0:
            results.append((mutation.group, "MISSED", f"门仍绿 —— {mutation.check_id} 是假门"))
        elif mutation.check_id not in out:
            results.append(
                (mutation.group, "MISSED", f"门红了但没报 {mutation.check_id}（红了别的地方）")
            )
        else:
            results.append((mutation.group, "CAUGHT", f"{mutation.check_id} 如预期变红"))

    # 还原后必须复绿
    for gate in ALL_GATES:
        code, out = run_gate(gate)
        if code != 0:
            sys.stdout.write(f"FAIL  还原后未复绿（{' '.join(gate)} rc={code}）\n{out}\n")
            return 1

    bad = [r for r in results if r[1] != "CAUGHT"]
    sys.stdout.write("变异验证（三道门）\n" + "=" * 60 + "\n")
    for group, status, detail in results:
        sys.stdout.write(f"{status:7} {group:28} {detail}\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write(
        f"共 {len(results)} 组：{len(results) - len(bad)} 符合预期 / {len(bad)} 不符；"
        "还原后三道门复绿\n"
    )
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
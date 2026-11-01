#!/usr/bin/env python3
"""布局门（方法论装订第②件）：把"项目还长在方法论上"变成可跑红的断言。

来源：``ai-tool-project-sprint`` 的 ``references/templates/check-sprint-layout.mjs``，
按同一判据集用 Python 重写（**判据不改**，只是换成项目自己的语言，见 ``plan/06`` §4.1）。

六条纪律（模板要求，逐条落在这里）：

1. **非空跑自证**：结论行打印"这轮扫到了几个"——否则"0 命中"与"扫了 0 个"输出相同。
2. **逐副本采集、不取任何一处当真值**：``LAYOUT.STATUS`` 把每份副本的状态收成集合再对，
   避免"自我参照真值源"（在某副本里翻状态，该里程碑直接掉出待检集合 → 恒绿）。
3. **每份副本单独记命中行数**：0 行的副本是合法配置，但**必须可见**；合计 0 行 = 真空跑 = FAIL。
4. **永不崩**：任一步异常报一条 FAIL 并继续，不是 traceback 逃逸。
5. **判据只落仓库内文件**：不读 git 元数据（浅克隆/无 .git 树里会翻转）。
6. **超集宽容**：只断言"必需节都存在"，不断言"节数恰好等于 N"。

退出码：``0`` 全绿 / ``1`` 有 FAIL / ``2`` 用法错误。
"""

from __future__ import annotations

import re
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]

CHECKS: list[tuple[str, bool, str]] = []
SCANNED = {"docs": 0, "handoffs": 0, "copies": 0, "doc_tools": 0, "gap_rows": 0, "ledger_rows": 0}


def add(check_id: str, ok: bool, detail: str) -> None:
    CHECKS.append((check_id, ok, detail))


def read(rel: str) -> str | None:
    path = ROOT / rel
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


# ── 配置（改这里，不要改判据）────────────────────────────────────────────────
REQUIRED_FILES = [
    "AGENTS.md",
    "README.md",
    "data/README.md",
    "data/gaps.md",
    "plan/00-README总览.md",
    "plan/01-题目文档.md",
    "plan/02-架构与技术选型.md",
    "plan/03-模块详设.md",
    "plan/04-数据计划.md",
    "plan/05-里程碑与发布.md",
    "plan/06-交付对标与决策.md",
]

#: 装订行：三个锚点**必须同现于一行**（顺序无关）。写死顺序会假红，写成"或"关系会假绿。
BINDING_LINE = re.compile(
    r"^>(?=.*ai-tool-project-sprint)(?=.*check_sprint_layout)(?=.*20\d{2}-\d{2}-\d{2}).*$",
    re.MULTILINE,
)

REQUIRED_SECTIONS: dict[str, tuple[str, ...]] = {
    "plan/00-README总览.md": ("文档索引", "决策记录", "承诺-证据台账", "里程碑"),
    "plan/01-题目文档.md": ("任务要求", "评分标准", "边界与非目标"),
    "plan/02-架构与技术选型.md": ("分层", "构建"),
    "plan/03-模块详设.md": ("模块①", "模块②", "模块③", "模块④", "契约块"),
    "plan/04-数据计划.md": ("数据清单", "真值纪律", "数值口径"),
    "plan/05-里程碑与发布.md": ("DoD", "已知未验证项"),
    "plan/06-交付对标与决策.md": ("评分对标", "风险登记"),
    "data/README.md": ("依据查证记录", "数值口径"),
    "data/gaps.md": ("逐条缺口", "计数口径"),
}

#: 交接单七节（含「当前事实·状态不变量」—— 那正是下一棒逐条消费的一节）。
HANDOFF_SECTIONS = ("当前进度", "当前事实", "待办", "既定口径", "环境坑", "DoD", "命令速查")

#: 项目**已声明**的豁免：本项目一个都不豁免（M0 也写交接单）。
EXEMPT_MILESTONES: frozenset[int] = frozenset()
HANDOFF_FORMAT_FROM = 0
#: 末棒要不要交接单：False = 要。
#:
#: **交接单的语义（项目规则，2026-11-01 用户订正）**：
#: ``plan/HANDOFF-M<k>.md`` 按**它开哪个里程碑**命名，不按"哪一棒写完它"命名 ——
#: 它不是"第 k 棒的收尾单"，而是 **M<k> 的入口文件**（进这个里程碑就读它）。
#:
#: 由此推出两条判据（首版只做了第一条，于是"上一棒没给下一棒留入口"这种情况门完全看不见）：
#: 1. **每个已开的里程碑都要有入口**：已 ✅ 的那些 + **当前在做的那个**（= 最小的 ⬜）。
#: 2. **不得超前**：状态仍是 ⬜ 且不是当前里程碑的编号，不许有入口文件 ——
#:    否则等于给一支还没跑的棒编好了"当前进度 + 证据"，而那整张表只能是编的。
HANDOFF_EXEMPT_LAST = False

#: 状态副本 = **2 张表**。``README.md`` **刻意不承载状态**（随包读者没有 plan/），
#: 所以它不在本表里；``plan/00`` §3 台账作为第 3 份由 ``LAYOUT.LEDGER`` 单独判。
STATUS_COPIES = (
    ("plan/00-README总览.md", "里程碑表"),
    ("plan/05-里程碑与发布.md", "状态表"),
)

#: 只认"状态行"：表格行且首格就是里程碑号（不扫自由文本 —— 散文状态行会张冠李戴）。
STATUS_LINE = re.compile(r"^\|\s*\*{0,2}M(\d+)\b")
PENDING_MARKERS = ("⬜", "🟡", "未开始", "未执行", "待执行", "待确认")

#: 发布里程碑固定为 M6（``plan/00`` §4 / ``plan/05`` §1）。未 ✅ 时 LAYOUT.RELEASE 报 PASS 并写明不适用。
RELEASE_MILESTONE = 6

#: 文档已点名、但**还没到该里程碑**的脚本。该里程碑翻 ✅ 后必须删掉本条，否则 stale 分支变红。
#:
#: M1 落位时 `tools/fetch_sources.py` 的登记项与本笔**同笔删掉** —— 只落脚本不删登记，
#: stale 分支会报"已 ✅ 的里程碑名下还挂着待办"（HANDOFF-M0 §二 第 7 条）。
#: 本表的靶子在 `tools/verify_gates.py` 的 L4b 组里锚 `check_release.py` 那一行。
PENDING_TOOLS: dict[str, int] = {
    "tools/check_release.py": 6,  # plan/00 M6 DoD / plan/05 §2：发布门
}
#: 确实不打算实现的脚本（理由必须写在注释里）。本项目为空。
EXEMPT_TOOLS: frozenset[str] = frozenset()

DOC_TOOLS_PATTERN = re.compile(r"(?<![\w./-])tools/[\w.-]+\.(?:py|mjs|js|cjs|sh|ps1)")
RELEASE_COVERAGE = re.compile(r"^#{2,3}.*覆盖对账", re.MULTILINE)
RELEASE_TWO_COLUMNS = (
    re.compile(r"^##\s*一、tag\s*前事实", re.MULTILINE),
    re.compile(r"^##\s*二、tag\s*后追加", re.MULTILINE),
)


# ── 判据 ────────────────────────────────────────────────────────────────────
def check_required_files() -> None:
    missing = [rel for rel in REQUIRED_FILES if not (ROOT / rel).is_file()]
    SCANNED["docs"] = len(REQUIRED_FILES) - len(missing)
    add(
        "LAYOUT.FILES",
        not missing,
        f"缺: {','.join(missing)}" if missing else f"{SCANNED['docs']} 份齐备",
    )


def check_binding_head() -> None:
    text = read("plan/00-README总览.md") or ""
    ok = bool(BINDING_LINE.search(text))
    add(
        "LAYOUT.BINDING_HEAD",
        ok,
        "plan/00 顶部有装订行（三锚点齐）"
        if ok
        else "plan/00 顶部缺装订行（需同现：方法论名 + 布局门命令 + 装订日期）",
    )


def check_sections() -> None:
    bad: list[str] = []
    for rel, needles in REQUIRED_SECTIONS.items():
        text = read(rel)
        if text is None:
            continue  # 缺文件已由 LAYOUT.FILES 报过
        missing = [n for n in needles if n not in text]
        if missing:
            bad.append(f"{rel}: {'/'.join(missing)}")
    add(
        "LAYOUT.SECTIONS",
        not bad,
        "；".join(bad) if bad else f"{len(REQUIRED_SECTIONS)} 份小节齐备",
    )


def collect_states() -> tuple[dict[int, set[str]], dict[str, int]]:
    """逐副本采集状态。**真值不取自任何一个副本**。"""
    states: dict[int, set[str]] = {}
    rows_by_copy: dict[str, int] = {}
    for rel, _kind in STATUS_COPIES:
        text = read(rel)
        if text is None:
            rows_by_copy[rel] = 0
            continue
        SCANNED["copies"] += 1
        rows = 0
        for line in text.split("\n"):
            match = STATUS_LINE.match(line)
            if not match:
                continue
            rows += 1
            pending = any(marker in line for marker in PENDING_MARKERS)
            states.setdefault(int(match.group(1)), set()).add("pending" if pending else "done")
        rows_by_copy[rel] = rows
    return states, rows_by_copy


def check_status_agreement(states: dict[int, set[str]], rows_by_copy: dict[str, int]) -> None:
    conflicts = [
        f"M{k} 在副本间状态不一致（{' vs '.join(sorted(values))}）"
        for k, values in sorted(states.items())
        if len(values) > 1
    ]
    total = sum(rows_by_copy.values())
    per_copy = " ".join(
        f"{Path(rel).name}:{rows}" for rel, rows in sorted(rows_by_copy.items())
    )
    if conflicts:
        add("LAYOUT.STATUS", False, "；".join(conflicts))
        return
    if total == 0:
        add("LAYOUT.STATUS", False, f"所有副本合计 0 行状态行（判据空跑）：{per_copy}")
        return
    add(
        "LAYOUT.STATUS",
        True,
        f"{SCANNED['copies']} 处副本 × {len(states)} 个里程碑 状态全一致（行数 {per_copy}）",
    )


def check_handoffs(done: Iterable[int], all_milestones: Iterable[int]) -> None:
    """交接单 = **里程碑入口文件**（不是"某棒的收尾单"）。

    两条判据（缺一条就是假门）：

    * ① **每个已开的里程碑都要有入口** = 已 ✅ 的 + **当前在做的那个**（最小的 ⬜）。
      首版只遍历 ``done``，于是"M1 做完了却没给 M2 留入口"这种情况门照旧全绿 ——
      门看起来在管交接单，实际只管"完成过的"，漏掉的正是最该管的那个。
    * ② **不得超前**：状态仍是 ⬜ 且不是当前里程碑的编号，不许有入口文件。
      否则就是给一支还没跑的棒编好了"当前进度 + 证据"，那整张表只能是编的。
    """
    done = sorted(done)
    milestones = sorted(all_milestones)
    last = max(milestones + [0])
    pending = [k for k in milestones if k not in done]
    #: 当前在做的里程碑 = 最小的未完成号（全部完成时没有"当前"）
    current = pending[0] if pending else None
    required = [k for k in milestones if k in done or k == current]
    missing: list[str] = []
    for k in required:
        if k in EXEMPT_MILESTONES:
            continue
        if HANDOFF_EXEMPT_LAST and k == last:
            continue
        rel = f"plan/HANDOFF-M{k}.md"
        text = read(rel)
        if text is None:
            role = "已完成里程碑" if k in done else "**当前在做的里程碑**（上一棒没留入口）"
            missing.append(f"{rel}(缺：{role})")
            continue
        SCANNED["handoffs"] += 1
        if k < HANDOFF_FORMAT_FROM:
            continue
        lack = [name for name in HANDOFF_SECTIONS if name not in text]
        if lack:
            missing.append(f"{rel}(缺节: {'/'.join(lack)})")

    # ② 不得超前：给还没到的里程碑预写入口
    ahead: list[str] = []
    if current is not None:
        for k in pending:
            if k == current:
                continue
            rel = f"plan/HANDOFF-M{k}.md"
            if (ROOT / rel).is_file():
                ahead.append(rel)
    if ahead:
        missing.append(f"超前入口（状态仍 ⬜ 且不是当前里程碑，等于给没跑的棒编记录）: {', '.join(ahead)}")

    expected = [k for k in required if k not in EXEMPT_MILESTONES]
    detail_tail = f"应备 {len(expected)} 份（已 ✅ {len(done)} + 当前 M{current}）" if current is not None else f"应备 {len(expected)} 份（全部已完成，无当前里程碑）"
    add(
        "LAYOUT.HANDOFFS",
        not missing,
        "；".join(missing)
        if missing
        else f"{SCANNED['handoffs']} 份交接单齐（{detail_tail}；无超前入口）",
    )


def _strip_evidence_cell(cell: str) -> str:
    """匹配前剥掉行内代码与文件名 —— 否则"证据在哪份文件"会被判成"仍提 M<k>"（假红）。"""
    cell = re.sub(r"`[^`]*`", " ", cell)
    return re.sub(r"[\w./-]+\.(?:md|py|mjs|js|json|toml|txt|yaml|yml)", " ", cell)


def check_stale_gaps(done: Iterable[int]) -> None:
    """`plan/06` §3 的缺口表：已 ✅ 的里程碑号不得出现。

    扫描面 = 表头 → **首条非表格行即止**（不是"到文件末尾"，否则后面章节的表格会被误扫）。
    行数进结论：0 行是合法终态，但必须能与"表头搬家了/判据空跑"区分。

    **列号必须按表头名定位，不能按位置取**（假门族②：模板早期写 ``len(cells) - 2``，
    假设缺口是最后一列；本项目把缺口放在**第一列**，于是判据读的是"状态"列 ——
    把 ``M0`` 写进缺口格，门仍绿，变异验证当场抓出这条假门）。
    """
    done = sorted(done)
    lines = (read("plan/06-交付对标与决策.md") or "").split("\n")
    header_idx = next(
        (i for i, line in enumerate(lines) if line.startswith("|") and "缺口" in line), -1
    )
    if header_idx < 0:
        add("LAYOUT.GAPS", False, "plan/06 找不到含『缺口』表头的表（判据表搬走了？）")
        return
    header_cells = [c.strip() for c in lines[header_idx].split("|")]
    col = next((i for i, name in enumerate(header_cells) if "缺口" in name), -1)
    if col < 0:
        add("LAYOUT.GAPS", False, "缺口表头里找不到『缺口』列（列名改了？）")
        return
    stale: list[str] = []
    counted = 0
    for line in lines[header_idx + 2 :]:
        if not line.startswith("|"):
            break  # 表结束
        counted += 1
        cells = line.split("|")
        if col >= len(cells):
            continue
        cell = _strip_evidence_cell(cells[col])
        for k in done:
            if re.search(rf"(^|[^0-9A-Za-z])M{k}([^0-9]|$)", cell):
                stale.append(f"plan/06 缺口列仍提 M{k}: {cell.strip()[:80]}")
    SCANNED["gap_rows"] = counted
    add(
        "LAYOUT.GAPS",
        not stale,
        "；".join(stale) if stale else f"plan/06 缺口列扫了 {counted} 行，无已 ✅ 里程碑",
    )


def check_ledger(done: Iterable[int]) -> None:
    """承诺-证据台账 = 第 3 份状态副本，但它不在"状态表"里 → 单独一条判据。"""
    done = sorted(done)
    lines = (read("plan/00-README总览.md") or "").split("\n")
    header_idx = next(
        (
            i
            for i, line in enumerate(lines)
            if line.startswith("|") and "承诺" in line and "状态" in line
        ),
        -1,
    )
    if header_idx < 0:
        add("LAYOUT.LEDGER", False, "plan/00 找不到『承诺-证据台账』表头（承诺项与状态列）")
        return
    SCANNED["copies"] += 1  # 它是第 3 份状态副本，要进"扫到了几个"的计数
    bad: list[str] = []
    rows = 0
    for line in lines[header_idx + 2 :]:
        if not line.startswith("|"):
            break
        rows += 1
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 2:
            continue
        status = cells[-2]
        if not re.search(r"[⬜🟡]|未开始|待\s*M\d|待开工", status):
            continue
        for k in done:
            if re.search(rf"(^|[^0-9A-Za-z])M{k}([^0-9]|$)", status):
                bad.append(f"台账行仍挂未完成: {status[:60]}")
    SCANNED["ledger_rows"] = rows
    if rows == 0:
        add("LAYOUT.LEDGER", False, "台账表 0 行 —— 判据空跑")
        return
    add(
        "LAYOUT.LEDGER",
        not bad,
        "；".join(bad) if bad else f"台账 {rows} 行，已成 ✅ 的里程碑无未完成标记",
    )


def check_release_doc(done: Iterable[int]) -> None:
    done = sorted(done)
    if RELEASE_MILESTONE == 0 or RELEASE_MILESTONE not in done:
        add(
            "LAYOUT.RELEASE",
            True,
            f"发布里程碑 M{RELEASE_MILESTONE} 未完成，收尾记录尚不适用（已扫 {len(done)} 个 ✅ 里程碑）",
        )
        return
    release = read(f"plan/RELEASE-M{RELEASE_MILESTONE}.md")
    wrapup = read(f"plan/WRAPUP-M{RELEASE_MILESTONE}.md")
    if release is None and wrapup is None:
        add(
            "LAYOUT.RELEASE",
            False,
            f"缺 plan/RELEASE-M{RELEASE_MILESTONE}.md 或 plan/WRAPUP-M{RELEASE_MILESTONE}.md",
        )
        return
    if release is not None:
        two_cols = all(pattern.search(release) for pattern in RELEASE_TWO_COLUMNS)
        coverage = bool(RELEASE_COVERAGE.search(release))
        rows = len(re.findall(r"^\|.*(实现|不适用|待首推).*\|$", release, re.MULTILINE))
        add(
            "LAYOUT.RELEASE",
            two_cols and coverage and rows >= 3,
            f"两栏:{two_cols} 覆盖对账小节:{coverage} 三态行数:{rows}",
        )
        return
    add("LAYOUT.RELEASE", True, "WRAPUP 形态")


def check_documented_tools(done: Iterable[int]) -> None:
    """文档点名的 ``tools/*.py`` 必须有实物 —— 三个状态，不是一个白名单。"""
    done = sorted(done)
    docs = ["AGENTS.md"] + sorted(
        f"plan/{p.name}" for p in (ROOT / "plan").glob("*.md")
    )
    referenced: set[str] = set()
    for rel in docs:
        text = read(rel)
        if text is None:
            continue
        referenced.update(DOC_TOOLS_PATTERN.findall(text))
    if not referenced:
        add(
            "LAYOUT.DOC_TOOLS",
            False,
            f"扫了 {len(docs)} 份文档，0 处 tools/ 引用 —— 判据是空的（阳性对照失败）",
        )
        return
    SCANNED["doc_tools"] = len(referenced)
    missing: list[str] = []
    deferred: list[str] = []
    stale: list[str] = []
    for rel in sorted(referenced):
        if (ROOT / rel).is_file() or rel in EXEMPT_TOOLS:
            continue
        milestone = PENDING_TOOLS.get(rel)
        if milestone is None:
            missing.append(rel)
        elif milestone in done:
            stale.append(f"{rel}（M{milestone} 已 ✅，登记项必须清理）")
        else:
            deferred.append(f"{rel}(M{milestone})")
    problems = missing + stale
    detail = f"{len(referenced)} 个文档点名的 tools/ 脚本"
    if problems:
        detail += f"；问题: {','.join(problems)}"
    elif deferred:
        detail += f"；{len(deferred)} 个待里程碑落位: {','.join(deferred)}"
    else:
        detail += " 全部在位"
    add("LAYOUT.DOC_TOOLS", not problems, detail)


# ── 主流程 ──────────────────────────────────────────────────────────────────
def _run(fn: Callable[[], Any], check_id: str) -> Any:
    try:
        return fn()
    except Exception:  # noqa: BLE001 - 门永不崩：报一条 FAIL 并继续
        add(check_id, False, "判据执行异常: " + traceback.format_exc(limit=1).strip().replace("\n", " "))
        return None


def main(argv: list[str] | None = None) -> int:
    unknown = [a for a in (argv if argv is not None else sys.argv[1:]) if a not in ("--json",)]
    if unknown:
        sys.stderr.write(f"check-sprint-layout: unknown argument {unknown[0]}\n")
        return 2

    _run(check_required_files, "LAYOUT.FILES")
    _run(check_binding_head, "LAYOUT.BINDING_HEAD")
    _run(check_sections, "LAYOUT.SECTIONS")

    collected = _run(collect_states, "LAYOUT.STATUS") or ({}, {})
    states, rows_by_copy = collected
    done = sorted(k for k, values in states.items() if "done" in values)
    all_milestones = sorted(states)

    _run(lambda: check_documented_tools(done), "LAYOUT.DOC_TOOLS")
    _run(lambda: check_status_agreement(states, rows_by_copy), "LAYOUT.STATUS")
    _run(lambda: check_handoffs(done, all_milestones), "LAYOUT.HANDOFFS")
    _run(lambda: check_stale_gaps(done), "LAYOUT.GAPS")
    _run(lambda: check_ledger(done), "LAYOUT.LEDGER")
    _run(lambda: check_release_doc(done), "LAYOUT.RELEASE")

    failures = [c for c in CHECKS if not c[1]]
    out = [
        "布局门（方法论装订） · 判据只落仓库内文件",
        "=" * 56,
        *[f"{'PASS' if ok else 'FAIL'}  {cid}  {detail}" for cid, ok, detail in CHECKS],
        "=" * 56,
        (
            f"这轮扫到：文档 {SCANNED['docs']} / 交接单 {SCANNED['handoffs']} / "
            f"状态副本 {SCANNED['copies']} / 文档点名工具 {SCANNED['doc_tools']} / "
            f"缺口行 {SCANNED['gap_rows']} / 台账行 {SCANNED['ledger_rows']}"
        ),
        f"结论: {'全绿' if not failures else f'{len(failures)} 项 FAIL'}",
    ]
    sys.stdout.write("\n".join(out) + "\n")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
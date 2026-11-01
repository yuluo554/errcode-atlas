"""两道门本身的测试：门必须能被程序调用、且结论行可读。

变异验证（``tools/verify_gates.py``）覆盖"门会变红"；这里补的是另一半 ——
**门在 pytest 里也能跑**（否则"这条判据只在 CI 跑过"就没人知道它是不是真跑）。
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(script: str, *args: str) -> subprocess.CompletedProcess:
    # **必须继承 os.environ**：只传 PYTHONPATH 会让 3.8 通道子进程拿不到 SYSTEMROOT，
    # 崩在 `_Py_HashRandomization_Init: failed to get random numbers`（本项目实测：
    # 看起来像"门在 3.8 上坏了"，实际是环境被剪掉了）。
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / script), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


# ── 布局门 ────────────────────────────────────────────────────────────────
def test_layout_gate_is_green_on_current_tree() -> None:
    proc = _run("check_sprint_layout.py")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_layout_gate_prints_counts_for_every_surface() -> None:
    """"0 命中"与"扫了 0 个"必须可区分（非空跑自证）。

    **每条计数都单独断言** —— 首版只测了"这一轮扫到："在不在，于是某个计数退化成 0
    时测试照样绿（那不是门在验，是测试在验门的措辞）。
    """
    proc = _run("check_sprint_layout.py")
    line = next((l for l in proc.stdout.split("\n") if l.startswith("这轮扫到：")), "")
    assert line, "布局门没打印「这轮扫到」行 —— 空跑自证缺失"
    for surface in ("文档", "交接单", "状态副本", "文档点名工具", "缺口行", "台账行"):
        assert surface in line, f"非空跑自证缺 {surface}"


def test_layout_gate_reports_zero_scanned_as_failure() -> None:
    """反证：台账表被切成 0 行时必须报 FAIL（否则"全关完"与"没扫到"同形）。"""
    module = _load(REPO_ROOT / "tools" / "check_sprint_layout.py")
    original_read = module.read
    try:
        module.CHECKS.clear()
        module.read = lambda rel: "| 承诺项 | 素材 | 可及 | 核验 | 状态 |\n|---|---|---|---|---|\n"
        module.check_ledger([0])
    finally:
        module.read = original_read
    assert any(cid == "LAYOUT.LEDGER" and not ok for cid, ok, _ in module.CHECKS)


def test_layout_gate_rejects_unknown_argument() -> None:
    assert _run("check_sprint_layout.py", "--nope").returncode == 2


# ── 交接单 = 里程碑入口文件（本项目实测过的真缺陷）──────────────────────────
def test_handoff_required_for_current_milestone_not_only_done_ones() -> None:
    """**当前在做的里程碑**必须有入口文件，不只是"已完成"的那些。

    本项目实测：M1 收尾时没写 `HANDOFF-M2.md`，而首版 `check_handoffs` 只遍历 ``done``，
    于是门报"2 份交接单齐 全绿" —— 它看起来在管交接单，实际**只管完成过的**，
    漏掉的正是最该管的那个（下一棒打开仓库找不到入口）。

    这条测试直接对 `check_handoffs` 断言：把当前里程碑的入口"藏起来"（只读时返回 None），
    门必须变红并且在结论里点出"当前在做的里程碑"。
    """
    module = _load(REPO_ROOT / "tools" / "check_sprint_layout.py")
    states = _milestone_states()
    done = sorted(k for k, ok in states.items() if ok)
    pending = sorted(k for k, ok in states.items() if not ok)
    assert pending, "全部里程碑已 ✅，本测试的前提（存在当前里程碑）不成立"

    current = pending[0]
    hide = f"plan/HANDOFF-M{current}.md"
    original_read = module.read
    try:
        module.CHECKS.clear()
        module.SCANNED["handoffs"] = 0
        module.read = lambda rel: None if rel == hide else original_read(rel)
        module.check_handoffs(done, sorted(states))
    finally:
        module.read = original_read
        module.SCANNED["handoffs"] = 0
    verdicts = [item for item in module.CHECKS if item[0] == "LAYOUT.HANDOFFS"]
    assert verdicts, "check_handoffs 没产出结论"
    ok, detail = verdicts[-1][1], verdicts[-1][2]
    assert not ok, f"当前里程碑入口 {hide} 被藏起来了，门却仍绿：{detail}"
    assert "当前在做的里程碑" in detail, f"红了但没说清是哪一类缺失：{detail}"


def test_handoff_lookahead_is_rejected() -> None:
    """给**还没到的**里程碑预写入口也必须变红 —— 那是给没跑的棒编记录。

    首版门完全不管这一半：`HANDOFF-M6.md` 现在写出来，门照样全绿。

    **靶子用合成状态造，不依赖仓库里还剩几个未完成里程碑**（M5 收尾时只剩 M6 一个，
    那时"至少要有两个 pending"这个前提直接不成立，测试自己红 —— 那不是门坏了，
    是测试把仓库的里程碑进度绑进了判据）。合成本身不造假：被测的是门的
    **超前分支**，不是仓库状态。
    """
    module = _load(REPO_ROOT / "tools" / "check_sprint_layout.py")
    states = _milestone_states()
    done = sorted(k for k, ok in states.items() if ok)
    pending = sorted(k for k, ok in states.items() if not ok)
    assert done, "全部里程碑都未完成，本测试的前提（存在已完成里程碑）不成立"

    # 当前里程碑 = 最小的未完成号（没有未完成时，用 done 的最大号 + 1 造一个）
    current = pending[0] if pending else max(done) + 1
    # 超前靶子 = 比当前更大、且状态仍是 ⬜ 的号（合成，保证一定存在）
    far_number = max(list(states) + [current]) + 1
    synthetic_states = dict(states)
    synthetic_states[far_number] = False
    synthetic_done = sorted(k for k, ok in synthetic_states.items() if ok)
    far = f"plan/HANDOFF-M{far_number}.md"

    original_read = module.read
    original_is_file = Path.is_file
    try:
        module.CHECKS.clear()
        module.read = lambda rel: None if rel == far else original_read(rel)
        # 让门"看见"超前文件存在（但不真的写进仓库）
        Path.is_file = lambda self: True if self.as_posix().endswith(far) else original_is_file(self)
        module.check_handoffs(synthetic_done, sorted(synthetic_states))
    finally:
        module.read = original_read
        Path.is_file = original_is_file
    verdicts = [item for item in module.CHECKS if item[0] == "LAYOUT.HANDOFFS"]
    assert verdicts, "check_handoffs 没产出结论"
    ok, detail = verdicts[-1][1], verdicts[-1][2]
    assert not ok, f"超前入口 {far} 存在，门却仍绿：{detail}"
    assert "超前入口" in detail, f"红了但没说清是超前入口：{detail}"


def _milestone_states() -> dict[int, bool]:
    """从 ``plan/00`` 里程碑表读 ``{编号: 是否 ✅}`` —— 靶子从事实取，不写死编号。"""
    import re

    text = (REPO_ROOT / "plan" / "00-README总览.md").read_text(encoding="utf-8")
    states: dict[int, bool] = {}
    for line in text.split("\n"):
        match = re.match(r"^\|\s*M(\d+)\s*\|", line)
        if not match:
            continue
        cells = line.split("|")
        states[int(match.group(1))] = "✅" in cells[-2]
    return states


def _load(path: Path):
    """动态加载工具模块。

    ``spec_from_file_location`` 加载的模块**不会自动登记进 ``sys.modules``** ——
    而 ``@dataclass`` 在解析注解时会 `sys.modules.get(cls.__module__).__dict__`，
    于是直接 exec 会抛 ``AttributeError: 'NoneType' object has no attribute '__dict__'``。
    正解 = 先登记再 exec（本项目实测：不登记时四个测试一起红，红在 dataclasses 内部，
    看起来像"工具模块坏了"）。
    """
    name = f"_gate_under_test_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
        # dataclass 已解析完注解，后续调用不再需要它在 sys.modules 里
    return module


# ── 脱敏门 ────────────────────────────────────────────────────────────────
def test_desens_gate_is_green_on_current_tree() -> None:
    proc = _run("check_desensitized.py")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_desens_gate_prints_scanned_count() -> None:
    """0 命中与扫了 0 个必须可区分。"""
    proc = _run("check_desensitized.py")
    assert "扫了" in proc.stdout
    digits = [t for t in proc.stdout.split() if t.isdigit()]
    assert digits and int(digits[0]) > 0, proc.stdout


def test_desens_gate_has_the_four_rule_ids() -> None:
    module = _load(REPO_ROOT / "tools" / "check_desensitized.py")
    ids = [rule.id for rule in module.RULES]
    assert ids == [
        "absolute-session-path",
        "msys-user-path",
        "host-username",
        "loopback-proxy",
    ], ids


def test_desens_placeholder_allowance_uses_lookahead_not_whole_line() -> None:
    """放行判据必须看"命中之后紧跟占位符"，不是"整行含 ``<``"。

    后者的漏洞：同一行既写真路径又写占位符时，整行被放行 → 真泄露漏报。

    样本用**运行时拼接**，本文件自身因此不含被禁字面量 —— 脱敏门不需要为测试文件开豁免
    （本项目实测：直接写字面量 → 门当场报这一行，那不是假红，是门在正确地扫自己）。
    """
    module = _load(REPO_ROOT / "tools" / "check_desensitized.py")
    rule = next(r for r in module.RULES if r.id == "absolute-session-path")
    drive, sep = "C", ":"

    real_leak = f"见 {drive}{sep}\\Users\\someone\\secret.txt 与 {drive}{sep}\\Users\\<user>\\x"
    match = rule.pattern.search(real_leak)
    assert match is not None
    assert rule.allow(real_leak, match) is False, "同行有占位符就把真路径放行了 —— 漏报"

    placeholder_only = f"{drive}{sep}\\Users\\<user>\\x"
    match2 = rule.pattern.search(placeholder_only)
    assert match2 is not None
    assert rule.allow(placeholder_only, match2) is True


def test_desens_gate_self_exempt_set_is_narrow() -> None:
    """自豁免面越窄越好；且必须是"文件集合"形态。"""
    module = _load(REPO_ROOT / "tools" / "check_desensitized.py")
    assert isinstance(module.SELF_EXEMPT, frozenset)
    assert "tools/check_desensitized.py" in module.SELF_EXEMPT
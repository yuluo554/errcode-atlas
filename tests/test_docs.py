"""交付面文档的判据：技术报告与 SKILL.md 存在、样例真跑对得上、不复述数值口径。

三条判据，各自挡一类具体缺陷：

1. **样例必须真跑对得上**（`plan/05` §2 M5 DoD / K27 的同类）：报告里 `console` 块的
   ``$ py -3.12 -m errcode_atlas …`` 行下面贴的输出，必须与**现在真跑**的 stdout **逐字节相同**。
   手写样例会在某个时刻变成谎言，而且没有任何判据会抓到它 —— 这条就是那个判据。
2. **不复述数值口径**（`data/README.md` §5 是唯一定义处）：报告与 `SKILL.md` 里不得出现
   "把编目数值抄成一张表"或"把判定判据重写一遍"的形态。抄第二份副本的东西迟早会和第一份对不上，
   而 `bench` 与契约测试都只对账第一份。
3. **裸 clone 能读到的文件都真的入库**：报告与 GIF 必须在 `git ls-files` 里，
   否则解包树里读者看不到它们（"交付物存在但没入仓"是发布前最尴尬的一类）。

判据**不读 git 元数据以外的东西**；第 3 条用 ``git ls-files`` 是刻意的 ——
它问的正是"这个文件在不在仓库里"，而不是"它在不在我的磁盘上"。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT = REPO_ROOT / "docs" / "技术报告.md"
SKILL = REPO_ROOT / "SKILL.md"
DEMO = REPO_ROOT / "docs" / "demo" / "demo.gif"

#: 报告里被"真跑对账"的入口形态。只认这一种：报告是给本仓读者看的，
#: 装好后的裸命令 ``errcode-atlas`` 在未安装的检出树里跑不出来（会变成假红）。
INVOCATION = "py -3.12 -m errcode_atlas"


def _console_blocks(text: str) -> list[str]:
    return re.findall(r"```console\n(.*?)```", text, re.DOTALL)


def _report_samples() -> list[tuple[str, str]]:
    """从报告里抽出 ``(命令, 期望输出)``。

    只收**连续命令块**：``$ <invocation> …`` 之后到下一个 ``$`` 或块尾的所有行都是期望输出。
    块内混有别的命令（如 ``node -e``）时，非本入口的行原样跳过 —— 它们不由本判据负责。
    """
    samples: list[tuple[str, str]] = []
    for block in _console_blocks(REPORT.read_text(encoding="utf-8")):
        lines = block.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            if not line.startswith("$ "):
                i += 1
                continue
            command = line[2:].strip()
            i += 1
            body: list[str] = []
            while i < len(lines) and not lines[i].startswith("$ "):
                body.append(lines[i])
                i += 1
            if command.startswith(INVOCATION):
                # 块尾的空行是 markdown 排版，不是输出的一部分
                while body and body[-1] == "":
                    body.pop()
                samples.append((command, "\n".join(body) + "\n"))
    return samples


def test_report_and_skill_exist() -> None:
    assert REPORT.is_file(), "docs/技术报告.md 不存在"
    assert SKILL.is_file(), "SKILL.md 不存在"
    assert REPORT.stat().st_size > 0 and SKILL.stat().st_size > 0


def test_report_samples_are_extracted() -> None:
    """非空跑自证：一条样例都没抽到 = 判据是空的（报告的写法变了？）。"""
    samples = _report_samples()
    assert samples, "技术报告里没抽到任何 errcode_atlas 命令样例 —— 抽取口径对不上了"


@pytest.mark.parametrize("command,expected", _report_samples(), ids=[c for c, _ in _report_samples()])
def test_report_sample_matches_real_run(command: str, expected: str) -> None:
    """报告里的每条样例都必须与现在真跑的输出**逐字节相同**。

    期望输出与实测差一个字符就红 —— 包括末尾换行。手写样例、粘贴时手抖、
    或者"改了实现忘了改报告"，都会在这里红。
    """
    argv = command[len(INVOCATION) :].split()
    proc = subprocess.run(
        [sys.executable, "-m", "errcode_atlas", *argv],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={
            **__import__("os").environ,
            "PYTHONPATH": str(REPO_ROOT / "src"),
            "PYTHONUTF8": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    assert proc.stdout == expected, (
        f"报告里的样例与真跑不一致：`{command}`\n"
        f"--- 报告里写的 ---\n{expected}\n--- 真跑实得 ---\n{proc.stdout}"
    )


def test_report_does_not_restate_verdict_thresholds() -> None:
    """报告不得把 §5.2 的判定判据重写一遍（只许引用编号）。

    判据是**形态**而不是关键词：报告里出现 ``| 判定态 | 判据 |`` 这种"再定义一遍"的表格头，
    或者出现 ``UNAMBIGUOUS`` 与 ``|`` 同处一行的表格行 —— 都是第二份副本的开头。
    报告可以说"五个态各自的判据见 `data/README.md` §5.2"，但不能把那张表搬过来。
    """
    text = REPORT.read_text(encoding="utf-8")
    offenders: list[str] = []
    for line in text.split("\n"):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 4:
            continue
        # 表头形态：第一列是"判定态"，第二列是"判据"
        if cells[1] in ("判定态", "归因", "退出码") and "判据" in cells[2]:
            offenders.append(line.strip()[:80])
        # 数据行形态：第一列是判定态字面量，且还有第三列内容（= 在解释它）
        if re.fullmatch(r"`?[A-Z][A-Z0-9-]*`?", cells[1]) and cells[2].strip():
            offenders.append(line.strip()[:80])
    assert not offenders, (
        "技术报告里复述了判定态判据表（数值口径唯一定义处是 data/README.md §5）: "
        f"{offenders}"
    )


def test_report_does_not_copy_catalog_numbers() -> None:
    """报告不得抄编目数值（``E* = 数字`` 形态）—— 那是 catalog 的活儿。"""
    text = REPORT.read_text(encoding="utf-8")
    offenders = re.findall(r"`(E[A-Z0-9_]{2,})`\s*=\s*\d+", text)
    assert not offenders, f"技术报告里抄了编目数值：{offenders}"


def test_deliverables_are_tracked_in_git() -> None:
    """交付物必须在 ``git ls-files`` 里 —— "文件在磁盘上"不等于"随包发得出去"。

    用 ``git ls-files`` 而不是 ``Path.is_file()``：后者在解包树里永远为真，
    问不出"这个文件到底入没入仓"。无 git 的环境（导出树）跳过并说明原因。

    **必须 ``-z``**（M5 实测）：``git ls-files`` 默认会把中文路径按 C 转义成
    ``"docs/\\346\\212\\..."`` 形态，于是 ``endswith("docs/技术报告.md")`` 永远不成立 ——
    那不是"没入仓"，是判据在跟转义后的名字比对。``-z`` 输出原始字节、不转义。

    **必须确认 cwd 就是仓库根**（M5 实测）：导出树常常被解到另一个仓库的临时目录里，
    那时 ``git ls-files`` 会**向上找到父仓库**并返回它的索引 —— 判据于是拿"父仓库的
    文件表"去断言"导出树入没入仓"，两边都不是它想问的东西。判据用
    ``git rev-parse --show-prefix``：非空 = cwd 不是仓库根 → 跳过（导出树场景）。
    """
    try:
        prefix = subprocess.run(
            ["git", "rev-parse", "--show-prefix"],
            cwd=REPO_ROOT,
            capture_output=True,
            encoding="utf-8",
        )
        if prefix.returncode != 0:  # pragma: no cover - 无 .git 的导出树
            pytest.skip("cwd 不在 git 仓库里（导出树）—— 入仓判据不适用")
        if prefix.stdout.strip():  # pragma: no cover - 导出树解在父仓库的临时目录里
            pytest.skip(
                f"cwd 是父仓库的子目录（prefix={prefix.stdout.strip()}），"
                "不是仓库根 —— git ls-files 会向上找父仓库，判据不适用"
            )
        tracked = subprocess.run(
            ["git", "ls-files", "-z", "docs/", "SKILL.md"],
            cwd=REPO_ROOT,
            capture_output=True,
            encoding="utf-8",
        )
    except FileNotFoundError:  # pragma: no cover - 无 git 的导出树
        pytest.skip("本机没有 git 命令（导出树）—— 入仓判据不适用")
    if tracked.returncode != 0:  # pragma: no cover
        pytest.skip(f"git ls-files 不可用（{tracked.stderr.strip()[:80]}）")
    names = {n for n in tracked.stdout.split("\0") if n}
    assert "SKILL.md" in names, f"SKILL.md 没有入仓（随包发不出去）：{sorted(names)}"
    assert "docs/技术报告.md" in names, (
        f"技术报告没有入仓（随包发不出去）：{sorted(names)}"
    )
    assert "docs/demo/demo.gif" in names, f"demo GIF 没有入仓：{sorted(names)}"


# ── demo GIF（K31：必须是真跑录制）───────────────────────────────────────────
def test_demo_gif_exists_and_is_a_gif() -> None:
    """存在 + 真的是 GIF（不是被改名成 .gif 的 PNG）。"""
    assert DEMO.is_file(), "docs/demo/demo.gif 不存在"
    head = DEMO.read_bytes()[:6]
    assert head in (b"GIF87a", b"GIF89a"), f"demo.gif 的文件头不是 GIF：{head!r}"


def test_demo_gif_is_multi_frame_animation() -> None:
    """必须是**多帧动画**：单帧的 GIF 证明不了"录过"，只能证明"截过一张图"。

    判据用 GIF 的帧分隔符（0x2C）计数 + 尺寸一致性。没有 Pillow 的依赖关系：
    本仓运行期零第三方依赖，测试侧也不为这条引入 Pillow —— 数分隔符就够了。
    """
    data = DEMO.read_bytes()
    frames = data.count(b"\x2c")
    assert frames >= 10, f"demo.gif 只有 {frames} 个帧标记 —— 这不像是真录制的动画"
    assert len(data) > 200_000, f"demo.gif 只有 {len(data)} bytes —— 太小，不像完整录制"


def test_demo_gif_does_not_leak_local_paths() -> None:
    """GIF 里不许留下本机绝对路径痕迹。

    **这条判据脱敏门抓不到**：``*.gif`` 在门的 ``SKIP_EXTS`` 里（二进制不扫文本）。
    所以录制脚本的提示符必须脱敏（``prompt errcode-atlas$G``）—— 本项目实测踩到过：
    默认提示符把本机工作目录路径录进了最后一帧。

    判据是"GIF 里能不能读出盘符路径的 ASCII 字节"——GIF 是压缩的，所以这条**不能**
    保证 100% 覆盖；它挡的是"录制时提示符没改"这个高频形态。真正可靠的是录制脚本里的
    那一行 ``prompt``，这里补的是"改完之后还漏了没有"。

    **特征串必须够长**（M5 实测）：两字节的 ``<盘符>:`` 在 GIF 的 LZW 压缩字节里
    **会偶然出现** —— 那会把"录进了路径"判成"录进了路径"的反面（假红）。
    GIF 里文字是调色板索引、不是 ASCII，所以判据只能靠"足够长的特征串偶然概率极低"，
    不能靠"任意短串不出现"。

    本文件的字面量用运行时拼接，因此不含被禁形态 —— 脱敏门不需要为测试文件开豁免。
    """
    raw = DEMO.read_bytes()
    # 足够长的本机特征：本机会话目录名 + 本机项目名（各自 10 字节以上，偶然出现概率可忽略）
    for marker in ("ProgramData".encode(), b"\\zcode\\", b"-errcode-atlas-tmp"):
        assert marker not in raw, f"demo.gif 里出现了本机路径特征 {marker!r}"


def test_demo_recording_script_sanitizes_the_prompt() -> None:
    """录制脚本（``tmp/demo/demo_run.cmd``）必须设脱敏提示符。

    这条守的是"上一轮修好了、下一轮重录又忘了"。脚本不在仓库里（``tmp/`` 被封），
    所以它在解包树里不存在 —— 那时跳过，但**在开发树里必须存在且带 prompt**。
    """
    script = REPO_ROOT / "tmp" / "demo" / "demo_run.cmd"
    if not script.is_file():
        pytest.skip("录制脚本不在（导出树 / 已清理）—— 只在开发树里检查")
    text = script.read_text(encoding="utf-8")
    assert "prompt errcode-atlas$G" in text, (
        "demo_run.cmd 没设脱敏提示符 —— 默认提示符会把本机绝对路径录进 GIF，"
        "而 *.gif 在脱敏门的 SKIP_EXTS 里，门抓不到"
    )

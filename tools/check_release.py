#!/usr/bin/env python3
"""发布门（M6 三档）：把「发布这件事真的发生了」变成可跑红的断言。

三档是**递进**的，不是三种口径：

* ``--pre-tag``：留档在 tag **之前**就已落盘且形状正确（两栏 / 覆盖对账 / 三态行齐）、
  名字占用已重核、版本号两处一致、tag 树（尚无 tag 时看工作树）里**没有自指值**。
* ``--offline``：上面全部 + **本地**对账（附件 zip / ``SHA256SUMS`` / 回下载件与本地副本
  ``cmp`` / 附件内容与 tag 树**逐字节同源**）。全程不联网。
* ``--online``：上面全部 + 远端 Release（存在 / ≥1 个**手工上传**附件 / 留档里记的 CI run id
  真跑过且绿）。

四条纪律（与另两道门同一套，别在这里另立一套）：

1. **非空跑自证**：结论行打印「本轮实检 N 项 / 不适用 M 项」，否则"全绿"与"什么都没查"
   输出同形。
2. **不适用必须写明原因，且只在真正不适用时报**：``--offline`` 在 tag 尚未创建时跳过附件对账
   —— 那时仓库里**不可能**有附件；tag 一旦存在，缺附件就是 FAIL，不是跳过。
   （判别 = "这条跳过，是因为事实还不存在，还是因为我不想让它红？"）
3. **永不崩**：任一项异常报一条 FAIL 并继续，不是 traceback 逃逸。
4. **只读**：本门不改任何文件；变异验证（``tools/verify_gates.py``）负责证明它会变红。

命令一律走 ``subprocess.run([...])`` 的字面量参数列表（``shell=False``），不拼字符串。

退出码：``0`` 无 FAIL / ``1`` 有 FAIL / ``2`` 用法错误。
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import traceback
import zipfile
from argparse import ArgumentParser
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]

DOC_REL = "plan/RELEASE-M6.md"
PACKAGE_NAME = "errcode-atlas"
LOCAL_DIR = ROOT / "dist-release"
DOWNLOAD_DIR = LOCAL_DIR / "downloaded"
SHA_NAME = "SHA256SUMS"

#: 两栏结构（K33）：``## 一、tag 前事实`` / ``## 二、tag 后追加``。与布局门 ``LAYOUT.RELEASE``
#: 用**同一组正则**（布局门判"形状在"，本门判"内容对"）；两处漂移就是两份口径。
COLUMN_HEADINGS = (
    re.compile(r"^##\s*一、tag\s*前事实", re.MULTILINE),
    re.compile(r"^##\s*二、tag\s*后追加", re.MULTILINE),
)
COVERAGE = re.compile(r"^#{2,3}.*覆盖对账", re.MULTILINE)

#: 三态词汇（``plan/00`` §4 M6 DoD）。判据 = 三件事：
#:
#: * **条数 ≥3**（``plan/05`` §2 的"≥3 条三态行"）；
#: * 每行只挂**一个**标签（一行挂两个 = 想说"既实现又待推"，那是没表态）；
#: * **至少一条 `实现`** —— 全部写"不适用/待首推"而门仍绿，就是拿三态表当免票。
#:
#: **不要求三种都出现**：本仓 M6 收尾时"待首推"会自然归零，硬要求它留一条
#: 等于逼着留一行谎话。分布进结论行（"三态里各几条"可数），不硬凑。
STATES = ("实现", "不适用", "待首推")
STATE_ROW = {state: re.compile(rf"^\|.*{state}.*\|$", re.MULTILINE) for state in STATES}

#: 自指值 = 只有**跑完**才知道的事实。它们属 §二，且只能在 tag **之后**的新提交里；
#: tag 树里出现任何一条，就是"用未来的事实写了过去"（K33）。
SELF_REF = (
    re.compile(r"\b[0-9a-fA-F]{64}\b"),
    re.compile(r"run[ _-]?id\s*[:：=]?\s*\d{6,}", re.IGNORECASE),
)

#: 名字占用重核的判据：§一 必须同时有 PyPI 与 GitHub 的结论、且带复核日期。
NAME_NEEDLES = ("PyPI", "404", "GitHub")

#: 三个状态码：与另两道门同一套语义（0 绿 / 1 红 / 2 用法）。
RC_OK, RC_BAD, RC_USAGE = 0, 1, 2

CHECKS: list[tuple[str, bool, str]] = []
COUNTED = {"checked": 0, "skipped": 0}


# ── 基础 ────────────────────────────────────────────────────────────────────
def add(check_id: str, ok: bool, detail: str, *, skipped: bool = False) -> None:
    """记一条结论。``skipped=True`` 的条目算"不适用"，不参与 FAIL 判定，但**进计数**。"""
    CHECKS.append((check_id, ok, detail))
    COUNTED["skipped" if skipped else "checked"] += 1


def read(rel: str) -> str | None:
    path = ROOT / rel
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def run_cmd(cmd: list[str], *, text: bool = True) -> subprocess.CompletedProcess:
    """执行一条**字面量**参数列表（``shell=False``）。

    每个调用点都写完整的 ``[...]`` —— 不把外部输入拼进命令串，也不走 shell 解释。
    参数里的动态部分只有 tag / 版本号 / run id，全部经 ``re`` 校验后才到得了这里
    （见 ``check_ci`` / ``tag_exists``）。
    """
    return subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
    )


def git_text(args: list[str]) -> subprocess.CompletedProcess:
    """git 的文本通道。``core.quotepath=false`` 让中文路径原样输出（本仓文件名贯穿判据链）。"""
    return run_cmd(["git", "-c", "core.quotepath=false", *args])


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def version_from_source() -> str | None:
    """版本**唯一定义处**（``plan/02`` §4.2）：``__init__.py`` 与 ``pyproject.toml`` 两处。

    本门不 import 包（否则要先有 ``PYTHONPATH=src``，门就不独立了）—— 只读两处字面量并对账。
    """
    text = read("src/errcode_atlas/__init__.py") or ""
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else None


def version_from_pyproject() -> str | None:
    text = read("pyproject.toml") or ""
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else None


def tag_name(version: str) -> str:
    return f"v{version}"


def attachment_name(version: str) -> str:
    return f"{PACKAGE_NAME}-{version}.zip"


def tag_exists(tag: str) -> bool:
    if not re.fullmatch(r"v[0-9][0-9A-Za-z.\-]*", tag):
        return False  # 版本号读歪了就到此为止，不把它带进命令行
    proc = git_text(["rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"])
    return proc.returncode == 0


def tag_commit(tag: str) -> str:
    if not tag_exists(tag):
        return ""
    proc = git_text(["rev-list", "-n", "1", tag])
    return proc.stdout.strip() if proc.returncode == 0 else ""


def remote_slug() -> str | None:
    """``owner/repo`` —— 从 ``origin`` 取；本机没配远端时返回 None（``--online`` 会因此 FAIL）。"""
    proc = git_text(["remote", "get-url", "origin"])
    if proc.returncode != 0:
        return None
    url = proc.stdout.strip().rstrip("/")
    match = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?$", url)
    return f"{match.group(1)}/{match.group(2)}" if match else None


# ── 一、留档结构（三档都跑）──────────────────────────────────────────────────
def _state_rows(text: str) -> tuple[int, int, dict[str, int]]:
    """返回 ``(三态行数, 一行挂多标签的行数, 各态行数)``。

    "一行挂多标签"单独数：那是**没表态**的表格（写"既实现又待推"等于什么都没说），
    比"某个态 0 行"更该红 —— 后者在真实进度下是合法的（最后一棒的"待首推"会归零）。
    """
    multi = 0
    counts: dict[str, int] = {state: 0 for state in STATES}
    total = 0
    for line in text.split("\n"):
        if not line.startswith("|"):
            continue
        hits = [state for state, pattern in STATE_ROW.items() if pattern.match(line)]
        if not hits:
            continue
        total += 1
        for state in hits:
            counts[state] += 1
        if len(hits) > 1:
            multi += 1
    return total, multi, counts


def check_doc() -> None:
    text = read(DOC_REL)
    if text is None:
        add("RELEASE.DOC", False, f"缺 {DOC_REL}（K33：tag 之前必须落盘）")
        return
    missing_cols = [
        name
        for name, pattern in zip(("一、tag 前事实", "二、tag 后追加"), COLUMN_HEADINGS)
        if not pattern.search(text)
    ]
    has_coverage = bool(COVERAGE.search(text))
    total, multi, counts = _state_rows(text)
    problems: list[str] = []
    if missing_cols:
        problems.append(f"两栏缺 {missing_cols}")
    if not has_coverage:
        problems.append("覆盖对账小节缺失")
    if total < 3:
        problems.append(f"三态行只有 {total} 条（要求 ≥3）")
    if counts["实现"] == 0:
        problems.append("没有任何一条『实现』（三态表不表态 = 免票）")
    if multi:
        problems.append(f"{multi} 行同时挂多个标签（一行只能表一个态）")
    add(
        "RELEASE.DOC",
        not problems,
        "；".join(problems) if problems
        else f"两栏齐 / 覆盖对账在 / 三态 {total} 行（{counts}）",
    )


def check_name_occupancy() -> None:
    """名字占用必须**在建仓之前重核**，且重核结果落在 §一（``plan/06`` §4.1 是旧快照）。

    判据不看"结论是 0 还是 1"，只判"§一 里有没有这次重核的**可指认记录**" ——
    名字真被占了是另一件事（那时该改的是名字，不是让門变色）。
    """
    text = read(DOC_REL) or ""
    first = text.split("## 二、")[0] if "## 二、" in text else text
    has_date = bool(re.search(r"20\d{2}-\d{2}-\d{2}", first))
    missing = [needle for needle in NAME_NEEDLES if needle not in first]
    problems = list(missing)
    if not has_date:
        problems.append("复核日期")
    add(
        "RELEASE.NAME",
        not problems,
        f"§一 缺: {'/'.join(problems)}" if problems
        else "§一 有带日期的名字占用重核记录（GitHub + PyPI）",
    )


def check_version() -> None:
    from_src, from_pyproject = version_from_source(), version_from_pyproject()
    ok = bool(from_src) and from_src == from_pyproject
    add(
        "RELEASE.VERSION",
        ok,
        f"__init__={from_src!r} pyproject={from_pyproject!r}"
        + ("" if ok else "（两处必须相等，tag 名由它推出）"),
    )


def _doc_in_tag_tree(tag: str) -> tuple[str | None, str]:
    """tag 树里的留档正文。tag 尚未创建时退回工作树 —— 那时"树"就是工作树。"""
    if not tag_exists(tag):
        return read(DOC_REL), "工作树（tag 尚未创建）"
    proc = run_cmd(["git", "cat-file", "blob", f"{tag}:{DOC_REL}"], text=False)
    if proc.returncode != 0:
        return None, f"tag {tag}"
    return proc.stdout.decode("utf-8", "replace"), f"tag {tag}"


def _find_self_ref(text: str) -> list[str]:
    hits: list[str] = []
    for pattern in SELF_REF:
        for match in pattern.finditer(text):
            line = text[: match.start()].count("\n") + 1
            hits.append(f"line {line}: {match.group(0)[:40]}")
    return hits


def check_self_reference(tag: str) -> None:
    """self-ref 值（附件 sha256 / run id）不许出现在 **§一**，也不许预置进 tag 树。

    两个面、两条理由：

    * **§一（tag 前事实）**：这一节在 tag 时就冻结了。往里面写 sha256 / run id，
      要么是"用未来的事实写了过去"（K33），要么就是 tag 之后**回填**（HANDOFF-M6 §二 第 3 条禁止）。
      所以 §一 里出现自指值在任何阶段都红 —— 这也让本判据**不随 tag 状态漂移**
      （变异验证要一组恒可触发的靶子）。
    * **tag 树整份留档**：tag 时 §二 必须还是骨架；提前把 sha256 填进去同样是自指。
      只在 tag 已存在时判 —— tag 还没打时"树"就是工作树，那是下一丸的事。
    """
    doc = read(DOC_REL)
    if doc is None:
        add("RELEASE.TREE", False, f"缺 {DOC_REL} —— 无留档可判")
        return
    head = doc.split("## 二、", 1)[0]
    problems: list[str] = []
    head_hits = _find_self_ref(head)
    if head_hits:
        problems.append("§一（tag 前事实）出现自指值: " + "；".join(head_hits[:5]))
    where = "工作树（tag 尚未创建，只判 §一）"
    if tag_exists(tag):
        text, where = _doc_in_tag_tree(tag)
        if text is None:
            add("RELEASE.TREE", False, f"{where} 里没有 {DOC_REL} —— 留档没进树")
            return
        tree_hits = _find_self_ref(text)
        if tree_hits:
            problems.append(f"tag 树整份留档出现自指值: " + "；".join(tree_hits[:5]))
    add(
        "RELEASE.TREE",
        not problems,
        "；".join(problems) if problems
        else f"{where} 自指值 0 处（§一 与 tag 树均无附件 sha256 / run id）",
    )


# ── 二、tag 事实 ─────────────────────────────────────────────────────────────
def check_tag(tag: str, strict: bool) -> None:
    if not tag_exists(tag):
        add(
            "RELEASE.TAG",
            not strict,
            f"tag {tag} 尚未创建 —— 本档按 pre-tag 阶段放过（附件对账同批不适用）"
            if not strict
            else f"tag {tag} 不存在（本档要求 tag 已打）",
            skipped=not strict,
        )
        return
    proc = git_text(["cat-file", "-t", f"refs/tags/{tag}"])
    kind = proc.stdout.strip()
    annotated = proc.returncode == 0 and kind == "tag"
    add(
        "RELEASE.TAG",
        annotated,
        f"tag {tag} 类型={kind!r}"
        + ("" if annotated else "（必须是 annotated，轻量 tag 记不了发布事实）"),
    )


# ── 三、本地附件（--offline 起）──────────────────────────────────────────────
def check_local_assets(tag: str, version: str) -> None:
    """本地副本在位：``dist-release/<附件>.zip`` + ``SHA256SUMS``。"""
    asset = LOCAL_DIR / attachment_name(version)
    sums = LOCAL_DIR / SHA_NAME
    if not tag_exists(tag):
        add("RELEASE.ASSETS", True, "不适用：tag 尚未创建，仓库里不可能有附件", skipped=True)
        return
    missing = [p.relative_to(ROOT).as_posix() for p in (asset, sums) if not p.is_file()]
    if missing:
        add("RELEASE.ASSETS", False, f"tag {tag} 已创建，但本地缺: {','.join(missing)}")
        return
    add(
        "RELEASE.ASSETS",
        True,
        f"本地副本在位: {asset.name}（{asset.stat().st_size} 字节）+ {sums.name}",
    )


def check_digest(version: str) -> None:
    """``SHA256SUMS`` 必须真的描述本地附件（不是"有这么一个文件"就算数）。"""
    asset = LOCAL_DIR / attachment_name(version)
    sums = LOCAL_DIR / SHA_NAME
    if not (asset.is_file() and sums.is_file()):
        add("RELEASE.DIGEST", True, "不适用：本地附件或 SHA256SUMS 不在位", skipped=True)
        return
    wanted: dict[str, str] = {}
    for raw in sums.read_text(encoding="utf-8").split("\n"):
        line = raw.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            wanted[parts[1].strip().lstrip("*")] = parts[0].strip().lower()
    actual = sha256_file(asset)
    recorded = wanted.get(asset.name)
    ok = recorded == actual
    add(
        "RELEASE.DIGEST",
        ok,
        f"{asset.name}: 记录 {recorded} vs 实算 {actual}"
        if not ok
        else f"{asset.name} sha256 与 {SHA_NAME} 一致（{actual[:16]}…）",
    )


def _tag_tree_files(tag: str) -> set[str] | None:
    proc = git_text(["ls-tree", "-r", "--name-only", tag])
    if proc.returncode != 0:
        return None
    return {line for line in proc.stdout.split("\n") if line}


def compare_zip_to_tag(tag: str, asset: Path) -> list[str]:
    """附件内容与 tag 树**逐字节同源**（K35）。返回差异描述，空 = 一致。

    判据是**文件集合相等 + 每个文件字节相等**，不是"能打开就行"：

    * 集合相等挡住"少打了一个文件"与"多打了未跟踪文件"（后者会让附件带上本地残留）；
    * 逐字节相等用 ``git cat-file blob <tag>:<path>`` 比，比的是**树的真实内容**，
      而不是"我重新导出一次再和自己比"（那等于没比）。
    """
    tree = _tag_tree_files(tag)
    if tree is None:
        return [f"git ls-tree {tag} 失败"]
    problems: list[str] = []
    try:
        with zipfile.ZipFile(asset) as archive:
            names = {info.filename for info in archive.infolist() if not info.is_dir()}
            missing = sorted(tree - names)
            extra = sorted(names - tree)
            if missing:
                problems.append(f"附件缺 {len(missing)} 个 tag 树里的文件: {missing[:5]}")
            if extra:
                problems.append(f"附件多 {len(extra)} 个不在 tag 树里的文件: {extra[:5]}")
            differing = 0
            for name in sorted(tree & names):
                proc = run_cmd(["git", "cat-file", "blob", f"{tag}:{name}"], text=False)
                if proc.returncode != 0:
                    problems.append(f"{name}: tag 树里读不出来")
                    continue
                if archive.read(name) != proc.stdout:
                    differing += 1
                    if differing <= 3:
                        problems.append(f"{name}: 字节与 tag 树不同")
            if differing > 3:
                problems.append(f"另有 {differing - 3} 个文件字节不同")
    except zipfile.BadZipFile as exc:
        problems.append(f"{asset.name} 不是合法 zip: {exc}")
    return problems[:10]


def check_source(tag: str, version: str) -> None:
    asset = LOCAL_DIR / attachment_name(version)
    if not tag_exists(tag) or not asset.is_file():
        add("RELEASE.SOURCE", True, "不适用：tag 或本地附件不在位", skipped=True)
        return
    problems = compare_zip_to_tag(tag, asset)
    add(
        "RELEASE.SOURCE",
        not problems,
        "；".join(problems) if problems
        else f"附件 {asset.name} 与 tag {tag} 的文件集合相等、逐字节同源",
    )


def check_download(tag: str, version: str) -> None:
    """回下载件与本地副本 ``cmp``（K35）—— 发布面上"上传后拿回来还是不是那一个"。"""
    asset = LOCAL_DIR / attachment_name(version)
    downloaded = DOWNLOAD_DIR / attachment_name(version)
    if not tag_exists(tag) or not asset.is_file():
        add("RELEASE.DOWNLOAD", True, "不适用：tag 或本地附件不在位", skipped=True)
        return
    if not downloaded.is_file():
        add(
            "RELEASE.DOWNLOAD",
            False,
            f"缺回下载件 {downloaded.relative_to(ROOT).as_posix()} —— "
            f"跑 `gh release download {tag} --dir {DOWNLOAD_DIR.relative_to(ROOT).as_posix()}`",
        )
        return
    same = downloaded.read_bytes() == asset.read_bytes()
    add(
        "RELEASE.DOWNLOAD",
        same,
        f"回下载件与本地副本一致（sha256 {sha256_file(asset)[:16]}…）"
        if same
        else f"回下载件 {sha256_file(downloaded)[:16]}… ≠ 本地副本 {sha256_file(asset)[:16]}…",
    )


# ── 四、远端（--online）───────────────────────────────────────────────────────
def gh_available() -> bool:
    return shutil.which("gh") is not None


def check_online(tag: str, version: str) -> None:
    if not gh_available():
        add("RELEASE.ONLINE", False, "`gh` 不在 PATH —— --online 档无法判定（不是跳过）")
        return
    slug = remote_slug()
    if slug is None:
        add("RELEASE.ONLINE", False, "没有 origin 远端 —— 先建仓并 push")
        return
    proc = run_cmd(["gh", "api", f"repos/{slug}/releases/tags/{tag}"])
    if proc.returncode != 0:
        add("RELEASE.ONLINE", False, f"远端没有 {tag} 的 Release: {proc.stdout.strip()[:200]}")
        return
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        add("RELEASE.ONLINE", False, f"gh api 返回的不是 JSON: {proc.stdout.strip()[:200]}")
        return
    assets = payload.get("assets") or []
    # 口径 A（K34）：**手工上传附件** ≥1。GitHub 自动生成的 Source code 不在 `assets` 里，
    # 所以"assets 非空"等价于"确实手工传了东西"。
    manual = [a for a in assets if a.get("name")]
    expected = {attachment_name(version), SHA_NAME}
    got = {str(a.get("name")) for a in manual}
    problems: list[str] = []
    if not manual:
        problems.append("Release 没有任何手工上传附件（口径 A 不可降级，K34）")
    if not expected <= got:
        problems.append(f"缺附件 {sorted(expected - got)}（实际 {sorted(got)}）")
    for asset in manual:
        name = str(asset.get("name"))
        digest = asset.get("digest")
        if not digest:
            continue  # GitHub 只在较新版本给 digest；没有就不拿它判（回下载对账另有判据）
        local = LOCAL_DIR / name
        if not local.is_file():
            problems.append(f"{name}: 本地没有同名副本可比摘要")
            continue
        want = f"sha256:{sha256_file(local)}"
        if str(digest).lower() != want:
            problems.append(f"{name}: 远端 digest {digest} ≠ 本地 {want}")
    add(
        "RELEASE.ONLINE",
        not problems,
        "；".join(problems) if problems
        else f"{slug} / {tag}：{len(manual)} 个手工附件（{sorted(got)}），摘要与本地一致",
    )


def check_ci(tag: str) -> None:
    """留档 §二 记的 run id 必须真跑过且绿（``plan/05`` §4 U1 的关闭条件）。"""
    text = read(DOC_REL) or ""
    after = text.split("## 二、", 1)[1] if "## 二、" in text else ""
    ids = re.findall(r"run[ _-]?id\s*[:：=]?\s*(\d{6,})", after, re.IGNORECASE)
    if not ids:
        add("RELEASE.CI", False, "§二 还没记首推 CI 的 run id（U1 的关闭条件是真实 run id）")
        return
    run_id = ids[-1]
    slug = remote_slug()
    if not gh_available() or slug is None:
        add("RELEASE.CI", False, f"记了 run id={run_id}，但本机无法核（缺 gh 或 origin）")
        return
    if not re.fullmatch(r"\d{6,}", run_id):
        add("RELEASE.CI", False, f"run id {run_id!r} 形态不合法")
        return
    proc = run_cmd(["gh", "api", f"repos/{slug}/actions/runs/{run_id}"])
    if proc.returncode != 0:
        add("RELEASE.CI", False, f"run {run_id} 在 {slug} 上查不到: {proc.stdout.strip()[:160]}")
        return
    try:
        run = json.loads(proc.stdout)
    except json.JSONDecodeError:
        add("RELEASE.CI", False, f"run {run_id} 的返回不是 JSON")
        return
    conclusion = str(run.get("conclusion") or "")
    head_sha = str(run.get("head_sha") or "")
    tag_sha = tag_commit(tag)
    problems: list[str] = []
    if conclusion != "success":
        problems.append(f"conclusion={conclusion!r}（必须 success）")
    if tag_sha and head_sha and head_sha != tag_sha:
        problems.append(f"head_sha={head_sha[:12]} ≠ tag 提交 {tag_sha[:12]}")
    add(
        "RELEASE.CI",
        not problems,
        "；".join(problems) if problems
        else f"run {run_id} = success，head_sha 与 tag {tag} 一致（{tag_sha[:12]}）",
    )


# ── 主流程 ──────────────────────────────────────────────────────────────────
def _run(fn: Callable[[], None], check_id: str) -> None:
    try:
        fn()
    except Exception:  # noqa: BLE001 - 门永不崩
        add(check_id, False, "判据执行异常: " + traceback.format_exc(limit=1).strip().replace("\n", " "))


def main(argv: list[str] | None = None) -> int:
    parser = ArgumentParser(prog="check_release", description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--pre-tag", action="store_true", help="tag 之前的留档与名字占用核对")
    mode.add_argument("--offline", action="store_true", help="本地附件对账（不联网）")
    mode.add_argument("--online", action="store_true", help="远端 Release 对账（需 gh + origin）")
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:  # argparse 的用法错误是 2，与本门口径一致
        return RC_USAGE if exc.code else RC_OK

    stage = "pre-tag" if args.pre_tag else ("offline" if args.offline else "online")

    version = version_from_source() or "0.0.0"
    tag = tag_name(version)
    #: ``--online`` 要求 tag 已在（它是最后一档）；``--pre-tag`` / ``--offline`` 在 tag 未打时放过。
    strict_tag = stage == "online"

    _run(check_doc, "RELEASE.DOC")
    _run(check_name_occupancy, "RELEASE.NAME")
    _run(check_version, "RELEASE.VERSION")
    _run(lambda: check_self_reference(tag), "RELEASE.TREE")
    _run(lambda: check_tag(tag, strict_tag), "RELEASE.TAG")

    if stage in ("offline", "online"):
        _run(lambda: check_local_assets(tag, version), "RELEASE.ASSETS")
        _run(lambda: check_digest(version), "RELEASE.DIGEST")
        _run(lambda: check_source(tag, version), "RELEASE.SOURCE")
        _run(lambda: check_download(tag, version), "RELEASE.DOWNLOAD")

    if stage == "online":
        _run(lambda: check_online(tag, version), "RELEASE.ONLINE")
        _run(lambda: check_ci(tag), "RELEASE.CI")

    failures = [c for c in CHECKS if not c[1]]
    out = [
        f"发布门（{stage} 档） · 只读",
        "=" * 56,
        *[f"{'PASS' if ok else 'FAIL'}  {cid}  {detail}" for cid, ok, detail in CHECKS],
        "=" * 56,
        f"本轮实检 {COUNTED['checked']} 项 / 不适用 {COUNTED['skipped']} 项（不适用均写明原因）",
        f"结论: {'全绿' if not failures else f'{len(failures)} 项 FAIL'}",
    ]
    sys.stdout.write("\n".join(out) + "\n")
    return RC_OK if not failures else RC_BAD


if __name__ == "__main__":
    raise SystemExit(main())
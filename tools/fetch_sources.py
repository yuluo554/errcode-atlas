"""取数脚本：把三平台头文件原文取到本地，并登记钉死的 commit sha。

**它不参与构建**（`plan/02` D2）：构建只读入仓的 `data/catalog/*.yaml`；
本脚本存在的意义是「任何一条入仓数值背后都必须有一份能重跑出它的取数命令」（`plan/04` §1.2）。

三条渠道纪律：

1. 只走 ``gh api repos/<owner>/<repo>/contents/<path>``。
   ``raw.githubusercontent.com`` 在本机 HTTP 000（不可达，`data/README.md` §2.1 实测），
   ``github.com`` 网页直连亦被重置 —— 所以这里**不提供** raw 回退路径（有回退就等于有假绿）。
2. 取完立刻记下 **commit sha**（``source.ref`` 的证据）。没有 sha 的取数结果会随上游漂移，
   而漂移出来的数值与"当初核对过"是两件事。
3. 产出落 ``_headers/``（`.gitignore` 封）：入库的是**抽取结果**，不是原料。

用法::

    py -3.12 tools/fetch_sources.py --list
    py -3.12 tools/fetch_sources.py --out _headers
    py -3.12 tools/fetch_sources.py --out _headers --only linux-errno-base
    py -3.12 tools/fetch_sources.py --out _headers --ref torvalds/linux=<sha>
    py -3.12 tools/fetch_sources.py --out _headers --check   # 已取件与 SOURCES.json 的 sha256 对账

退出码：``0`` 全部成功 / ``1`` ``--check`` 发现不一致 / ``2`` 用法错误 / ``3`` 取数失败。
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[1]

#: 默认产出目录。`.gitignore` 已封（`_headers/`）：原料不入仓。
DEFAULT_OUT = REPO_ROOT / "_headers"
MANIFEST_NAME = "SOURCES.json"


class Source(NamedTuple):
    """一份要取的原文。``dest`` 是本地文件名（不含目录）。"""

    id: str
    repo: str
    path: str
    dest: str


#: 取数清单。**只增不改**：改一条已有的 `path` 会让历史抽取结果失去出处。
SOURCES: tuple[Source, ...] = (
    Source(
        "linux-errno-base",
        "torvalds/linux",
        "include/uapi/asm-generic/errno-base.h",
        "linux-errno-base.h",
    ),
    Source(
        "linux-errno",
        "torvalds/linux",
        "include/uapi/asm-generic/errno.h",
        "linux-errno.h",
    ),
    Source(
        "linux-signal",
        "torvalds/linux",
        "include/uapi/asm-generic/signal.h",
        "linux-signal.h",
    ),
    Source(
        "macos-errno",
        "apple-oss-distributions/xnu",
        "bsd/sys/errno.h",
        "macos-errno.h",
    ),
    Source(
        "macos-signal",
        "apple-oss-distributions/xnu",
        "bsd/sys/signal.h",
        "macos-signal.h",
    ),
)

BY_ID = {source.id: source for source in SOURCES}


class FetchError(RuntimeError):
    """取数失败。**不静默跳过**：缺一份原文就不该继续往下抽取。"""


def _gh(args: list[str]) -> str:
    """调 ``gh``。失败一律抛 ``FetchError``（不让半截输出流过）。"""
    try:
        proc = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except FileNotFoundError as exc:  # pragma: no cover - gh 不在 PATH 时的出口
        raise FetchError("找不到 gh：本脚本只走 gh api 通路（见 data/README.md §2.1）") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else f"rc={proc.returncode}"
        raise FetchError(f"gh {' '.join(args[:3])} 失败: {tail}")
    return proc.stdout


def resolve_ref(repo: str) -> str:
    """取仓库默认分支的 HEAD sha —— 这就是入编目的 ``source.ref``。"""
    branch = _gh(["api", f"repos/{repo}", "--jq", ".default_branch"]).strip()
    if not branch:
        raise FetchError(f"{repo}: 读不出 default_branch")
    sha = _gh(["api", f"repos/{repo}/commits/{branch}", "--jq", ".sha"]).strip()
    if not sha or len(sha) < 7:
        raise FetchError(f"{repo}: 读不出 commit sha")
    return sha


def fetch_one(source: Source, ref: str) -> bytes:
    """取一份原文（base64 解码）。

    大文件（>1 MB）时 GitHub 的 contents 接口返回 ``content: ""``、``encoding: "none"`` ——
    那会儿必须走 blobs 接口，否则会拿到 0 字节却"看起来成功"。
    """
    payload = _gh(
        [
            "api",
            f"repos/{source.repo}/contents/{source.path}?ref={ref}",
            "--jq",
            "{content: .content, encoding: .encoding, sha: .sha, size: .size}",
        ]
    )
    try:
        meta = json.loads(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover - gh 输出异常时的出口
        raise FetchError(f"{source.id}: gh 输出不是 JSON") from exc

    encoding = meta.get("encoding")
    content = meta.get("content") or ""
    if encoding != "base64" or not content:
        blob_sha = meta.get("sha")
        if not blob_sha:
            raise FetchError(f"{source.id}: 既无 base64 content 也无 blob sha")
        content = _gh(["api", f"repos/{source.repo}/git/blobs/{blob_sha}", "--jq", ".content"])
        content = content.strip()
        if not content:
            raise FetchError(f"{source.id}: blobs 接口也没给出内容（{meta.get('size')} bytes）")

    try:
        data = base64.b64decode(content, validate=False)
    except (ValueError, TypeError) as exc:
        raise FetchError(f"{source.id}: base64 解码失败") from exc
    if not data:
        raise FetchError(f"{source.id}: 取到 0 字节 —— 当成功处理会让抽取静默空转")
    return data


def _write(out_dir: Path, name: str, data: bytes) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / name
    target.write_bytes(data)
    return target


def _manifest_entry(source: Source, ref: str, data: bytes, fetched_at: str) -> dict[str, str]:
    return {
        "id": source.id,
        "repo": source.repo,
        "path": source.path,
        "dest": source.dest,
        "ref": ref,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": str(len(data)),
        "fetched_at": fetched_at,
    }


def _load_manifest(out_dir: Path) -> dict[str, dict[str, str]]:
    path = out_dir / MANIFEST_NAME
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FetchError(f"{MANIFEST_NAME} 不是合法 JSON: {exc}") from exc
    entries = payload.get("sources")
    return {item["id"]: item for item in entries} if isinstance(entries, list) else {}


def _render_manifest(entries: dict[str, dict[str, str]], refs: dict[str, str]) -> str:
    ordered = [entries[key] for key in sorted(entries)]
    body = {
        "generator_version": _tool_version(),
        "refs": {repo: sha for repo, sha in sorted(refs.items())},
        "sources": ordered,
    }
    return json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _tool_version() -> str:
    return "m1"


def run_fetch(out_dir: Path, only: Iterable[str], ref_overrides: dict[str, str]) -> int:
    selected = [BY_ID[i] for i in only] if only else list(SOURCES)
    if not selected:
        sys.stderr.write("fetch_sources: --only 没匹配到任何清单项\n")
        return 2

    manifest = _load_manifest(out_dir)
    refs: dict[str, str] = {e["repo"]: e["ref"] for e in manifest.values() if e.get("ref")}
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    failures = 0

    for source in selected:
        try:
            ref = ref_overrides.get(source.repo) or refs.get(source.repo)
            if not ref:
                ref = resolve_ref(source.repo)
            data = fetch_one(source, ref)
            target = _write(out_dir, source.dest, data)
        except FetchError as exc:
            sys.stderr.write(f"fetch_sources: {source.id} 失败 —— {exc}\n")
            failures += 1
            continue
        manifest[source.id] = _manifest_entry(source, ref, data, fetched_at)
        refs[source.repo] = ref
        sys.stdout.write(
            f"fetch_sources: {source.id} -> {target.name} "
            f"({len(data)} bytes, {source.repo}@{ref[:12]})\n"
        )

    # 只有全成功才落清单：半截清单会把"没取到"记成"取过"
    if failures:
        sys.stderr.write(f"fetch_sources: {failures} 份取数失败，清单未更新\n")
        return 3
    _write(out_dir, MANIFEST_NAME, _render_manifest(manifest, refs).encode("utf-8"))
    return 0


def run_check(out_dir: Path) -> int:
    """``--check``：已取件是否还与清单一致（防止手改 `_headers/` 后下游抽取悄悄漂移）。"""
    manifest = _load_manifest(out_dir)
    if not manifest:
        sys.stderr.write(f"fetch_sources: {out_dir.name}/{MANIFEST_NAME} 不存在或无条目 —— 先跑一次取数\n")
        return 3
    problems: list[str] = []
    for key in sorted(manifest):
        item = manifest[key]
        target = out_dir / item["dest"]
        if not target.is_file():
            problems.append(f"{item['dest']}: 文件缺失")
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != item["sha256"]:
            problems.append(
                f"{item['dest']}: sha256 不符（清单={item['sha256'][:12]}… 实测={actual[:12]}…）"
            )
    if problems:
        for line in problems:
            sys.stderr.write(f"fetch_sources: {line}\n")
        return 1
    sys.stderr.write(f"fetch_sources: 一致（{len(manifest)} 份原文）\n")
    return 0


def run_list() -> int:
    for source in SOURCES:
        sys.stdout.write(f"{source.id:<20} {source.repo}/{source.path}\n")
    sys.stdout.write(f"共 {len(SOURCES)} 份\n")
    return 0


def _parse_overrides(raw: Iterable[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for item in raw:
        if "=" not in item:
            raise SystemExit(f"fetch_sources: --ref 需要 <owner/repo>=<sha>，实得 {item!r}")
        repo, sha = item.split("=", 1)
        overrides[repo.strip()] = sha.strip()
    return overrides


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fetch_sources", description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT), help=f"产出目录（默认 {DEFAULT_OUT.name}）")
    parser.add_argument("--list", action="store_true", help="打印取数清单（不联网）")
    parser.add_argument("--only", action="append", default=[], help="只取指定 id（可重复）")
    parser.add_argument("--ref", action="append", default=[], help="钉死 sha：<owner/repo>=<sha>")
    parser.add_argument("--check", action="store_true", help="已取件与 SOURCES.json 的 sha256 对账")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.list:
        return run_list()

    unknown = [i for i in args.only if i not in BY_ID]
    if unknown:
        sys.stderr.write(f"fetch_sources: 未知 id {unknown}（用 --list 看清单）\n")
        return 2

    out_dir = Path(args.out)
    try:
        if args.check:
            return run_check(out_dir)
        return run_fetch(out_dir, args.only, _parse_overrides(args.ref))
    except FetchError as exc:
        sys.stderr.write(f"fetch_sources: {exc}\n")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
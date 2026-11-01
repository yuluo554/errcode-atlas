"""呈现层：argv → 调用 → 退出码。**退出码映射的唯一处**（plan/02 D5）。

三条纪律：
* ``argparse`` 原生对用法错误是 ``SystemExit(2)``；本入口统一捕获并映射成
  ``contract.EXIT_USAGE``（4），使「cli.main() 返回 4」与「子进程退出码 4」两条形态一致。
* 判定层返回结果对象，**不返回退出码**；映射只在这里发生。
* 错误一律走 stderr，单行 + 可机读前缀 ``errcode-atlas: ``；``--json`` 时 stderr 也出 JSON。
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Sequence

from . import __version__, contract, report
from .catalog import Catalog, CatalogError, load
from .exitcode import attribute
from .explain import Query, explain

PROG = "errcode-atlas"
ERROR_PREFIX = f"{PROG}: "


class UsageError(Exception):
    """用法错误 → ``contract.EXIT_USAGE``。"""


def _ensure_utf8_stdio() -> None:
    """按 ``stream.encoding`` 探针决定是否 reconfigure。

    中文控制台（cp936）保持不动；只有编码装不下本项目输出时才切到 UTF-8。
    这条是"`py -X utf8` 是本机习惯、也是 CI 盲区"的落法（AGENTS.md §三）。
    """
    for stream in (sys.stdout, sys.stderr):
        encoding = (getattr(stream, "encoding", "") or "").lower()
        if encoding in ("utf-8", "utf8"):
            continue
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):  # pragma: no cover - 桩对象/不支持时静默
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="三平台错误码与退出码判定表：给定「数字 + 平台 + 语境」，判它能否被唯一归因。",
        epilog=(
            "判定结果不可唯一归因（AMBIGUOUS / PLATFORM-ABSENT / UNATTRIBUTABLE）时退出码为 1，"
            "那是正确结论，不是失败。"
        ),
    )
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p_explain = sub.add_parser("explain", help="数字/名字 → 语义判定（五判定态）")
    p_explain.add_argument("query", help="数字（如 98）或常量名（如 EADDRINUSE）")
    p_explain.add_argument("--platform", help="linux | macos | win32-node | win32-python")
    p_explain.add_argument("--domain", choices=contract.DOMAINS, help="errno | signal | exit")
    p_explain.add_argument("--json", action="store_true", help="机读输出")

    p_exit = sub.add_parser("exitcode", help="进程退出码 → 归因")
    p_exit.add_argument("code", help="进程退出码（整数）")
    p_exit.add_argument("--platform", required=True, help="linux | macos | win32-node | win32-python")
    p_exit.add_argument("--json", action="store_true", help="机读输出")

    p_build = sub.add_parser("build", help="校验随包编目（冻结面）")
    p_build.add_argument("--check", action="store_true", help="校验摘要与结构（默认行为）")
    p_build.add_argument("--json", action="store_true", help="机读输出")

    sub.add_parser("selftest", help="内置不变量自测")
    sub.add_parser("bench", help="跑 fixtures 基准语料")
    return parser


def _normalize_platform(value: str | None) -> str | None:
    """``win32`` / ``windows`` 是**必须被拒绝**的别名 —— 它们掩盖了两个视角的数值差异。"""
    if value is None:
        return None
    key = value.strip().lower()
    if key in contract.AMBIGUOUS_PLATFORM_ALIASES:
        raise UsageError(contract.AMBIGUOUS_PLATFORM_ALIASES[key])
    if key not in contract.PLATFORMS:
        raise UsageError(
            f"--platform {value!r} 不支持；可选：{', '.join(contract.PLATFORMS)}"
        )
    return key


def _emit(text: str) -> None:
    sys.stdout.write(text)


def _fail(message: str, code: int, as_json: bool = False) -> int:
    if as_json:
        sys.stderr.write(report.to_json({"error": message, "exit_code": code}))
    else:
        sys.stderr.write(ERROR_PREFIX + message + "\n")
    return code


def _load_catalog() -> Catalog:
    try:
        return load()
    except CatalogError as exc:
        raise CatalogError(str(exc)) from exc


# ── 子命令 ──────────────────────────────────────────────────────────────────
def _cmd_explain(args: argparse.Namespace, catalog: Catalog) -> int:
    platform = _normalize_platform(args.platform)
    try:
        query = Query.parse(args.query, platform, args.domain)
    except ValueError as exc:
        raise UsageError(str(exc)) from exc
    result = explain(query, catalog)
    payload = result.as_dict()
    if args.json:
        _emit(report.to_json(payload))
    else:
        _emit(report.render_explanation(payload))
    return result.exit_code


def _cmd_exitcode(args: argparse.Namespace, catalog: Catalog) -> int:
    platform = _normalize_platform(args.platform)
    if platform is None:  # argparse required=True 已挡住，这里防"被绕过"
        raise UsageError("exitcode 必须指定 --platform")
    try:
        code = int(str(args.code), 10)
    except ValueError as exc:
        raise UsageError(f"退出码必须是整数，实得 {args.code!r}") from exc
    result = attribute(code, platform, catalog)
    payload = result.as_dict()
    if args.json:
        _emit(report.to_json(payload))
    else:
        _emit(report.render_attribution(payload))
    return result.exit_code


def _cmd_build(args: argparse.Namespace, catalog: Catalog) -> int:
    """运行期只做**校验**（生成在 dev 侧的 tools/build_catalog.py，plan/02 D2）。"""
    counts = catalog.entry_count()
    payload = {
        "status": "ok",
        "schema_version": catalog.schema_version,
        "generator_version": catalog.generator_version,
        "platforms": list(catalog.platforms()),
        "entry_count": counts,
    }
    if args.json:
        _emit(report.to_json(payload))
    else:
        rows = [(domain, count) for domain, count in sorted(counts.items())]
        _emit(
            f"编目校验通过（schema {catalog.schema_version}，生成器 {catalog.generator_version}）\n"
            + report.render_table(("域", "条目数"), rows)
            + "\n"
        )
    return contract.EXIT_OK


def _cmd_selftest(args: argparse.Namespace, catalog: Catalog) -> int:  # noqa: ARG001
    from .selftest import run_selftest

    failures = run_selftest(catalog)
    for line in failures:
        _emit(f"FAIL  {line}\n")
    _emit(f"selftest: {'全绿' if not failures else f'{len(failures)} 项失败'}\n")
    return contract.EXIT_OK if not failures else contract.EXIT_NON_UNIQUE


def _cmd_bench(args: argparse.Namespace, catalog: Catalog) -> int:  # noqa: ARG001
    from .bench import run_bench

    return run_bench(catalog)


# ── 入口 ────────────────────────────────────────────────────────────────────
_DISPATCH = {
    "explain": _cmd_explain,
    "exitcode": _cmd_exitcode,
    "build": _cmd_build,
    "selftest": _cmd_selftest,
    "bench": _cmd_bench,
}


def main(argv: Sequence[str] | None = None) -> int:
    _ensure_utf8_stdio()
    parser = build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:  # argparse 的用法错误是 2；本项目统一映射成 4
        code = exc.code if isinstance(exc.code, int) else contract.EXIT_USAGE
        if code == 0:  # --help / --version 是正常出口
            return 0
        return contract.EXIT_USAGE

    if not getattr(args, "command", None):
        parser.print_help()
        return contract.EXIT_USAGE

    as_json = bool(getattr(args, "json", False))
    try:
        catalog = _load_catalog()
        handler = _DISPATCH[args.command]
        return handler(args, catalog)
    except UsageError as exc:
        return _fail(str(exc), contract.EXIT_USAGE, as_json)
    except CatalogError as exc:
        return _fail(str(exc), contract.EXIT_UNDECIDABLE, as_json)
    except KeyError:  # pragma: no cover - argparse 已限定 command 取值
        return _fail(f"未知子命令: {args.command}", contract.EXIT_USAGE, as_json)


def console_main() -> Any:  # pragma: no cover - setuptools 入口
    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
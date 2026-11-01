"""抽取脚本：``_headers/*.h`` 原文 + 本机两条运行时 → ``data/catalog/*.yaml``。

为什么要有这个脚本（而不是手抄一遍 YAML）：

* ``plan/04`` §1.2 的纪律 —— **任何一条入仓数值背后都必须有一份"能重跑出它"的取数命令**。
  手抄的 YAML 没有这样的命令；重跑本脚本即可逐字节复现，于是"抄错一行"变成可检测的差异。
* 行号必须由**解析器**给出，不能由人手填。手填的行号与原文对不上时，``source`` 就退化成安慰剂
  —— 而 ``source`` 是本题"每条数值带出处"的唯一凭据。
* 被**排除**的 ``#define`` 也要自动列出来（``--report``），否则 ``data/gaps.md`` 里那句
  "为什么没入编目"就要靠人回忆。三态纪律（全录/部分录/未录）因此是数出来的，不是写出来的。

与 ``tools/build_catalog.py`` 的分工：本脚本产 **YAML 源**（dev 侧），那个脚本产 **冻结 JSON**（随包）。
**本脚本不参与构建** —— 构建只读 YAML（``plan/02`` D2）。

预处理器口径（这是"逐条"二字的技术含义）
-------------------------------------------
头文件里的 ``#define E*`` / ``#define SIG*`` 并非都在同一个编译环境里可见。本脚本按表里写死的
**默认编译环境**求值每条 ``#if/#ifdef/#elif`` 链，只收**该环境下可见**的分支：

* macOS 用户态默认：``__DARWIN_C_LEVEL = __DARWIN_C_FULL``（900000）、``__DARWIN_UNIX03 = 1``、
  ``KERNEL`` / ``KERNEL_PRIVATE`` / ``BSD_KERNEL_PRIVATE`` / ``PRIVATE`` / ``_POSIX_C_SOURCE``
  / ``_ANSI_SOURCE`` 均**未定义**（来源：xnu ``bsd/sys/cdefs.h`` 第 805–829、1028–1037 行，
  同一个 ``ref`` 可取）。
* Linux uapi 默认：``__KERNEL__`` / ``__ASSEMBLY__`` / ``SA_RESTORER`` 未定义。

不可见分支里的定义**不会静默丢弃**：它们进 ``--report`` 的 excluded 一栏，
由 ``data/gaps.md`` 逐类承接。

用法::

    py -3.12 tools/extract_catalog.py --out data/catalog
    py -3.12 tools/extract_catalog.py --check          # 与仓库里的 YAML 逐字节比对
    py -3.12 tools/extract_catalog.py --report         # 打印被排除的定义及原因（不写文件）

退出码：``0`` 成功 / ``1`` ``--check`` 不一致 / ``2`` 用法错误 / ``3`` 原料缺失。

安全说明：本脚本执行的两条外部命令（``node`` / 解释器自身）的参数是**模块级常量**，
不存在把外部输入拼进命令行的通路；因此不接受任何来自文件或参数的命令文本。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
HEADERS_DIR = REPO_ROOT / "_headers"
SOURCES_MANIFEST = HEADERS_DIR / "SOURCES.json"
DEFAULT_OUT = REPO_ROOT / "data" / "catalog"

VERIFIED_AT = "2026-11-01"

#: 运行时视角的**钉死版本**。`program_version` 必须是常量，不能取"跑本脚本的那个解释器"。
#:
#: 本项目实测过的坑（`py -3.8 tools/extract_catalog.py --check` 报 win32-python 不一致，
#: 而两份 `errno` 模块的内容逐项相同）：用 `sys.executable` 取版本时，**换一条解释器通道
#: 重跑抽取就会写出不同的 `program_version`** —— 数值全对、文字变了，于是 `--check` 与
#: `extract_catalog.py` 的复现性判据一起红。这不是数据错，是**出处字段没有钉死**。
#: 判据 = "这个字段是**事实**（某天在某机器上实读），还是**本次运行的环境**？"——前者必须常量。
#:
#: 取值来源：2026-11-01 在本机 win32 上实读得到的那一份（`_headers/` 已按它核对过）。
PINNED_RUNTIME_VERSIONS = {
    "node": "v24.15.0",
    "python": "3.12.10",
}

#: 平台 -> 该平台 errno 条目所依据的头文件（id 见 ``tools/fetch_sources.py`` 的清单）。
ERRNO_HEADERS = {
    "linux": ("linux-errno-base", "linux-errno"),
    "macos": ("macos-errno",),
}
SIGNAL_HEADERS = {
    "linux": ("linux-signal",),
    "macos": ("macos-signal",),
}

ERRNO_NAME = re.compile(r"^E[A-Z0-9_]+$")
SIGNAL_NAME = re.compile(r"^SIG[A-Z0-9]+$")

#: 名字长得像信号、但**不是信号编号**的宏。排除理由逐条写在这里，而不是靠人记。
SIGNAL_NOT_A_NUMBER = {
    "SIG_DFL": "信号处理函数取值（(void(*)(int))0），不是信号编号",
    "SIG_IGN": "信号处理函数取值，不是信号编号",
    "SIG_ERR": "信号处理函数取值，不是信号编号",
    "SIG_HOLD": "信号处理函数取值，不是信号编号",
    "SIG_BLOCK": "sigprocmask 的动作参数，不是信号编号",
    "SIG_UNBLOCK": "sigprocmask 的动作参数，不是信号编号",
    "SIG_SETMASK": "sigprocmask 的动作参数，不是信号编号",
    "SIGEV_NONE": "sigevent 的取值，不是信号编号",
    "SIGEV_SIGNAL": "sigevent 的取值，不是信号编号",
    "SIGEV_THREAD": "sigevent 的取值，不是信号编号",
    "SIGEV_KEVENT": "sigevent 的取值，不是信号编号",
    "SIGSTKSZ": "备用栈尺寸（字节数），不是信号编号",
    "MINSIGSTKSZ": "备用栈最小尺寸（字节数），不是信号编号",
    "SIGRTMIN": "实时信号下界。原文写「should not be considered constants from userland」"
    "（linux signal.h 第 49 行），且实际值由 libc/架构再定；入编目会造出跨架构的假精确",
    "SIGRTMAX": "实时信号上界，理由同 SIGRTMIN（其值是 `_NSIG` 而非字面量）",
}

#: 编译器条件表达式里可能出现的比较目标。只列本仓真正用到的。
MACRO_ENV = {
    "macos": {
        "__DARWIN_C_LEVEL": 900000,  # __DARWIN_C_FULL
        "__DARWIN_C_FULL": 900000,
        "__DARWIN_UNIX03": 1,
        "__DARWIN_ONLY_UNIX_CONFORMANCE": 1,
        "__x86_64__": 1,
        "_POSIX_C_SOURCE": None,
        "_ANSI_SOURCE": None,
        "_NONSTD_SOURCE": None,
        "_DARWIN_C_SOURCE": None,
        "KERNEL": None,
        "KERNEL_PRIVATE": None,
        "BSD_KERNEL_PRIVATE": None,
        "PRIVATE": None,
    },
    "linux": {
        "__KERNEL__": None,
        "__ASSEMBLY__": None,
        "SA_RESTORER": None,
    },
}

#: 头文件 id -> 上游仓库。ref 从 ``_headers/SOURCES.json`` 读，不在这里写死。
HEADER_REPOS = {
    "linux-errno-base": "torvalds/linux",
    "linux-errno": "torvalds/linux",
    "linux-signal": "torvalds/linux",
    "macos-errno": "apple-oss-distributions/xnu",
    "macos-signal": "apple-oss-distributions/xnu",
}

#: 头文件 id -> 入 ``source["file"]`` 的上游路径（不是本地缓存路径 —— 出处指上游）。
HEADER_PATHS = {
    "linux-errno-base": "include/uapi/asm-generic/errno-base.h",
    "linux-errno": "include/uapi/asm-generic/errno.h",
    "linux-signal": "include/uapi/asm-generic/signal.h",
    "macos-errno": "bsd/sys/errno.h",
    "macos-signal": "bsd/sys/signal.h",
}

#: Node 侧取数的固定探针（常量，不是拼接出来的）。
NODE_PROBE = "const o=require('os').constants;process.stdout.write(JSON.stringify({errno:o.errno,signals:o.signals}))"
PY_CONSTANTS_PROBE = (
    "import errno, json, signal\n"
    "e = {k: v for k, v in vars(errno).items()"
    " if k.isupper() and isinstance(v, int) and not isinstance(v, bool)}\n"
    "s = {k: int(v) for k, v in vars(signal).items()"
    " if k.startswith('SIG') and isinstance(v, int)"
    " and not isinstance(v, bool) and not k.startswith('SIG_')}\n"
    "print(json.dumps({'errno': e, 'signals': s}))\n"
)


class ExtractError(RuntimeError):
    """原料缺失或结构不可解析。**不静默降级**为空编目。"""


# ── 预处理指令求值 ──────────────────────────────────────────────────────────
_TOKEN = re.compile(
    r"\s*(defined\s*\(?\s*[A-Za-z_]\w*\s*\)?|\d+[lL]?|[A-Za-z_]\w*|&&|\|\||==|!=|>=|<=|[-+<>()!])"
)


def _tokenize(expr: str) -> list[str]:
    tokens: list[str] = []
    pos = 0
    while pos < len(expr):
        match = _TOKEN.match(expr, pos)
        if not match:
            raise ExtractError(f"无法解析的条件表达式片段: {expr[pos:]!r}")
        tokens.append(match.group(1))
        pos = match.end()
    return tokens


def evaluate_condition(expr: str, env: dict[str, int | None]) -> bool:
    """求值 ``#if`` 表达式。**未定义的宏按 C 语义取 0**，不抛错。"""
    tokens = _tokenize(expr)
    state = {"index": 0}

    def peek() -> str | None:
        return tokens[state["index"]] if state["index"] < len(tokens) else None

    def take() -> str:
        token = tokens[state["index"]]
        state["index"] += 1
        return token

    def primary() -> int:
        token = peek()
        if token is None:
            raise ExtractError(f"条件表达式意外结束: {expr!r}")
        if token.startswith("defined"):
            take()
            name = token[len("defined") :].strip()
            if name.startswith("("):
                name = name.strip("()").strip()
            if not name:  # `defined ( X )` 被切成两个 token 的情形
                if peek() == "(":
                    take()
                name = take()
                if peek() == ")":
                    take()
            return 1 if env.get(name) is not None else 0
        if token == "(":
            take()
            result = disjunction()
            if peek() != ")":
                raise ExtractError(f"括号不配对: {expr!r}")
            take()
            return result
        if token == "!":
            take()
            return 0 if primary() else 1
        if token == "-":
            take()
            return -primary()
        take()
        if token.isdigit():
            return int(token.rstrip("lL"))
        resolved = env.get(token)
        return 0 if resolved is None else resolved

    def comparison() -> int:
        left = primary()
        while peek() in ("==", "!=", ">=", "<=", "<", ">"):
            operator = take()
            right = primary()
            table = {
                "==": left == right,
                "!=": left != right,
                ">=": left >= right,
                "<=": left <= right,
                "<": left < right,
                ">": left > right,
            }
            left = int(table[operator])
        return left

    def conjunction() -> int:
        left = comparison()
        while peek() == "&&":
            take()
            right = comparison()
            left = 1 if (left and right) else 0
        return left

    def disjunction() -> int:
        left = conjunction()
        while peek() == "||":
            take()
            right = conjunction()
            left = 1 if (left or right) else 0
        return left

    result = disjunction()
    if state["index"] != len(tokens):
        raise ExtractError(f"条件表达式有多余片段: {expr!r}")
    return bool(result)


# ── 逐行扫描 ────────────────────────────────────────────────────────────────
@dataclass
class Definition:
    name: str
    value: int
    line: int
    alias_of: str = ""


@dataclass
class Skipped:
    name: str
    reason: str
    line: int


@dataclass
class Scanned:
    defined: list[Definition] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)


def _strip_comments(line: str, in_block: bool) -> tuple[str, bool]:
    """去掉行内注释，返回 (代码部分, 结束后的 in_block 状态)。"""
    out: list[str] = []
    index = 0
    while index < len(line):
        if in_block:
            end = line.find("*/", index)
            if end < 0:
                return "".join(out), True
            index = end + 2
            in_block = False
            continue
        if line.startswith("/*", index):
            in_block = True
            index += 2
            continue
        if line.startswith("//", index):
            break
        out.append(line[index])
        index += 1
    return "".join(out), in_block


_DEFINE = re.compile(r"^\s*#\s*define\s+([A-Za-z_]\w*)\s+(.+?)\s*$")
_DIRECTIVE = re.compile(r"^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b\s*(.*)$")
_LITERAL = re.compile(r"^(-?)\s*\(?\s*(\d+)[lL]?\s*\)?$")


def scan_header(
    path: Path,
    env: dict[str, int | None],
    name_pattern: re.Pattern[str],
    symbols: dict[str, int] | None = None,
) -> Scanned:
    """扫描一份头文件，返回该编译环境下可见的定义 + 被排除的定义。

    ``#if`` 链按栈求值：每一层记 (父层是否可见, 本链是否已有分支命中, 本分支当前是否可见)。

    ``symbols`` 由调用方传入时会被**就地累加**：errno 分成 ``errno-base.h`` 与 ``errno.h``
    两份，而 ``errno.h`` 里的 ``#define EWOULDBLOCK EAGAIN`` 指向的是**前一份**里的数值
    （``errno.h`` 第 5 行 ``#include <asm-generic/errno-base.h>``）。
    每份文件各用一个空字典 → 这条别名会被误判成"值是另一个宏，可见区里没有数值定义"，
    于是 EWOULDBLOCK 凭空消失 —— 本项目实测过这一种假缺口。
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ExtractError(
            f"原料缺失: {path.name}（先跑 tools/fetch_sources.py --out _headers）"
        ) from exc

    in_block = False
    stack: list[list[bool]] = []
    if symbols is None:
        symbols = {}
    result = Scanned()

    def visible() -> bool:
        return all(frame[2] for frame in stack)

    for line_no, raw in enumerate(text.splitlines(), 1):
        code, in_block = _strip_comments(raw, in_block)
        if not code.strip():
            continue

        directive = _DIRECTIVE.match(code)
        if directive:
            keyword, rest = directive.group(1), directive.group(2).strip()
            parent = visible()
            if keyword in ("if", "ifdef", "ifndef"):
                if keyword == "if":
                    condition = evaluate_condition(rest, env)
                elif keyword == "ifdef":
                    condition = env.get(rest.split()[0], None) is not None
                else:
                    condition = env.get(rest.split()[0], None) is None
                stack.append([parent, condition, condition])
            elif keyword in ("elif", "else"):
                if not stack:
                    raise ExtractError(f"{path.name}:{line_no}: 孤立 #{keyword}")
                frame = stack[-1]
                taken = True if keyword == "else" else evaluate_condition(rest, env)
                frame[2] = frame[0] and (not frame[1]) and taken
                frame[1] = frame[1] or taken
            else:  # endif
                if not stack:
                    raise ExtractError(f"{path.name}:{line_no}: 孤立 #endif")
                stack.pop()
            continue

        define = _DEFINE.match(code)
        if not define:
            continue
        name, raw_value = define.group(1), define.group(2).strip()
        if not name_pattern.match(name):
            continue
        if not visible():
            result.skipped.append(
                Skipped(name, "默认编译环境下该分支不可见（#if/#ifdef 未成立）", line_no)
            )
            continue
        if name in SIGNAL_NOT_A_NUMBER:
            result.skipped.append(Skipped(name, SIGNAL_NOT_A_NUMBER[name], line_no))
            continue

        literal = _LITERAL.match(raw_value)
        if literal:
            number = int(literal.group(2))
            if literal.group(1) == "-":
                number = -number
            symbols[name] = number
            result.defined.append(Definition(name, number, line_no))
            continue
        if re.fullmatch(r"[A-Za-z_]\w*", raw_value):
            if raw_value in symbols:
                symbols[name] = symbols[raw_value]
                result.defined.append(
                    Definition(name, symbols[raw_value], line_no, alias_of=raw_value)
                )
            else:
                result.skipped.append(
                    Skipped(name, f"值是另一个宏 {raw_value}，而它在可见区里没有数值定义", line_no)
                )
            continue
        result.skipped.append(Skipped(name, f"值不是字面量整数（{raw_value!r}）", line_no))

    return result


# ── 中文释义（原文注释永远是第一凭据；这里只做翻译）─────────────────────────
ERRNO_GLOSS = {
    "EPERM": "操作不被允许",
    "ENOENT": "没有这个文件或目录",
    "ESRCH": "没有这个进程",
    "EINTR": "系统调用被中断",
    "EIO": "输入/输出错误",
    "ENXIO": "没有这个设备或地址",
    "E2BIG": "参数列表过长",
    "ENOEXEC": "可执行格式错误",
    "EBADF": "文件描述符错误",
    "ECHILD": "没有子进程",
    "EAGAIN": "资源暂时不可用，请重试",
    "EWOULDBLOCK": "操作会阻塞（EAGAIN 的别名）",
    "ENOMEM": "内存不足",
    "EACCES": "权限不足",
    "EFAULT": "地址错误",
    "ENOTBLK": "需要块设备",
    "EBUSY": "设备或资源忙",
    "EEXIST": "文件已存在",
    "EXDEV": "跨设备链接",
    "ENODEV": "没有这个设备",
    "ENOTDIR": "不是目录",
    "EISDIR": "是目录",
    "EINVAL": "参数无效",
    "ENFILE": "系统打开文件数已达上限",
    "EMFILE": "进程打开文件数已达上限",
    "ENOTTY": "不是终端设备（ioctl 不适用）",
    "ETXTBSY": "文本文件忙",
    "EFBIG": "文件过大",
    "ENOSPC": "设备上没有剩余空间",
    "ESPIPE": "非法的定位操作",
    "EROFS": "只读文件系统",
    "EMLINK": "链接数过多",
    "EPIPE": "管道破裂",
    "EDOM": "数学参数超出定义域",
    "ERANGE": "数学结果不可表示",
    "EDEADLK": "资源死锁会发生（macOS 语义为「已避免」）",
    "EDEADLOCK": "资源死锁（EDEADLK 的别名）",
    "ENAMETOOLONG": "文件名过长",
    "ENOLCK": "没有可用的记录锁",
    "ENOSYS": "系统调用不支持/未实现",
    "ENOTEMPTY": "目录非空",
    "ELOOP": "符号链接层数过多",
    "ENOMSG": "没有所需类型的消息",
    "EIDRM": "标识符已被移除",
    "ECHRNG": "通道号超出范围",
    "EL2NSYNC": "第 2 级未同步",
    "EL3HLT": "第 3 级已停止",
    "EL3RST": "第 3 级已复位",
    "ELNRNG": "链接号超出范围",
    "EUNATCH": "协议驱动未挂接",
    "ENOCSI": "没有可用的 CSI 结构",
    "EL2HLT": "第 2 级已停止",
    "EBADE": "交换无效",
    "EBADR": "请求描述符无效",
    "EXFULL": "交换区已满",
    "ENOANO": "没有阳极",
    "EBADRQC": "请求码无效",
    "EBADSLT": "槽位无效",
    "EBFONT": "字体文件格式错误",
    "ENOSTR": "设备不是流",
    "ENODATA": "没有可用数据",
    "ETIME": "定时器超时",
    "ENOSR": "流资源不足",
    "ENONET": "机器不在网络上",
    "ENOPKG": "包未安装",
    "EREMOTE": "对象是远程的",
    "ENOLINK": "链路已断开",
    "EADV": "通告错误",
    "ESRMNT": "挂载错误",
    "ECOMM": "发送时通信错误",
    "EPROTO": "协议错误",
    "EMULTIHOP": "尝试了多跳",
    "EDOTDOT": "RFS 特有错误",
    "EBADMSG": "不是数据消息",
    "EFSBADCRC": "检测到 CRC 错误（EBADMSG 的别名）",
    "EOVERFLOW": "值对给定数据类型过大",
    "ENOTUNIQ": "名字在网络上不唯一",
    "EBADFD": "文件描述符状态错误",
    "EREMCHG": "远程地址已改变",
    "ELIBACC": "无法访问所需的共享库",
    "ELIBBAD": "访问了损坏的共享库",
    "ELIBSCN": "a.out 中的 .lib 段损坏",
    "ELIBMAX": "尝试链接过多共享库",
    "ELIBEXEC": "无法直接执行共享库",
    "EILSEQ": "非法字节序列",
    "ERESTART": "被中断的系统调用应当重启",
    "ESTRPIPE": "流管道错误",
    "EUSERS": "用户过多",
    "ENOTSOCK": "在非套接字上做套接字操作",
    "EDESTADDRREQ": "需要目的地址",
    "EMSGSIZE": "消息过长",
    "EPROTOTYPE": "套接字的协议类型错误",
    "ENOPROTOOPT": "协议不可用",
    "EPROTONOSUPPORT": "不支持的协议",
    "ESOCKTNOSUPPORT": "不支持的套接字类型",
    "EOPNOTSUPP": "该端点不支持此操作",
    "ENOTSUP": "不支持该操作",
    "EPFNOSUPPORT": "不支持的协议族",
    "EAFNOSUPPORT": "协议不支持该地址族",
    "EADDRINUSE": "地址已被占用",
    "EADDRNOTAVAIL": "无法分配请求的地址",
    "ENETDOWN": "网络已关闭",
    "ENETUNREACH": "网络不可达",
    "ENETRESET": "连接因重置被断开",
    "ECONNABORTED": "软件导致连接中止",
    "ECONNRESET": "对端重置了连接",
    "ENOBUFS": "没有可用的缓冲区空间",
    "EISCONN": "端点已连接",
    "ENOTCONN": "端点未连接",
    "ESHUTDOWN": "传输端点已关闭，不能再发送",
    "ETOOMANYREFS": "引用过多，无法拼接",
    "ETIMEDOUT": "连接超时",
    "ECONNREFUSED": "连接被拒绝",
    "EHOSTDOWN": "主机已关闭",
    "EHOSTUNREACH": "主机不可达",
    "EALREADY": "操作已在进行中",
    "EINPROGRESS": "操作正在进行中",
    "ESTALE": "过期的文件句柄",
    "EUCLEAN": "结构需要清理",
    "EFSCORRUPTED": "文件系统已损坏（EUCLEAN 的别名）",
    "ENOTNAM": "不是 XENIX 命名类型文件",
    "ENAVAIL": "没有可用的 XENIX 信号量",
    "EISNAM": "是命名类型文件",
    "EREMOTEIO": "远程 I/O 错误",
    "EDQUOT": "配额超限",
    "ENOMEDIUM": "没有找到介质",
    "EMEDIUMTYPE": "介质类型错误",
    "ECANCELED": "操作已取消",
    "ENOKEY": "所需的密钥不可用",
    "EKEYEXPIRED": "密钥已过期",
    "EKEYREVOKED": "密钥已被吊销",
    "EKEYREJECTED": "密钥被服务拒绝",
    "EOWNERDEAD": "持锁者已死",
    "ENOTRECOVERABLE": "状态不可恢复",
    "ERFKILL": "因射频禁用而无法操作",
    "EHWPOISON": "内存页存在硬件错误",
    "EFTYPE": "文件类型与预期操作不符",
    "EPROCLIM": "进程过多",
    "EBADRPC": "RPC 结构错误",
    "ERPCMISMATCH": "RPC 版本不匹配",
    "EPROGUNAVAIL": "RPC 程序不可用",
    "EPROGMISMATCH": "程序版本不匹配",
    "EPROCUNAVAIL": "程序中过程错误",
    "EAUTH": "认证错误",
    "ENEEDAUTH": "需要认证器",
    "EPWROFF": "设备已断电",
    "EDEVERR": "设备错误（如缺纸）",
    "EBADEXEC": "可执行文件损坏",
    "EBADARCH": "可执行文件中的 CPU 类型错误",
    "ESHLIBVERS": "共享库版本不匹配",
    "EBADMACHO": "Mach-O 文件格式错误",
    "ENOATTR": "找不到属性",
    "ENOPOLICY": "没有注册该策略",
    "ENOTCAPABLE": "能力不足",
    "ELAST": "最大 errno 的哨兵值（须等于最大的 errno）",
}

SIGNAL_GLOSS = {
    "SIGHUP": "挂起",
    "SIGINT": "中断",
    "SIGQUIT": "退出",
    "SIGILL": "非法指令",
    "SIGTRAP": "跟踪陷阱",
    "SIGABRT": "abort 中止",
    "SIGIOT": "SIGABRT 的历史别名",
    "SIGBUS": "总线错误",
    "SIGFPE": "浮点异常",
    "SIGKILL": "强制杀死（不可捕获、不可忽略）",
    "SIGUSR1": "用户自定义信号 1",
    "SIGSEGV": "段错误",
    "SIGUSR2": "用户自定义信号 2",
    "SIGPIPE": "向无读端的管道写入",
    "SIGALRM": "闹钟超时",
    "SIGTERM": "终止请求",
    "SIGSTKFLT": "协处理器栈错误（x86 专属）",
    "SIGCHLD": "子进程状态变化",
    "SIGCONT": "继续被停止的进程",
    "SIGSTOP": "停止（不可捕获、不可忽略）",
    "SIGTSTP": "终端停止",
    "SIGTTIN": "后台进程读终端",
    "SIGTTOU": "后台进程写终端",
    "SIGURG": "套接字紧急条件",
    "SIGXCPU": "超出 CPU 时间限制",
    "SIGXFSZ": "超出文件大小限制",
    "SIGVTALRM": "虚拟定时器超时",
    "SIGPROF": "性能分析定时器超时",
    "SIGWINCH": "窗口大小变化",
    "SIGIO": "异步 I/O 事件",
    "SIGPOLL": "可轮询事件（POSIX 名，SIGIO 的等价物）",
    "SIGPWR": "电源故障",
    "SIGSYS": "系统调用参数错误",
    "SIGUNUSED": "未使用（SIGSYS 的别名）",
    "SIGEMT": "EMT 指令（macOS 专属，占 7 号）",
    "SIGINFO": "信息请求（macOS 专属，BSD 传统）",
    "SIGBREAK": "Ctrl+Break（Windows 控制台事件）",
}


def gloss_for(name: str, comment: str) -> str:
    """释义优先取词表；词表没有的退回**原文注释**（绝不自行编造成因）。"""
    zh = ERRNO_GLOSS.get(name) or SIGNAL_GLOSS.get(name)
    if zh:
        return zh
    return comment.strip() or "（原文注释为空；释义见出处行）"


# ── 运行时视角 ──────────────────────────────────────────────────────────────
def _run(command: list[str]) -> str:
    """跑一条**参数列表**命令（无 shell）。参数全部来自本模块常量。"""
    try:
        proc = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", check=False
        )
    except FileNotFoundError as exc:
        raise ExtractError(f"找不到可执行文件: {command[0]}") from exc
    if proc.returncode != 0:
        raise ExtractError(f"命令失败（rc={proc.returncode}）: {command[0]}\n{proc.stderr.strip()}")
    return proc.stdout.strip()


def node_constants() -> tuple[str, dict[str, int], dict[str, int]]:
    payload = _run(["node", "-e", NODE_PROBE])
    data = json.loads(payload)
    return PINNED_RUNTIME_VERSIONS["node"], data["errno"], data["signals"]


def python_constants() -> tuple[str, dict[str, int], dict[str, int]]:
    """Python 视角的常量。

    **版本号取 ``PINNED_RUNTIME_VERSIONS``，不取 ``sys.executable`` 报的版本** ——
    否则 `py -3.8` 跑一次 `--check` 就会把 `program_version` 写成 3.8.8，
    与仓库里那份（3.12.10）对不上而误报"YAML 被手改"（见该常量的注释）。
    用哪条通道跑不影响**数值**（本机实测两份 `errno` 模块内容逐项相同），
    所以这里只钉版本字段，不禁止双通道运行。
    """
    data = json.loads(_run([sys.executable, "-c", PY_CONSTANTS_PROBE]))
    return PINNED_RUNTIME_VERSIONS["python"], data["errno"], data["signals"]


# ── 条目构造 ────────────────────────────────────────────────────────────────
@dataclass
class Entry:
    name: str
    domain: str
    value: int
    source: dict[str, object]
    description_zh: str
    posix_ref: str = "<none>"

    @property
    def sort_key(self) -> tuple[str, int, str]:
        return (self.domain, self.value, self.name)


def _file_source(header_id: str, line: int, refs: dict[str, str]) -> dict[str, object]:
    return {
        "kind": "file",
        "file": HEADER_PATHS[header_id],
        "line": line,
        "repo": HEADER_REPOS[header_id],
        "ref": refs[HEADER_REPOS[header_id]],
    }


def _runtime_source(runtime: str, version: str) -> dict[str, object]:
    return {
        "kind": "runtime",
        "runtime": runtime,
        "program_version": version,
        "verified_at": VERIFIED_AT,
    }


def load_refs() -> dict[str, str]:
    if not SOURCES_MANIFEST.is_file():
        raise ExtractError(
            f"缺少 {SOURCES_MANIFEST.name}（先跑 tools/fetch_sources.py --out _headers）"
        )
    payload = json.loads(SOURCES_MANIFEST.read_text(encoding="utf-8"))
    refs = payload.get("refs")
    if not isinstance(refs, dict) or not refs:
        raise ExtractError(f"{SOURCES_MANIFEST.name} 里没有 refs —— 无法给 source.ref 出处")
    return {str(key): str(value) for key, value in refs.items()}


def _header_comment(path: Path, line: int) -> str:
    """取该行右侧 ``/* ... */`` 注释（原文注释是释义的第一凭据）。"""
    try:
        text = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return ""
    if line > len(text):
        return ""
    match = re.search(r"/\*(.*?)\*/", text[line - 1])
    return match.group(1).strip() if match else ""


# ── 汇总 ────────────────────────────────────────────────────────────────────
#: 被排除项的记录形态 (name, domain, reason, line)。
#: **不用 ``Drop = tuple[str, ...]``**：模块级赋值在运行时求值，``tuple[str, ...]``
#: 是 3.9+ 才支持的下标，3.8 通道上直接 TypeError（本机实测：`py -3.8` 报
#: "'type' object is not subscriptable"）。函数签名里的注解有 ``from __future__ import
#: annotations`` 兜着不求值，但**普通赋值没有这层保护**。
Drop = Tuple[str, str, str, int]


def collect_all() -> tuple[dict[str, list[Entry]], dict[str, list[Drop]], dict[str, str]]:
    """返回 (平台 -> 条目, 平台 -> 被排除清单, 取数事实)。"""
    refs = load_refs()
    platforms: dict[str, list[Entry]] = {}
    excluded: dict[str, list[Drop]] = {}

    def scan_kind(domain: str, pattern: re.Pattern[str], header_map: dict[str, tuple[str, ...]]):
        for platform, header_ids in header_map.items():
            entries: list[Entry] = []
            drops: list[Drop] = []
            # 跨文件共享的宏表：同一平台的 errno 分两份头文件，别名可能跨文件（见 scan_header）
            symbols: dict[str, int] = {}
            for header_id in header_ids:
                path = HEADERS_DIR / f"{header_id}.h"
                scanned = scan_header(path, MACRO_ENV[platform], pattern, symbols)
                for definition in scanned.defined:
                    entries.append(
                        Entry(
                            name=definition.name,
                            domain=domain,
                            value=definition.value,
                            source=_file_source(header_id, definition.line, refs),
                            description_zh=gloss_for(
                                definition.name, _header_comment(path, definition.line)
                            ),
                        )
                    )
                drops.extend(
                    (item.name, domain, item.reason, item.line) for item in scanned.skipped
                )
            platforms.setdefault(platform, []).extend(entries)
            excluded.setdefault(platform, []).extend(drops)

    scan_kind("errno", ERRNO_NAME, ERRNO_HEADERS)
    scan_kind("signal", SIGNAL_NAME, SIGNAL_HEADERS)

    node_version, node_errno, node_signals = node_constants()
    py_version, py_errno, py_signals = python_constants()

    for platform, runtime, version, errno_map, signal_map in (
        ("win32-node", "node", node_version, node_errno, node_signals),
        ("win32-python", "python", py_version, py_errno, py_signals),
    ):
        entries = [
            Entry(
                name=name,
                domain="errno",
                value=int(value),
                source=_runtime_source(runtime, version),
                description_zh=gloss_for(name, ""),
            )
            for name, value in sorted(errno_map.items())
        ]
        entries += [
            Entry(
                name=name,
                domain="signal",
                value=int(value),
                source=_runtime_source(runtime, version),
                description_zh=gloss_for(name, ""),
            )
            for name, value in sorted(signal_map.items())
        ]
        platforms.setdefault(platform, []).extend(entries)
        excluded.setdefault(platform, [])

    facts = {"node": node_version, "python": py_version, **refs}
    return platforms, excluded, facts


# ── 渲染 ────────────────────────────────────────────────────────────────────
FILE_HEADERS = {
    "linux": """# 编目源 · 平台 `linux` · 由 tools/extract_catalog.py 生成，**不要手改**
#
# 纪律（plan/04 §2.1，装载期 fail-closed）：
#   · 每条必须有 `source`；`kind: file` 需要 file/line/repo/ref 四项齐备
#   · `source.file` 是**上游仓库内路径**（不是本地缓存路径）；`source.line` 是原文行号
#   · 无出处者不得入本文件 —— 记 data/gaps.md
#
# 底座：torvalds/linux
#   include/uapi/asm-generic/errno-base.h（errno 基础段 1–34）
#   include/uapi/asm-generic/errno.h（errno 扩展段 35+，含别名）
#   include/uapi/asm-generic/signal.h（信号编号 1–31）
#
# 预处理器口径：__KERNEL__ / __ASSEMBLY__ 未定义（用户态默认），只收该环境下可见的 #define。
# 被排除项（内核内部伪错误、非信号的 SIG_*、实时信号界）逐条记 data/gaps.md。
""",
    "macos": """# 编目源 · 平台 `macos` · 由 tools/extract_catalog.py 生成，**不要手改**
#
# 纪律同 data/catalog/linux.yaml 头注释（plan/04 §2.1）。
#
# 底座：apple-oss-distributions/xnu
#   bsd/sys/errno.h（用户态 errno；含别名与 ELAST 哨兵）
#   bsd/sys/signal.h（信号编号；从 7 号起与 Linux 分叉，见 data/README.md §1.2）
#
# 预处理器口径（这是"逐条"的关键）：__DARWIN_C_LEVEL = __DARWIN_C_FULL、
# __DARWIN_UNIX03 = 1、KERNEL/KERNEL_PRIVATE/_POSIX_C_SOURCE 均未定义 ——
# 用户态默认编译环境。该环境下不可见的分支（内核伪错误、非 UNIX03 的 EOPNOTSUPP=45、
# 只对 _POSIX_C_SOURCE 可见的 SIGPOLL）不入编目，逐条记 data/gaps.md。
#
# **`SIGSTKFLT` 不在本文件里**，这不是遗漏：macOS 没有这个信号。
# 查它时由 `PLATFORM-ABSENT` 承载（data/README.md §5.2），`data/gaps.md` 有专门一行。
""",
    "win32-node": """# 编目源 · 平台 `win32-node` · 由 tools/extract_catalog.py 生成，**不要手改**
#
# **Windows 有两个视角**（data/README.md §1.1，实测同机 EADDRINUSE: Node 100 / Python 10048）。
# 本文件只收 **Node 运行时** 的取值；Python 视角见 win32-python.yaml。
# 合并成一个 "windows" 在结构上就无法表达这个事实 —— 见 plan/02 D3。
#
# 底座：本机 `require('os').constants.errno` + `require('os').constants.signals` 实读
# 出处形态：kind: runtime（无头文件行号，改用 runtime + program_version + verified_at）
#
# 值域含两类名字：POSIX 风格 `E*` 与 Winsock 风格 `WSA*`。两者是**不同的常量**，
# 同一数值上并存时判定为 AMBIGUOUS-SAME-PLATFORM —— 这是结果，不是缺陷。
#
# 信号只有 11 项（Windows 平台不完整），缺口记 data/gaps.md。
""",
    "win32-python": """# 编目源 · 平台 `win32-python` · 由 tools/extract_catalog.py 生成，**不要手改**
#
# **Windows 有两个视角**（data/README.md §1.1）：本文件收 **Python 运行时** 的取值。
# 与 win32-node.yaml 的数值**不同**，这是本题最硬的事实之一。
#
# 底座：本机 `import errno` + `import signal` 实读
# 出处形态：kind: runtime（runtime + program_version + verified_at）
#
# 注意：Python 的 errno 模块同时导出 `EADDRINUSE=10048` 与 `WSAEADDRINUSE=10048`，
# 于是该值在这里是 AMBIGUOUS-SAME-PLATFORM；而 Node 视角下 100 只有 `EADDRINUSE` 一个名字
# —— 同一台机器、同一个端口错误，两个运行时的数值与名字结构都不同。
""",
}


def _yaml_scalar(value: object) -> str:
    """字符串一律用 JSON 双引号形态（合法 YAML 双引号标量），避免中文与冒号歧义。"""
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def render_yaml(platform: str, entries: list[Entry]) -> str:
    lines = [FILE_HEADERS[platform].rstrip("\n") + "\n"]
    if not entries:
        lines.append("[]\n")
        return "".join(lines)
    for entry in sorted(entries, key=lambda item: item.sort_key):
        lines.append(f"- name: {_yaml_scalar(entry.name)}\n")
        lines.append(f"  domain: {_yaml_scalar(entry.domain)}\n")
        lines.append(f"  value: {entry.value}\n")
        lines.append("  source:\n")
        for key, value in entry.source.items():
            lines.append(f"    {key}: {_yaml_scalar(value)}\n")
        lines.append(f"  description_zh: {_yaml_scalar(entry.description_zh)}\n")
        lines.append(f"  posix_ref: {_yaml_scalar(entry.posix_ref)}\n")
    return "".join(lines)


def _report(
    platforms: dict[str, list[Entry]],
    excluded: dict[str, list[Drop]],
    facts: dict[str, str],
) -> str:
    out: list[str] = ["取数事实", "=" * 68]
    for key, value in facts.items():
        out.append(f"  {key}: {value}")
    out.append("")
    out.append("逐平台条目数")
    out.append("-" * 68)
    for platform in sorted(platforms):
        counts: dict[str, int] = {}
        for entry in platforms[platform]:
            counts[entry.domain] = counts.get(entry.domain, 0) + 1
        out.append(f"  {platform:<14} {counts}  合计 {len(platforms[platform])}")
    out.append("")
    out.append("被排除的定义（逐条写进 data/gaps.md）")
    out.append("-" * 68)
    for platform in sorted(excluded):
        if not excluded[platform]:
            continue
        out.append(f"  [{platform}]")
        for name, domain, reason, line in sorted(excluded[platform], key=lambda x: (x[1], x[3])):
            out.append(f"    {name:<18} {domain:<7} 行 {line:>4}  {reason}")
    return "\n".join(out) + "\n"


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="extract_catalog", description=__doc__)
    parser.add_argument("--out", help=f"写出 data/catalog/*.yaml（默认 {DEFAULT_OUT}）")
    parser.add_argument("--check", action="store_true", help="与仓库里的 YAML 逐字节比对")
    parser.add_argument("--report", action="store_true", help="打印取数事实与被排除项")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not (args.out or args.check or args.report):
        parser.print_usage()
        sys.stderr.write("extract_catalog: 必须给 --out / --check / --report 之一\n")
        return 2

    try:
        platforms, excluded, facts = collect_all()
    except ExtractError as exc:
        sys.stderr.write(f"extract_catalog: {exc}\n")
        return 3

    rendered = {platform: render_yaml(platform, entries) for platform, entries in platforms.items()}

    if args.report:
        sys.stdout.write(_report(platforms, excluded, facts))

    if args.check:
        problems: list[str] = []
        for platform, body in sorted(rendered.items()):
            target = DEFAULT_OUT / f"{platform}.yaml"
            if not target.is_file():
                problems.append(f"{target.name}: 文件缺失")
                continue
            actual = target.read_text(encoding="utf-8").replace("\r\n", "\n")
            if actual != body:
                problems.append(f"{target.name}: 与抽取结果不一致（重新抽取过或手改过）")
        if problems:
            for line in problems:
                sys.stderr.write(f"extract_catalog: {line}\n")
            return 1
        total = sum(len(items) for items in platforms.values())
        sys.stderr.write(f"extract_catalog: 一致（{len(rendered)} 个平台文件 / {total} 条）\n")

    if args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        for platform, body in sorted(rendered.items()):
            (out_dir / f"{platform}.yaml").write_bytes(body.encode("utf-8"))
        total = sum(len(items) for items in platforms.values())
        sys.stderr.write(f"extract_catalog: 写出 {out_dir.name}/ 的 {len(rendered)} 个文件（{total} 条）\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""模块③ 退出码归因。

判定顺序写死在 :func:`attribute` 的分支里，与 plan/03 §3.2 的表逐行对应。

两条硬纪律（plan/01 §二 模块③）：
1. ``exit 1`` → ``UNATTRIBUTABLE``，不得强行解释成任何具体错误。
2. ``128+n`` 必须**同时**验 ``n`` 是该平台的有效信号编号；否则一律 ``UNATTRIBUTABLE``。
   ``n`` 的有效性只能来自编目（``catalog.signal_numbers``）—— 代码里不许写死信号表。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import contract
from .catalog import Catalog

#: sysexits 的 64–78 段是**约定而非标准**（plan/04 §2.3）。名字只用于报告，
#: 它的码值判定不依赖这张表（判定只看到区间），所以这张表不属于"编目数值"。
SYSEXITS_NAMES: dict[int, str] = {
    64: "EX_USAGE",
    65: "EX_DATAERR",
    66: "EX_NOINPUT",
    67: "EX_NOUSER",
    68: "EX_NOHOST",
    69: "EX_UNAVAILABLE",
    70: "EX_SOFTWARE",
    71: "EX_OSERR",
    72: "EX_OSFILE",
    73: "EX_CANTCREAT",
    74: "EX_IOERR",
    75: "EX_TEMPFAIL",
    76: "EX_PROTOCOL",
    77: "EX_NOPERM",
    78: "EX_CONFIG",
}

SYSEXITS_MIN = min(SYSEXITS_NAMES)
SYSEXITS_MAX = max(SYSEXITS_NAMES)

#: ``128+n`` 的上界来源是 8 位退出码；``n`` 的上界由编目决定，不在这里。
EXIT_CODE_MAX = 255
#: Windows 巨型退出码的截断解释边界（32 位无符号）。
UINT32_MAX = 0xFFFFFFFF


@dataclass(frozen=True)
class Attribution:
    """归因结果 —— 结果对象级真值，``expected.json`` 存它的字段。"""

    attribution: str
    code: int
    platform: str
    signal: int | None = None
    signal_name: str | None = None
    sysexits_name: str | None = None
    truncated: bool = False
    notes: tuple[str, ...] = ()
    sources: tuple[str, ...] = field(default_factory=tuple)

    @property
    def exit_code(self) -> int:
        return contract.exit_code_for_attribution(self.attribution)

    def as_dict(self) -> dict[str, Any]:
        return {
            "attribution": self.attribution,
            "code": self.code,
            "platform": self.platform,
            "signal": self.signal,
            "signal_name": self.signal_name,
            "sysexits_name": self.sysexits_name,
            "truncated": self.truncated,
            "notes": list(self.notes),
            "sources": list(self.sources),
        }


def _unattributable(code: int, platform: str, note: str, truncated: bool = False) -> Attribution:
    return Attribution(
        attribution=contract.UNATTRIBUTABLE,
        code=code,
        platform=platform,
        truncated=truncated,
        notes=(note,),
    )


def attribute(code: int, platform: str, catalog: Catalog) -> Attribution:
    """判定顺序见 plan/03 §3.2 —— 与那张六行表逐行对应，**不许重排**。"""
    original = code
    truncated = False

    # 序 1（前半）：高于 32 位的巨型码先按截断解释，并显式声明不可唯一归因。
    # 1.5) Windows 巨型退出码（plan/03 §3.4）。
    if code >> 32:
        code = code & UINT32_MAX
        truncated = True
    if code > EXIT_CODE_MAX:
        return _unattributable(
            original,
            platform,
            f"退出码 {original} 超出 8 位退出码可表达范围"
            + (f"（已按 32 位截断解释为 {code}）" if truncated else "")
            + "；原值不可唯一归因",
            truncated=truncated,
        )

    if code < 0:
        return _unattributable(original, platform, f"退出码 {original} 为负，不是合法的进程退出码")

    # 序 2：遗憾地排在 NORMAL-EXIT 之前 —— 约定段优先于惯例段（plan/03 §3.2）。
    if SYSEXITS_MIN <= code <= SYSEXITS_MAX:
        return Attribution(
            attribution=contract.SYSEXITS,
            code=code,
            platform=platform,
            sysexits_name=SYSEXITS_NAMES[code],
            truncated=truncated,
            notes=(
                "sysexits 64–78 段是约定非标准（即约定而非标准），各实现可自行约定",
                "本判定只说明该码落在约定段内，不说明程序真的用了这套约定",
            ),
        )

    # 序 3：0 = 成功
    if code == 0:
        return Attribution(
            attribution=contract.NORMAL_EXIT,
            code=0,
            platform=platform,
            truncated=truncated,
            notes=("退出码 0 = 成功",),
        )

    # 序 4：128+n —— 必须验 n 在该平台确实是有效信号
    if code > 128:
        signal_number = code - 128
        signals = catalog.signal_numbers(platform)
        if signal_number in signals:
            entry = _signal_entry(catalog, platform, signal_number)
            return Attribution(
                attribution=contract.SIGNAL_KILLED,
                code=code,
                platform=platform,
                signal=signal_number,
                signal_name=entry.name if entry else None,
                truncated=truncated,
                notes=(
                    "128+n 归因是 POSIX 惯例非标准（即惯例而非标准）",
                    f"n={signal_number} 已核对：在 {platform} 上是有效信号"
                    + (f"（{entry.name}）" if entry else ""),
                ),
                sources=(entry.source_label,) if entry else (),
            )
        # n 不在该平台信号表内 —— 128+n 不成立
        return _unattributable(
            original,
            platform,
            f"退出码 {original} 落在 128+n 区间，但 n={signal_number} 在 {platform} 上不是有效信号；"
            "128+n 是惯例非标准（即惯例而非标准），此处不成立，不可唯一归因"
            + ("（原值已按 32 位截断）" if truncated else ""),
            truncated=truncated,
        )

    # 序 5：1–127 且不属于 64–78
    if code == 1:
        return Attribution(
            attribution=contract.UNATTRIBUTABLE,
            code=1,
            platform=platform,
            truncated=truncated,
            notes=(
                "退出码 1 是通用失败，无特定语义；任何具体解释都是猜测",
                "不可唯一归因是正确结论，不代表工具失效",
            ),
        )
    if 1 <= code < 128:
        return Attribution(
            attribution=contract.NORMAL_EXIT,
            code=code,
            platform=platform,
            truncated=truncated,
            notes=(
                f"退出码 {code} 在 1–127 内且不属于 sysexits 约定段；"
                "程序自定义语义，不可唯一归因到某个系统错误",
            ),
        )

    # 序 6：其余（含 128 本身）
    return _unattributable(
        original,
        platform,
        f"退出码 {original} 无法按 128+n 或 sysexits 归因",
        truncated=truncated,
    )


def _signal_entry(catalog: Catalog, platform: str, number: int):
    for name in catalog.names_at(platform, "signal", number):
        entry = catalog.entry_for(platform, "signal", name)
        if entry is not None:
            return entry
    return None
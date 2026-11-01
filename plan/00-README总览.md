# 00 · 项目总览 — 11-1-errcode-atlas

## 1. 文档索引

| 编号 | 文档 | 状态 |
|---|---|---|
| 00 | `plan/00-README总览.md` | ✅ |
| 01 | `plan/01-题目文档.md` | ✅ 定稿 v1 |
| 02 | `plan/02-架构与技术选型.md` | ⬜ 待 M1 |
| 03 | `plan/03-模块详设.md` | ⬜ 待 M1 |
| 04 | `plan/04-数据计划.md` | ⬜ 待 M1 |
| 05 | `plan/05-里程碑与发布.md` | ⬜ 待 M1（M6 DoD 已在本文件 §4 预写死） |
| 06 | `plan/06-交付对标与决策.md` | ⬜ 待 M1 |
| — | `data/README.md` | ✅ 依据查证 + 口径唯一定义 |
| — | `data/gaps.md` | ⬜ 待 M1（未入编目项登记） |

## 2. 决策记录

| 日期 | 决策 | 结论与理由 |
|---|---|---|
| 2026-11-01 | 交付形态收敛为 **CLI + Agent Skill**（双形态） | 两形态各有四格验收（见 §5）。不设 GUI、不设 MCP。 |
| 2026-11-01 | 域范围锁死 **POSIX errno + 信号 + 进程退出码 × 三平台** | SQLite/HTTP/gRPC 各有独立编目面，首期全做等于四个项目。**明确降级为扩展项**。 |
| 2026-11-01 | **`AMBIGUOUS` 与 `UNATTRIBUTABLE` 作为一等公民** | 本题最大风险是"看起来答得很像"——强行归因比不答更有害。`exit 1` 必须判不可归因。 |
| 2026-11-01 | 每条数值**必须带出处行号**，无出处不入编目 | 踩 preflight「引用纪律」：无出处不得用确定语气。`data/gaps.md` 承接未入编目项。 |
| 2026-11-01 | 编目**随包分发**，运行时零联网 | 踩 preflight ②：底座必须可获取。三平台头文件已实测可直读（见台账）。 |
| 2026-11-01 | 放弃方向：错误码**全文检索/问答** | `context7` 64033★、`notebooklm-mcp` 3443★ 已占；且问答形态必然被模型编造污染。 |
| 2026-11-01 | 放弃方向：stack trace 归因 | 检索最高 1★，但形态是"猜 bug 成因"，不可确定性判定（违反零模型可跑）。 |
| 2026-11-01 | 放弃方向：跨方言 cron | 太窄；虽 `cron dialect difference`=0，但撑不起独立一题。 |
| 2026-11-01 | 放弃方向：GitHub Actions 未知 key | `actionlint` 4370★ 已占。 |
| 2026-11-01 | 放弃方向：包发布合规 lint | `publint` 1310★ + `arethetypeswrong` 1613★ 已占（且属包作者视角）。 |

## 3. 承诺-证据台账（全项目唯一一份）

| 承诺项 | 素材来源 | 交付物内可达性 | 核验方式 | 状态 |
|---|---|---|---|---|
| Linux errno 数值 | `errno-base.h` / `errno.h` 原文 | ✅ 编目入包 | `bench` 逐值对照 | ⬜ 待 M1 |
| macOS errno 数值 | xnu `errno.h` 原文（119 条） | ✅ 编目入包 | 同上 | ⬜ 待 M1 |
| Windows errno 数值（Node 视角） | 本机 `os.constants.errno`（134 项） | ✅ 编目入包 | 同上 | ⬜ 待 M1 |
| Windows errno 数值（Python 视角） | 本机 `errno`（88 项） | ✅ 编目入包 | 同上 | ⬜ 待 M1 |
| Linux / macOS 信号编号 | 两份 `signal.h` 原文 | ✅ 编目入包 | `bench` 分叉点断言 | ⬜ 待 M1 |
| Node 错误码清单 | `nodejs.org/api/errors.html` | ✅ 编目入包 | `bench` 抽样 | ⬜ 待 M2 |
| `sysexits` 64–78 | `man.openbsd.org/sysexits` | ✅ 编目入包 | `bench` | ⬜ 待 M2 |
| `128+n` 归因 | POSIX 惯例（**非标准**，须标注） | ✅ 内置规则 | `selftest` 断言含 `n` 有效性检查 | ⬜ 待 M3 |
| 五判定态 | `data/README.md` §5 | ✅ | `bench` 全态覆盖 | ⬜ 待 M3 |
| Skill 契约块双向一致 | `SKILL.md` ↔ `src` | ✅ | `tests/test_contract.py` | ⬜ 待 M5 |
| 裸 clone 可复现 | README 步骤 | ✅ | 手工 + CI | ⬜ 待 M6 |

> **本台账状态列必须与里程碑同一次提交里一起翻转。** 其他文档只可引用，不得复制。

## 4. 里程碑初稿

| 里程碑 | 内容 | DoD |
|---|---|---|
| **M1 数据先行** | 三平台头文件逐条抽取入编目、出处行号登记、`data/gaps.md` 建表 | 编目每条**带出处**；`build` 可复现；`data/README.md` §5 口径定稿 |
| **M2 解析** | Node 错误码抽取、sysexits 入编目、编目→查询索引 | 抽样对账一致；`UNKNOWN` 路径可复现 |
| **M3 判定** | 五判定态 + 退出码归因 | `bench` 全绿，含 `exit 1`→`UNATTRIBUTABLE` 断言 |
| **M4 基准** | 植入真值语料（含跨平台分叉点全覆盖）+ 不可归因集 | `selftest`/`bench` 可跑，退出码语义断言通过 |
| **M5 交付** | CLI + `SKILL.md` + 技术报告 + demo GIF | 四格表全绿；`docs/技术报告.md`、`docs/demo/demo.gif` 存在 |
| **M6 发布** | 公开发布 | **①git tag ②GitHub Release（附产物：≥1 个手工上传附件，本地留副本 + sha256）③`plan/RELEASE-M6.md`（tag 前落盘，tag 后事实分栏追加）**；`check_release.py` 无 FAIL |

> **DoD 口径二选一，本仓选 A：Release 附产物。** 自 M1 起**不得删改或降级**。

## 5. 逐形态验收四格表

| 形态 | 主入口 | 主命令/控件 | 接到哪个业务函数 | 断言在哪条测试 | 产物在哪个附件 |
|---|---|---|---|---|---|
| CLI | `pyproject.toml` `[project.scripts]` | `errcode-atlas explain 98 --platform linux` | `atlas.explain()` | `tests/test_cli_exitcode.py` | Release 附件 `errcode-atlas-<ver>.zip` |
| Agent Skill | `SKILL.md` | 契约块声明的五判定态 + 退出码 | `src/errcode_atlas/api.py::run()` | `tests/test_contract.py`（双向断言） | 同上 |

## 6. 招牌动词表

| 能力名词 | 哪条交付态命令产出它 | 哪条基准/测试断言它 |
|---|---|---|
| `UNAMBIGUOUS` | `explain` 的 `verdict` | `bench` 唯一值集 |
| `AMBIGUOUS-SAME-PLATFORM` | 同上 | `bench`（Linux `SIGABRT`/`SIGIOT`=6） |
| `AMBIGUOUS-CROSS-PLATFORM` | 同上 | `bench`（`EAGAIN` 11/35/11） |
| `PLATFORM-ABSENT` | 同上 | `bench`（macOS 无 `SIGSTKFLT`） |
| `UNKNOWN` | 同上 | `bench` 越界值集 |
| `SIGNAL-KILLED(n)` | `exitcode` 的 `attribution` | `bench`（137→SIGKILL） |
| `SYSEXITS(n)` | 同上 | `bench`（64–78） |
| `UNATTRIBUTABLE` | 同上 | `bench`（`exit 1`） |

## 7. 提交材料实物表

| 承诺项 | 应存在的文件路径 | 由哪个里程碑产出 | 用哪条命令核对 |
|---|---|---|---|
| 题目文档 | `plan/01-题目文档.md` | M0 | `git ls-files` |
| 架构选型 | `plan/02-架构与技术选型.md` | M1 | `git ls-files` |
| 模块详设 | `plan/03-模块详设.md` | M1 | `git ls-files` |
| 数据计划 | `plan/04-数据计划.md` | M1 | `git ls-files` |
| 三平台编目源 | `data/catalog/{linux,macos,windows}.yaml` | M1 | `git ls-files data/catalog/` |
| 缺口登记 | `data/gaps.md` | M1 | `git ls-files data/gaps.md` |
| 基准语料 | `fixtures/*/INPUT.md` + `expected.json` | M2 | `git ls-files fixtures/` |
| 自测与基准 | `tests/` + `selftest`/`bench` | M3/M4 | `pytest && errcode-atlas bench` |
| Agent Skill | `SKILL.md` | M5 | `git ls-files SKILL.md` |
| 技术报告 | `docs/技术报告.md` | M5 | `git ls-files docs/` |
| 演示产物 | `docs/demo/demo.gif` | M5 | `git ls-files docs/demo/` |
| 发布留档 | `plan/RELEASE-M6.md` | M6 | `git cat-file -e <tag>:plan/RELEASE-M6.md` |
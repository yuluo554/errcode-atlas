# 00 · 项目总览 — 11-1-errcode-atlas

> 方法论：`ai-tool-project-sprint` ｜ 布局门：`py -3.12 tools/check_sprint_layout.py` ｜ 装订日期：2026-11-01

**新对话第一件事 = 跑上面那条布局门**，红了先修布局再干活（详见 `AGENTS.md`）。

## 1. 文档索引

| 编号 | 文档 | 状态 |
|---|---|---|
| 00 | `plan/00-README总览.md` | ✅ |
| 01 | `plan/01-题目文档.md` | ✅ 定稿 v1 |
| 02 | `plan/02-架构与技术选型.md` | ✅ M0 落盘（D1–D8 决策已定） |
| 03 | `plan/03-模块详设.md` | ✅ M0 落盘（判定顺序与出口已写死） |
| 04 | `plan/04-数据计划.md` | ✅ M0 落盘（真值纪律 + 摘要口径已定） |
| 05 | `plan/05-里程碑与发布.md` | ✅ M0 落盘（M0–M6 DoD + 已知未验证项 U1–U6） |
| 06 | `plan/06-交付对标与决策.md` | ✅ M0 落盘（评分对标 + 风险 R1–R9 + 缺口 G1–G5） |
| — | `data/README.md` | ✅ 依据查证 + 口径唯一定义 |
| — | `data/gaps.md` | ✅ M0 建表（逐行可查三态） |

## 2. 决策记录

### 2.1 已定决策

| 日期 | 决策 | 结论与理由 |
|---|---|---|
| 2026-11-01 | 交付形态收敛为 **CLI + Agent Skill**（双形态） | 两形态各有四格验收（见 §5）。不设 GUI、不设 MCP。 |
| 2026-11-01 | 域范围锁死 **POSIX errno + 信号 + 进程退出码 × 三平台** | SQLite/HTTP/gRPC 各有独立编目面，首期全做等于四个项目。**明确降级为扩展项**。 |
| 2026-11-01 | **`AMBIGUOUS` 与 `UNATTRIBUTABLE` 作为一等公民** | 本题最大风险是"看起来答得很像"——强行归因比不答更有害。`exit 1` 必须判不可归因。 |
| 2026-11-01 | 每条数值**必须带出处行号**，无出处不入编目 | 踩 preflight「引用纪律」：无出处不得用确定语气。`data/gaps.md` 承接未入编目项。 |
| 2026-11-01 | 编目**随包分发**，运行时零联网 | 踩 preflight ②：底座必须可获取。三平台头文件已实测可直读（见台账）。 |
| 2026-11-01 | **区分 Windows 的 Node 视角与 Python 视角** | 实测同机 `EADDRINUSE` Node=100 / Python=10048；只写一个 "windows" 值是错的。 |

### 2.2 未采用方向（弃选项与理由）

| 未采用 | 理由 |
|---|---|
| 错误码**全文检索/问答** | `context7` 64033★、`notebooklm-mcp` 3443★ 已占；且问答形态必然被模型编造污染。 |
| stack trace 归因 | 检索最高 1★，但形态是"猜 bug 成因"，不可确定性判定（违反零模型可跑）。 |
| 跨方言 cron | 太窄；虽 `cron dialect difference`=0，但撑不起独立一题。 |
| GitHub Actions 未知 key | `actionlint` 4370★ 已占。 |
| 包发布合规 lint | `publint` 1310★ + `arethetypeswrong` 1613★ 已占（且属包作者视角）。 |
| SQLite 结果码 / HTTP 状态码 / gRPC 状态码 | 各自独立编目面，首期做四个等于四个项目；**降级为扩展项**。 |
| HTTP 状态码 | 已有 IANA 官方 CSV 可直连，但"编目"本身无判定难度，**降级为扩展项**。 |
| 依赖调用面对账（同批另一题方向） | 已独立成 **`11-1-depcheck-live`**，本案不重复覆盖，两仓文档互不提及。 |

## 3. 承诺-证据台账（全项目唯一一份）

| 承诺项 | 素材来源 | 交付物内可达性 | 核验方式 | 状态 |
|---|---|---|---|---|
| Linux errno 数值 | `errno-base.h` / `errno.h` 原文 | ✅ 编目入包 | `bench` 逐值对照 | ✅ M1（136 条，逐条带行号） |
| macOS errno 数值 | xnu `errno.h` 原文（119 条） | ✅ 编目入包 | 同上 | ✅ M1（用户态 109 条） |
| Windows errno 数值（Node 视角） | 本机 `os.constants.errno`（134 项） | ✅ 编目入包 | 同上 | ✅ M1（`kind: runtime`） |
| Windows errno 数值（Python 视角） | 本机 `errno`（136 项） | ✅ 编目入包 | 同上 | ✅ M1（`kind: runtime`） |
| Linux / macOS 信号编号 | 两份 `signal.h` 原文 | ✅ 编目入包 | `bench` 分叉点断言 | ✅ M1（34 + 32 条，五叉点已钉） |
| Node 错误码清单 | `nodejs.org/api/errors.html` | ✅ 编目入包 | `bench` 抽样 | ✅ M2（`node` 域 435 条 = 现行 383 + 弃用 52，`kind: doc`） |
| `sysexits` 64–78 | `man.openbsd.org/sysexits` | ✅ 编目入包 | `bench` | ✅ M2（`exit` 域 15 条，`kind: doc`，四轴共享） |
| `128+n` 归因 | POSIX 惯例（**非标准**，须标注） | ✅ 内置规则 | `selftest` 断言含 `n` 有效性检查 | ✅ M3（`selftest._check_signal_validity` + 语料 `e-exit-137-win32-python-invalid-n`） |
| 五判定态 | `data/README.md` §5 | ✅ | `bench` 全态覆盖 | ✅ M3（`selftest` 五态可达 + `bench` 59 case 比对结果对象） |
| Skill 契约块双向一致 | `SKILL.md` ↔ `src` | ✅ | `tests/test_contract.py` | ⬜ 待 M5 |
| 裸 clone 可复现 | README 步骤 | ✅ | 手工 + CI | ⬜ 待 M6 |

> **本台账状态列必须与里程碑同一次提交里一起翻转。** 其他文档只可引用，不得复制。

## 4. 里程碑初稿

> 本表与 `plan/05` §1 状态表是**两处机读副本**，必须逐行一致（布局门 `LAYOUT.STATUS` 逐副本采集）。
> `README.md` **刻意不承载状态**（随包读者手里没有 `plan/`），见 `AGENTS.md` §二。

| 里程碑 | 内容 | DoD | 状态 |
|---|---|---|---|
| M0 | 计划套件 + 方法论装订（`AGENTS.md` + 两道门）+ 骨架（契约表 / 空壳 CLI / 冻结面校验） | 两道门可跑且逐组变异变红；`--version`/`--help` 可用；未知子命令 exit 4 | ✅ |
| M1 | 数据先行 | 三平台头文件逐条抽取入编目、出处行号登记、`data/gaps.md` 建表 | 编目每条**带出处**；`build --check` 可复现；`data/README.md` §5 口径定稿 | ✅ |
| M2 | 解析 | Node 错误码抽取、sysexits 入编目、编目→查询索引 | 抽样对账一致；`UNKNOWN` 路径可复现 | ✅ |
| M3 | 判定 | 五判定态 + 退出码归因 | `bench` 全绿，含 `exit 1`→`UNATTRIBUTABLE` 断言 | ✅ |
| M4 | 基准 | 植入真值语料（含跨平台分叉点全覆盖）+ 不可归因集 | `selftest`/`bench` 可跑，退出码语义断言通过 | ⬜ |
| M5 | 交付 | CLI + `SKILL.md` + 技术报告 + demo GIF | 四格表全绿；`docs/技术报告.md`、`docs/demo/demo.gif` 存在 | ⬜ |
| M6 | 发布 | 公开发布 | **①git tag ②GitHub Release（附产物：≥1 个手工上传附件，本地留副本 + sha256）③`plan/RELEASE-M6.md`（tag 前落盘，tag 后事实分栏追加）**；`check_release.py` 无 FAIL | ⬜ |

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
| `AMBIGUOUS-CROSS-PLATFORM` | 同上 | `bench`（**数字** `11` 跨平台 → Linux `EAGAIN`/`EWOULDBLOCK`、macOS `EDEADLK`） |
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
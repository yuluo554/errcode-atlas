# HANDOFF-M0 · 计划套件 + 方法论装订 + 骨架

> 本棒：M0（已完成）。下一棒：M1 数据先行。
> 库内一律相对路径；本机绝对路径只出现在用户侧启动命令里。

---

## 一、当前进度 + 证据

| 项 | 证据（命令 / 文件） |
|---|---|
| 计划套件七份齐备 | `plan/00`–`plan/06` + `data/README.md` + `data/gaps.md` |
| 方法论装订三件 | `AGENTS.md` 存在；`plan/00` 顶部有装订行（三锚点同现）；`tools/check_sprint_layout.py` 可跑 |
| 布局门可跑且逐组变红 | `py -3.12 tools/verify_gates.py` → **17 组全 CAUGHT**（含 2 组阴性对照） |
| 脱敏门可跑且四条规则逐组变红 | 同上（D1–D4 四条规则 + D5 占位符放行对照） |
| 契约表落地 | `src/errcode_atlas/contract.py`：五态 / 四归因 / 四平台 / 三域 / 退出码 / 三强度 / 三出处类型 |
| CLI 骨架可跑 | `--version` → 0；未知子命令 → **4**（不是 argparse 的 2）；`--platform win32` → 4 并提示两个视角 |
| 冻结面校验可跑 | `py -3.12 tools/build_catalog.py --check` → 0（读 4 个源文件 / 0 条条目） |
| 契约双向断言 | `tests/test_contract.py`（文档 §5 三张表 ↔ `contract.py`，集合相等双向 + 解析器 0 行自证） |
| 判定/归因/报告三层测试 | `test_explain.py` / `test_exitcode.py` / `test_report.py`（含 AST 守门的"零判定"） |
| 全量测试双通道 | `py -3.12` 全绿；`py -3.8` 全绿 + **1 个显式 skip**（`sys.stdlib_module_names` 是 3.10+，见 §五） |
| README 命令反射 | `tests/test_readme_commands.py`：两种入口形态 + 五个子命令都逐条 `parse_args` 过 |
| `.gitignore` ↔ 脱敏门对齐 | `tests/test_gate_alignment.py`：目录级忽略逐项对齐，双向断言 |
| CI 工作流落盘 | `.github/workflows/ci.yml`（**本地等价校验，未接远端，CI 待首推验证**） |

**本轮门自己抓到的真缺陷（不是"写完就绿"）**：

| # | 形态 | 是谁抓出来的 |
|---|---|---|
| ① | 缺口列按**位置**取列（`len(cells)-2`）而非按表头名 → 缺口格写 `M0` 门仍绿 | 变异验证 L7（首版靶子还瞄错了列，一并改正） |
| ② | 盘符路径规则限定顶层目录名 → 盘符 + 任意目录的真泄露永远抓不到；放宽后又把含 `<…>` 占位符的脱敏写法判红 | 变异验证 D1 + D5（正解 = 命中后紧跟占位符才放行） |
| ③ | `selftest` 的期望值用 `contract.EXIT_*` 常量写 → 把常量改错时"实测 == 期望"一起错，判据恒绿 | 测试 `test_selftest_catches_broken_exit_code_mapping` |
| ④ | `bench` 把"有 case 但一个没跑成"与"跑过全过"都报 0 | 测试 `test_bench_with_case_missing_expected_reports_which_file` |
| ⑤ | `.gitignore` 的目录级忽略与脱敏门 `SKIP_DIRS` 长期不同步（22 项） | 新增 `tests/test_gate_alignment.py` |
| ⑥ | CI 冒烟步让 `explain 99999`（正确退出码 **3**）裸跑在 `set -e` 下 → "红得没有断言输出" | 本地逐步模拟 CI 时发现，改成显式断言 |

---

## 二、当前事实·状态不变量（下一棒动手前必须知道）

1. **编目源是唯一真相源**：`data/catalog/*.yaml` 可编辑；`src/errcode_atlas/data/catalog.json` 是**派生物**，
   不要手改 —— 改它会让 `build_catalog.py --check` 与运行期摘要校验**同时红**。
   正确动作 = 改 YAML → 跑 `--out` 重新生成 → 跑 `--check` 复核。
2. **四个平台值已冻结**：`linux` / `macos` / `win32-node` / `win32-python`。
   `--platform win32` 是**用法错误**（exit 4），故意不兼容 —— 不要"顺手"加回别名
   （那会把 Node 100 / Python 10048 的差异重新掩盖掉）。
3. **退出码 `1` 与 `3` 是两个语义，不得合并**：`1` = 有答案但不可唯一归因；`3` = 算不了。
   映射**只在** `src/errcode_atlas/cli.py::_exit_code_for` 一族（即 `contract.exit_code_for_*`）里发生。
4. **五判定态封闭**：`contract.VERDICTS` 恰好 5 个，不许加第六态。
   `tests/test_contract.py` 会同时断言"文档 = 代码"，加一个值三处一起红。
5. **M0 的编目是空的是合法初始态**（`entry_count` 全 0，`--check` 有空跑自证）。
   `explain` 返回 `UNKNOWN`（exit 3）在 M1 之前是**正确行为**，不是 bug。
6. **状态副本只有 2 张表**：`plan/00` 里程碑表 + `plan/05` §1 状态表。
   `README.md` **刻意不承载状态**（随包读者没有 `plan/`）。别"好心"往 README 加状态表格 ——
   布局门的 `STATUS_COPIES` 只有 2 项，加进去它贡献 0 行、还会让副本数看起来不对。
7. **`PENDING_TOOLS` 登记了两个还没到里程碑的脚本**：`tools/fetch_sources.py`(M1)、
   `tools/check_release.py`(M6)。**落位那个脚本的那一棒必须同笔删掉登记项**，否则门变红（stale 分支）。
   别把"还没到"写成"不做"（`EXEMPT_TOOLS` 是空的，且应该一直是空的）。
8. **`.gitattributes` 的 `* text=auto eol=lf` 是摘要口径的前提**：编目摘要按行尾归一后计算，
   删掉它会让从 `git archive` 导出树构建的包在用户侧 exit 3，而开发机永远绿。

---

## 三、下一棒待办（M1 数据先行）

1. 写 `tools/fetch_sources.py`（从 `gh api repos/<o>/<r>/contents/<path>` 取原文；
   **不要用 raw.githubusercontent.com，本机实测不可达**），并在同笔提交里**删掉 `PENDING_TOOLS` 的登记项**。
2. 逐条抽取 `data/catalog/linux.yaml`（errno 基础段 + 扩展段 + 信号）。
3. 逐条抽取 `data/catalog/macos.yaml`（errno 119 条 + 信号）；**`SIGSTKFLT` 不入编目**，留空即是 `PLATFORM-ABSENT` 的证据。
4. 两个运行时视角文件：`win32-node.yaml`、`win32-python.yaml`，用 `kind: runtime` + `program_version` + `verified_at`。
5. 每 20~30 条跑一次 `build_catalog.py --out` + `--check`，避免一次性堆到出错难定位。
6. `data/gaps.md` 逐行落实（三态：全录／部分录／未录），关闭项**只描述不点名文件名**。
7. `data/README.md` §1.3 的 X3（`128+n` 原典）核对后据实翻转或降级为 `gray`，并同步 `plan/06` G3。
8. 收尾：DoD 验证 → `plan/00`/`plan/05`/`plan/06` 状态回写 → 写 `plan/HANDOFF-M1.md` → commit。

---

## 四、既定口径清单（K 编号 —— 动了会打挂测试的约定）

| K | 口径 | 动了会红的东西 |
|---|---|---|
| K1 | 退出码映射只在 `contract.exit_code_for_verdict` / `exit_code_for_attribution` 两处 | `selftest._check_exit_codes`、`tests/test_cli_exitcode.py` |
| K2 | 判定层（`explain.py` / `exitcode.py`）不读时钟、不读环境变量、不联网 | `selftest._check_determinism` |
| K3 | `report.py` **零判定**：不得出现 `if verdict ==` 形态的分派 | `tests/test_report.py` 的 AST 守门 |
| K4 | 编目摘要按行尾归一后计算 | `tests/test_catalog_build.py`（LF/CRLF 摘要相等 + 改内容必变） |
| K5 | `source.kind` 三选一，各 kind 必填字段见 `contract.SOURCE_REQUIRED_FIELDS` | `catalog._validate_source`（fail-closed） |
| K6 | 判定强度不可升级：`runtime`/`doc` 永远拿不到 `hard` | `catalog.Entry.strength` + `contract.SOURCE_MAX_STRENGTH` |
| K7 | `AMBIGUOUS-*` / `PLATFORM-ABSENT` 是**结果**不是失败 → exit 1 | `tests/test_cli_exitcode.py` |
| K8 | `exit 1` 必须 `UNATTRIBUTABLE` | `selftest._check_exit_one`、`tests/test_exitcode.py` |
| K9 | `128+n` 的 `n` 只从编目取，代码里不许写死信号表 | `selftest._check_signal_validity` |
| K10 | 状态副本 = 2 张表；README 不承载状态 | `LAYOUT.STATUS` 的副本数结论行 |
| K11 | 布局门的变异靶子锚"既有事实"（文件/表行），**不锚"某个里程碑还没完成"** | `verify_gates.py` 的对照组 |
| K12 | **期望值写规范字面量**（0/1/3/4），不写被测代码读的同一个常量 | `selftest._check_exit_codes` 的注释 + `test_selftest_catches_broken_exit_code_mapping` |
| K13 | 脱敏门的 `SKIP_DIRS` 与 `.gitignore` 的目录级忽略**逐项对齐** | `tests/test_gate_alignment.py`（双向） |
| K14 | `gray` 强度条目的强制字样是 `"惯例非标准"` / `"约定非标准"`（不是"而非标准"） | `selftest._check_gray_markers` + `tests/test_exitcode.py` |
| K15 | 跨平台判歧义的分母 = **该域已覆盖的平台**（`catalog.covered_platforms`） | `tests/test_explain.py::test_number_without_platform_*` |

---

## 五、本机环境坑（只写实测过的，2026-11-01）

- `python` 是应用商店占位符（`python --version` → rc=49）；一律 `py -3.12` / `py -3.8`。
- 两条 Python 通道：**3.12.10**（主通道，装了 pytest 8.4.2 + PyYAML 6.0.3）、
  **3.8.8**（pytest 7.4.4 + PyYAML 有）。3.8 通道只验**语法面**，不是功能面。
- **`subprocess` 不能只传 `PYTHONPATH`**：3.8 通道上剪掉 `os.environ` 会让子进程崩在
  `_Py_HashRandomization_Init: failed to get random numbers to initialize Python`
  —— 看起来像"门在 3.8 上坏了"，实际是环境被剪掉了。一律 `{**os.environ, ...}`。
- **`spec_from_file_location` 不登记 `sys.modules`**：`@dataclass` 解析注解时
  `sys.modules.get(cls.__module__).__dict__` → `AttributeError`。动态加载工具模块要先登记。
- 本机 `raw.githubusercontent.com` 不可达；三平台头文件必须走 `gh api repos/.../contents/...`。
- 中文控制台编码 → 程序入口已加 `_ensure_utf8_stdio()`（按 `stream.encoding` 探针决定是否 reconfigure）；
  CI 侧仍要 job 级 `PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8`。
- `src` 布局：不装包直接跑必须 `PYTHONPATH=src`；CI 每个 job 都要设。
- 全程 `PYTHONDONTWRITEBYTECODE=1`（pyc 偶发损坏会导致随机 FAIL）。
- **`.mimosa/` 是本地钩子写的会话状态**，已加进 `.gitignore`；脱敏门的 `SKIP_DIRS` 里也有它。

---

## 六、DoD 逐项 checklist

- [x] `plan/00`–`plan/06` 七份齐备，各含布局门要求的小节
- [x] `AGENTS.md` + `plan/00` 顶部装订行（三锚点同现）
- [x] `tools/check_sprint_layout.py` 可跑，逐组变异变红（`verify_gates.py` 实跑留档见下）
- [x] `tools/check_desensitized.py` 可跑，四条规则逐组变红
- [x] `src/errcode_atlas/contract.py` 五态／四归因／四平台／三域／退出码齐备
- [x] CLI 骨架：`--version` → 0；未知子命令 → 4；`--platform win32` → 4 且提示两个视角
- [x] `tools/build_catalog.py --check` 在空编目合法初始态下 → 0，且有"读 4 个源文件"的空跑自证
- [x] `pytest -q` 双通道：`py -3.12` 全绿；`py -3.8` 全绿 + 1 个显式 skip（3.10+ 属性）
- [x] README 命令反射 + `.gitignore` ↔ 脱敏门对齐，都已落测试
- [x] `.github/workflows/ci.yml` 落盘 + **本地按 CI 原样 shell 标志逐步模拟过一次**
- [ ] ~~CI 绿~~ → **本棒不适用**：无远端、未推送。见 `plan/05` §4 U1
- [ ] 裸 clone（无 `.git` 树）验证 → **本棒末提交后跑**，结果见 `plan/05` §4 U1 的替代证据栏

**偏差说明**：

| 项 | 原计划 | 实际 | 原因与替代验证 |
|---|---|---|---|
| CI 实跑 | "CI 绿" | 未跑过 | 无远端。替代 = 本地等价校验（`py -3.12` / `py -3.8` 双通道全量测试 + 三道门 + 生成器 `--check` + 按 CI 原样 shell 标志逐步模拟）；不可本机实跑的通路（runner 矩阵 / `--network none`）显式标"待首推验证"，缺口记 `plan/05` §4 U1–U4 |
| `plan/01` 模块① 口径 | "YAML → JSON 的确定性变换" | 生成侧 dev 工具 + 运行期只校验 | 运行期必须零依赖。已登记 `plan/02` D2 与 `plan/06` G1，文档口径一致 |
| 跨平台判歧义的分母 | `plan/03` 原写"各平台不一致" | 明确为"该域**已覆盖**的平台" | 把"还没查"与"查过没有"分开：前者不进分母（否则编目半途每条都判跨平台歧义），后者必须算不一致（否则"只在一个平台有"会被判成"各平台一致"）。已回写 `plan/03` §2.2 并在 K15 |

---

## 七、关键命令速查

```bash
# 门（对外）
py -3.12 tools/check_sprint_layout.py
py -3.12 tools/check_desensitized.py

# 门自己是否在验东西（逐组变异）
py -3.12 tools/verify_gates.py

# 编目冻结面
py -3.12 tools/build_catalog.py --check
py -3.12 tools/build_catalog.py --out src/errcode_atlas/data

# 判定面（骨架期：编目为空 → UNKNOWN / exit 3）
PYTHONPATH=src py -3.12 -m errcode_atlas explain 98 --platform linux
PYTHONPATH=src py -3.12 -m errcode_atlas exitcode 137 --platform linux
PYTHONPATH=src py -3.12 -m errcode_atlas selftest

# 测试（两条通道）
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 py -3.12 -m pytest -q
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 py -3.8 -m pytest -q
```
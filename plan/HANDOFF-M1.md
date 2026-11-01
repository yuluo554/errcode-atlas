# HANDOFF-M1 · 数据先行（三平台编目 + 两个运行时视角）

> 本棒：M1（已完成）。下一棒：M2 解析。
> 库内一律相对路径；本机绝对路径只出现在用户侧启动命令里。

---

## 一、当前进度 + 证据

| 项 | 证据（命令 / 文件） |
|---|---|
| 取数脚本落位 | `tools/fetch_sources.py`：`--list` / `--out` / `--check` / `--only` / `--ref`；只走 `gh api`，无 raw 回退路径 |
| 原文已取到并钉 sha | `_headers/SOURCES.json`：5 份原文 + `torvalds/linux@cbbddb6b…` / `apple-oss-distributions/xnu@f6217f89…` + 逐份 sha256 |
| 抽取脚本落位 | `tools/extract_catalog.py`：`--out` / `--check` / `--report`；按用户态默认编译环境求值 `#if` 链 |
| 编目真实条目数 | **599 条**（`py -3.12 tools/extract_catalog.py --report`）：linux 170 / macos 141 / win32-node 145 / win32-python 143 |
| 逐条带出处 | 每条 `source` 齐备；`kind: file` 的 `source.line` 由测试**按行号回原文取那一行**校验（改错一位立刻红） |
| 冻结面稳定 | `py -3.12 tools/build_catalog.py --check` → 0（读 4 个源文件 / 599 条）；`--out` 双跑逐字节一致 |
| 复现性 | `py -3.12 tools/extract_catalog.py --check` → 0；**`py -3.8` 同命令也 → 0**（两通道同一份 YAML） |
| 五个信号分叉点 | 测试逐点钉死：`SIGBUS` 7/10、`SIGSTOP` 19/17、`SIGCHLD` 17/20、`SIGUSR1` 10/30、`SIGSTKFLT` 16/**无** |
| 三个 Windows 数值差异 | 测试逐点钉死：`EADDRINUSE` 100/10048、`ECONNREFUSED` 107/10061、`ETIMEDOUT` 138/10060 |
| 缺口三态逐行落实 | `data/gaps.md` 全部改写为具体原因（不是"待 M1"）；可被 `--report` 的输出逐条对上 |
| X3 `128+n` 原典已核 | POSIX `wait()` 页：只有 `WIFSIGNALED`/`WTERMSIG`，`WEXITSTATUS` 取低 8 位，**无 `128+n` 公式** → `gray` 处置 |
| 新增测试 | `tests/test_catalog_data_m1.py`（27 条），双通道全绿 |
| 全量测试双通道 | `py -3.12` 203 passed；`py -3.8` 202 passed + 1 skip（3.10+ 属性） |
| 变异验证 | `py -3.12 tools/verify_gates.py` → 全组 CAUGHT（含 2 组阴性对照），还原后复绿 |

**本轮抓到并修掉的真缺陷（不是"写完就绿"）**：

| # | 形态 | 是谁抓出来的 |
|---|---|---|
| ① | `EWOULDBLOCK → EAGAIN` 的别名目标在**另一份**头文件里，扫描器每文件清空符号表 → 该条凭空消失 | `--report` 把 `EWOULDBLOCK` 列进"值是另一个宏，可见区里没有数值定义"；修正 = 跨文件共享符号表 |
| ② | `program_version` 取 `sys.executable` 报的版本 → 换 3.8 通道跑一次 `--check` 就把 `3.12.10` 写成 `3.8.8`，**误报"YAML 被手改"** | `py -3.8 tools/extract_catalog.py --check` 报 win32-python 不一致，而两份 `errno` 模块内容逐项相同 → 定位到是出处字段没钉死 |
| ③ | 模块级 `Drop = tuple[str, str, str, int]` 是 3.9+ 才支持的下标，3.8 通道直接 TypeError | 3.8 通道跑抽检时崩在 `import` 阶段（`from __future__ import annotations` 只保护注解，不保护普通赋值） |
| ④ | 变异靶子 `L4b` 锚在 `PENDING_TOOLS["tools/fetch_sources.py"]` 那一行 —— 而 M1 落位时该行按纪律必须删除 → 靶子随进度漂移 | 改 `PENDING_TOOLS` 后立刻想到 K11「靶子锚既有事实、不锚某里程碑还没完成」，改锚 `check_release.py`(M6) |
| ⑤ | `data/README.md` X1 写"M1 逐条抽取"Node 错误码，而计划里它属 M2 | 与本棒 DoD 对账时发现口径不一致，已改 M2 |
| ⑥ | 首版抽取器把 macOS `EOPNOTSUPP` 当普通条目处理，没意识到它定义两次（45 / 102） | `--report` 显示 raw 120 / catalog 109 的差额要能解释 → 回原文确认默认环境走 102 分支 |
| ⑦ | **装载真实编目后暴露口径冲突**：`explain EAGAIN`（未给平台）返回 `UNAMBIGUOUS`/exit 0 并列 11/35/11/11，而 `data/README.md` §5.2 把 `EAGAIN → 11/35/11` 举作 `AMBIGUOUS-CROSS-PLATFORM` 的样本 | **装好的包实跑**时发现（工作树 pytest 全绿抓不到：那是文档与设计的冲突，不是代码错） |

---

## 二、当前事实·状态不变量（下一棒动手前必须知道）

1. **编目源是唯一真相源，且现在有两个上游**：`_headers/`（原文缓存，`.gitignore` 封）→
   `data/catalog/*.yaml`（入仓）→ `src/errcode_atlas/data/catalog.json`（派生物）。
   改数据的正确链路 = **改抽取器或改 `MACRO_ENV` → 重跑 `--out` → 跑 `build_catalog.py --out` → 两道 `--check`**。
   手改 YAML 会被 `extract_catalog.py --check` 抓；手改 JSON 会被 `build_catalog.py --check` 抓。
2. **`extract_catalog.py` 的 `--check` 必须零网络**：它只读 `_headers/` 与仓库 YAML。
   不要把 `fetch_sources.py` 的联网步骤并进来 —— 否则离线环境里"验数据对不对"这件事做不了。
3. **`program_version` 是常量**（`PINNED_RUNTIME_VERSIONS`），不是 `sys.executable` 的版本。
   `kind: runtime` 的 `program_version` 记录的是**某天在某机器上实读的事实**，不是本次运行环境。
   判据 = "这个字段是事实，还是本次运行的环境？"
4. **`entry_count` 现在不是 0**：errno 515 / signal 84 / exit 0。`exit` 域要等 M2
   （`sysexits` + Node 错误码）才有条目 —— **M2 会让 `entry_count` 变，这是预期**，
   不是"数据被改坏"。改完记得重跑 `build_catalog.py --out`。
5. **`macos.yaml` 是"用户态默认编译环境"口径**，不是"头文件里所有 `#define`"：
   `__DARWIN_C_LEVEL=FULL`(900000)、`__DARWIN_UNIX03=1`、`KERNEL`/`_POSIX_C_SOURCE` 未定义。
   所以 `EOPNOTSUPP=102`（不是 45）、7 号是 `SIGEMT`（不是 `SIGPOLL`）、10 条内核伪错误不入编目。
   **要改这个口径就得同时改 `MACRO_ENV` 与 `data/gaps.md` 的对应行**，否则缺口表会说谎。
6. **`SIGSTKFLT` 不在 `macos.yaml` 里是对的** —— 它是 `PLATFORM-ABSENT` 的证据源头。
   别"顺手"补一个占位条目：macOS 的 16 号是 `SIGURG`，补 `SIGSTKFLT=16` 会让
   "该平台没有这个信号"这个一等公民结论消失。
7. **同一数值多名是合法且必须保留的**：linux errno 4 组别名、linux signal 3 组、
   macos errno 2 组、**win32-python errno 35 组**（`E*` 与 `WSA*` 同值并存）。
   这就是 `AMBIGUOUS-SAME-PLATFORM` 的真实素材；谁"去重"谁就把招牌判据弄没了。
8. **`source.file` 写的是上游仓库路径，不是 `_headers/` 本地缓存路径**。
   本地路径对读者无意义，且会让"重新取数后出处仍成立"变成假话。
9. **`.gitattributes` 的 `* text=auto eol=lf` 仍是摘要口径的前提**（M0 第 8 条不变）。
10. **`PENDING_TOOLS` 现在只剩 `tools/check_release.py`(M6)**。落位 M6 那个脚本时必须同笔删除登记项。

---

## 三、下一棒待办（M2 解析）

0. **先处理 `plan/06` G6（口径冲突，优先于下面所有条目）**：`plan/03` §2.2 的七行判定顺序表
   **没有覆盖"名字 + 无平台 + 各平台取值不一致"这种形态**。M1 装载真实编目后实测：
   `errcode-atlas explain EAGAIN`（未给平台）→ `UNAMBIGUOUS` / exit 0，列四平台 11/35/11/11；
   而 `data/README.md` §5.2 把 `EAGAIN → 11/35/11` 举作 `AMBIGUOUS-CROSS-PLATFORM` 的样本。
   两处必须择一改口，**不许两边都留着**。当前代码行为有明确设计依据（名字查询确有唯一答案），
   所以更可能是"§5.2 那句举例挑错了样本"，但**这是判定态棒该拍的板**，不是数据棒该顺手改的。
1. `tools/fetch_sources.py` 的清单加两份：`sysexits` 页与 `nodejs.org/api/errors.html`。
   **它们不是 `contents/` 接口能取的**（不是某个仓库的文件）—— 要么加一个 `--url` 通路
   （同样不吃 raw），要么明确登记为"手工取 + 记 sha256"。别默默降级成"凭记忆抄"。
   > 这条是下一棒最容易踩的坑：现有 `fetch_one` 只认 `repos/<o>/<r>/contents/<path>`。
2. `data/catalog/sysexits.yaml`：`kind: doc` + `url` + `anchor` + `verified_at`（三选一里的第三种，还没被用过）。
   **这是 `SOURCE_DOC` 分支的首次实战** —— `catalog._validate_source` 的 doc 校验目前零调用。
3. `data/catalog/node-errors.yaml`：`nodejs.org/api/errors.html` 415 KB，逐条抽 `ERR_*`。
   `build_catalog.py` 里 `SHARED_FILES` 已预留这两个文件名（`sysexits.yaml`→`exit`、`node-errors.yaml`→`errno`），
   **但 `collect()` 目前只遍历 `PLATFORM_FILES`，不读 `SHARED_FILES`** —— 这个接线是下一棒要补的。
4. 编目→查询索引：`catalog.build_indexes` 已建好三索引，但**共享域文件的多平台归属**要想清楚
   （`sysexits` 是全平台共享，"在哪几个平台可见"会直接影响 `covered_platforms` 的分母，
   而那个分母决定跨平台歧义判定 —— 见 K15）。
5. `UNKNOWN` 路径可复现：现在是"越界 → exit 3"，M2 要补一条 **"编目里有该域但没该值"** 的用例。
6. `data/gaps.md` 里"Node 错误码清单"那一行改状态（未录 → 全录/部分录）。
7. 收尾：DoD 验证 → `plan/00`/`plan/05`/`plan/06` 状态回写 → **删掉 `PENDING_TOOLS` 里没有的登记**
   → **写 `plan/HANDOFF-M3.md`**（M3 的**入口文件**，不是 M2 的收官单）→ commit。

> **关于入口文件（M1 本轮踩过并订正）**：`plan/HANDOFF-M<k>.md` 按**它开哪个里程碑**命名，
> 不按"哪一棒写完它"命名。所以 **M1 收尾的义务就是落盘 `HANDOFF-M2.md`** ——
> 已由本棒完成。同理，下一棒收尾要落盘的是 `HANDOFF-M3.md`。
> 首版布局门只遍历已 ✅ 的里程碑，于是"漏了当前棒入口"完全看不见
> （它当时报"2 份交接单齐 全绿"）；现在门有 `L6c`（当前入口缺失）与 `L6d`（超前入口）两组变异守着。

---

## 四、既定口径清单（K 编号 —— 动了会打挂测试的约定）

M0 的 K1–K15 **全部仍然有效**，另加 M1 新增 4 条：

| K | 口径 | 动了会红的东西 |
|---|---|---|
| K16 | **编译环境口径写死在 `MACRO_ENV`**，不靠 `gcc -dM -E` 现算（本机无 Apple 工具链，现算不可复现） | `tests/test_catalog_data_m1.py` 的 `EOPNOTSUPP=102` / kernel-only 两组 |
| K17 | **抽取器的行号必须能回原文取到同名 `#define`** | `test_every_file_entry_line_points_at_its_own_define` |
| K18 | **`program_version` 是常量**（`PINNED_RUNTIME_VERSIONS`），不取 `sys.executable` 版本 | `test_runtime_program_version_is_pinned_not_current_interpreter` |
| K19 | **`extract_catalog.py --check` 零网络**（只读 `_headers/` 与仓库 YAML） | 离线环境下跑该命令；并进本表原因：联网会让离线复核做不了 |

> K12（期望值写规范字面量）在 M1 的测试里同样适用：分叉点断言写的是 `7`/`10` 这类数字，
> 不是 `catalog.value_of(...)` 的返回值。

---

## 五、本机环境坑（只写实测过的，2026-11-01 续）

M0 §五 全部仍有效，另加：

- **`from __future__ import annotations` 只保护注解，不保护普通赋值**：
  `Drop = tuple[str, str, str, int]` 在 3.8 通道上 `import` 期就 TypeError。
  模块级泛型别名要用 `typing.Tuple[...]`。
- **`sys.executable` 在 dev 脚本里要当心**：用它取"程序版本"会让双通道运行产生**不同输出**。
  用它取"跑哪条解释器"是对的（`python_constants()` 仍用 `sys.executable` 跑探针），
  用它填**出处字段**是错的。
- **`node -e` 里用 `process.stdout.write` 而不是 `console.log`**：后者会多一个换行，
  在 `json.loads` 前后不一致时容易把"少一行"看成"数据不同"。
- 本机 `py -3.8` 通道的 `errno` 模块与 `py -3.12` **逐项相同**（已实测 136 项、零差异）——
  所以两通道能跑出同一份 YAML；但**这只在本机成立**，CI 上的其他 Windows 版本未验（U4 同族）。
- **Bash 里用重定向写文件会被本地安全钩子拦下**（`>` / `|` 到仓库文件）。
  取数、抽取一律走"脚本自己写文件"，不要用 shell 重定向 —— 顺带也是更好的做法（可复现）。

---

## 六、DoD 逐项 checklist

- [x] 三个头文件 / 两个运行时视角逐条抽取，**每条带出处**（599 条）
- [x] `data/gaps.md` 建表且逐行可查（三态可数；逐行原因可由 `--report` 复现）
- [x] `build_catalog.py --check` 在真实编目上逐字节稳定（`--out` 双跑一致）
- [x] `data/README.md` §1 的 ⬜ 项（X3）据实翻转并写明"标准里确实没有"
- [x] `tools/fetch_sources.py` 落位，且 **`PENDING_TOOLS` 登记项同笔删除**
- [x] 五个信号分叉点 + 三个 Windows 数值差异**逐点有断言**
- [x] `pytest` 双通道：`py -3.12` 203 passed；`py -3.8` 202 passed + 1 skip
- [x] 两道门全绿；`verify_gates.py` 全组 CAUGHT，还原后复绿
- [x] `data/catalog/*.yaml` 可由 `extract_catalog.py --out` 逐字节复现（**两条通道都是**）
- [x] **无 `.git` 导出树验证**（`git archive HEAD` → 解包树）：两道门绿、`build_catalog.py --check`
      报「599 条」一致、`pytest` 全绿且 **28 条 M1 数据测试显式 skip**（无 `_headers/`，skip 原因写明）
- [x] **装好的包实跑**（导出树里建 venv → `pip install .`）：`__file__` 落在 `site-packages`；
      `--version` / `build --check`（errno 515 / signal 84）/ `explain 6 --domain signal` → 1 /
      `explain SIGSTKFLT --platform macos` → 1 且报 `PLATFORM-ABSENT` / `exitcode 137` → 0
- [x] 装好的包**抓到了一条工作树抓不到的真缺陷**（见 §一 缺陷 ⑦ 与 §三 第 0 条）
- [ ] ~~CI 绿~~ → **本棒仍不适用**：无远端、未推送。见 `plan/05` §4 U1

**偏差说明**：

| 项 | 原计划（HANDOFF-M0 §三） | 实际 | 原因与替代验证 |
|---|---|---|---|
| 抽取脚本 | 只提"写 `tools/fetch_sources.py`"，抽取手法未定 | 拆成 `fetch_sources.py`（联网取原文）+ `extract_catalog.py`（零网络抽取） | 取数与抽取的**网络需求相反**：合成一个会让离线复核被迫联网。已登记 `plan/04` §1.2 |
| "逐条抽取" | 未说明条件编译怎么处理 | 按写死的用户态默认环境求值 `#if` 链，不可见分支逐条登记 | 不求值就会把内核伪错误当用户态 errno、把 `EOPNOTSUPP` 抄成 45。差额（38→34 / 45→32）在 `data/gaps.md` 逐类登记 |
| macOS errno 规模 | `data/README.md` 原写"119 条" | 原文 120 行 / 119 个不同名字；用户态入编目 109 条 | 119 指的是**不同名字数**（`EOPNOTSUPP` 定义两次）。已在 `data/README.md` §1.1 与 `data/gaps.md` 写明差额来源 |
| Windows Python 规模 | 原写"88 项" | 136 项 = `E*` 88 + `WSA*` 48 | 88 只数了 `E*` 前缀。`WSA*` 是同值并存的独立常量（`AMBIGUOUS-SAME-PLATFORM` 素材），漏了会少 35 组歧义样本 |
| 竞品检索（G4） | "M1 补检索" | 已补：两个检索式 0 命中，`exit code reference` 42 命中无同类 | 仍是**软论据**；已写明"不能当成方向空白的强结论" |

---

## 七、关键命令速查

```bash
# 门（对外）
py -3.12 tools/check_sprint_layout.py
py -3.12 tools/check_desensitized.py

# 门自己是否在验东西（逐组变异）
py -3.12 tools/verify_gates.py

# 数据链（三步，顺序不能颠倒）
py -3.12 tools/fetch_sources.py --out _headers        # 1) 取原文（联网，gh api）
py -3.12 tools/fetch_sources.py --check               #    已取件 sha256 对账
py -3.12 tools/extract_catalog.py --out data/catalog   # 2) 抽取 YAML（零网络）
py -3.12 tools/extract_catalog.py --check              #    与仓库 YAML 逐字节比对
py -3.12 tools/extract_catalog.py --report             #    取数事实 + 被排除项
py -3.12 tools/build_catalog.py --out src/errcode_atlas/data   # 3) 冻结 JSON
py -3.12 tools/build_catalog.py --check

# 判定面（真实编目已可用）
PYTHONPATH=src py -3.12 -m errcode_atlas explain 6 --platform linux --domain signal   # AMBIGUOUS-SAME-PLATFORM → 1
PYTHONPATH=src py -3.12 -m errcode_atlas explain SIGSTKFLT --platform macos --domain signal  # PLATFORM-ABSENT → 1
PYTHONPATH=src py -3.12 -m errcode_atlas exitcode 137 --platform linux   # SIGNAL-KILLED(9) → 0

# 测试（两条通道）
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 py -3.12 -m pytest -q
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 py -3.8 -m pytest -q
```
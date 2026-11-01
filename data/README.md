# data/README — 依据查证与口径唯一定义

> 本文件是 **11-1-errcode-atlas** 的**唯一口径真相源**。
> `plan/01`、`plan/03`、代码、`SKILL.md` 一律**引用本节编号，不得复述数值**。

---

## 1. 依据查证记录（三态）

### 1.1 errno —— 三平台取值

| # | 依据 | 渠道 | 状态 | 规模 |
|---|---|---|---|---|
| E1 | Linux errno 基础段 | `torvalds/linux` `include/uapi/asm-generic/errno-base.h` | ✅ 已抽取入编目 | 34 条 `#define E*` |
| E2 | Linux errno 扩展段 | 同仓 `include/uapi/asm-generic/errno.h` | ✅ 已抽取入编目 | 102 条 `#define E*`（含 4 组别名：`EWOULDBLOCK`→`EAGAIN`、`EDEADLOCK`→`EDEADLK`、`EFSBADCRC`→`EBADMSG`、`EFSCORRUPTED`→`EUCLEAN`） |
| E3 | macOS errno | `apple-oss-distributions/xnu` `bsd/sys/errno.h` | ✅ 已抽取入编目 | 原文 120 行 `#define E*` / **119 个不同名字**（`EOPNOTSUPP` 定义了两次，分属两个编译环境）；用户态默认口径下入编目 **109** 条 |
| E4 | Windows errno（**Node 视角**） | 本机 `os.constants.errno` | ✅ 已抽取入编目 | 134 项 = `E*` 76 + `WSA*` 58，Node v24.15.0 / win32 |
| E5 | Windows errno（**Python 视角**） | 本机 `errno` 模块 | ✅ 已抽取入编目 | 136 项 = `E*` 88 + `WSA*` 48（含 `WSABASEERR`） |

> **⚠️ E4 与 E5 在同一台机器上数值不同**，这是本题最硬的事实之一：
> `EADDRINUSE` → Node `100`、Python `10048`；`ECONNREFUSED` → Node `107`、Python `10061`；
> `ETIMEDOUT` → Node `138`、Python `10060`。
> **因此编目必须区分"运行时视角"，不得只写一个 "windows" 值。**
>
> **E5 的"88 项"是 `E*` 前缀那部分**；Python 的 `errno` 模块同时导出 48 个 `WSA*` 名字，
> 它们与 `E*` 在**同一数值**上并存（如 `EADDRINUSE` 与 `WSAEADDRINUSE` 都是 10048）。
> 于是同一台机器上：Node 视角的 `100` 只有一个名字，Python 视角的 `10048` 有**两个**名字
> —— 这正是 `AMBIGUOUS-SAME-PLATFORM` 的真实来源，不是编造出来的用例。
>
> 两个视角的规模数字由 `py -3.12 tools/extract_catalog.py --report` 数出来，不是手写常量。

### 1.2 信号

| # | 依据 | 渠道 | 状态 | 规模 |
|---|---|---|---|---|
| S1 | Linux 信号编号 | `include/uapi/asm-generic/signal.h` | ✅ 已抽取入编目 | 原文 38 条 `#define SIG*`；入编目 **34** 条（排除见下） |
| S2 | macOS 信号编号 | xnu `bsd/sys/signal.h` | ✅ 已抽取入编目 | 原文 52 行 / 45 个不同名字；用户态默认口径入编目 **32** 条 |

> **实测分叉点（已核对原文，并由测试逐点钉死）**：
> `SIGBUS` Linux=7 / macOS=10；`SIGSTKFLT` Linux=16 / macOS **无**；
> `SIGSTOP` Linux=19 / macOS=17；`SIGCHLD` Linux=17 / macOS=20；
> `SIGUSR1` Linux=10 / macOS=30。
> **从 7 号起两平台即开始分叉**，因此任何"统一的信号编号表"都是错的。
> 这五个点各有一条断言（`tests/test_catalog_data_m1.py::test_documented_signal_fork_points`
> 与 `::test_sigstkflt_exists_on_linux_and_absent_on_macos`），不是靠人复核。
>
> **S1 的"38 → 34"与 S2 的"45 → 32"不是遗漏**，逐类原因见 `data/gaps.md`：
> 非信号的 `SIG_*`/`SIGEV_*`/`SIGSTKSZ`、只在别的编译环境下可见的分支（macOS `SIGPOLL`）、
> 原文自述"不应被用户态当作常量"的实时信号界（`SIGRTMIN`/`SIGRTMAX`）、
> 以及注释块里的 `SIGLOST`。

### 1.3 其他

| # | 依据 | 渠道 | 状态 | 备注 |
|---|---|---|---|---|
| X1 | Node 错误码清单 | `nodejs.org/api/errors.html` | ✅ 已抽取入编目（**M2**） | 415,009 bytes；**435 节 = 现行 383 + 弃用 52**，落 `node` 域（不是 `errno`，见 §2.3） |
| X2 | `sysexits` 约定（64–78） | `man.openbsd.org/sysexits` | ✅ 已抽取入编目（**M2**） | 15 条，落 `exit` 域，**约定非标准**，报告须标注 |
| X3 | `128+n` 归因惯例 | POSIX.1-2017 `wait()` 手册页（已核对原文） | ✅ 已核对：**标准中确实没有这条** | **惯例非标准**，报告中必须如此标注 |
| X4 | Node `os.constants.signals` | 本机实读 | ✅ 已抽取入编目 | 11 项（Windows 平台不完整，见 gaps） |

> **⚠️ X3 的核对做完了，结论是"风险落地"而不是"风险消除"。**
>
> **核对对象**：POSIX.1-2017 `wait()` 页
> （`pubs.opengroup.org/onlinepubs/9699919799/functions/wait.html`）。
> **核对结论（逐条）**：
> 1. `WEXITSTATUS(status)` 只在 `WIFEXITED` 为真时有意义，取的是传给 `_exit()` / `exit()` /
>    `main()` 参数的**低 8 位**；
> 2. 信号终止用 `WIFSIGNALED` + `WTERMSIG`，后者求值为"导致子进程终止的信号编号"；
> 3. **全文没有任何 `128+n` 或等价公式。**
>
> 所以 `128+n` 是 **shell 实现惯例**（shell 在 `$?` 上报 128+信号号），不是 POSIX 正文规定的。
> **报告与文档必须写"惯例"，不得写"标准规定"。**
>
> 状态从 ⬜ 翻 ✅ 的含义是"**核对这个动作**做完了"，**不是**"这条规矩变成了标准"。
> 强制措辞由三层兜住，不靠人记得写：`gray` 强度（`plan/04` §2.3）→ `notes` 里的
> "惯例非标准"字样 → `selftest._check_gray_markers` 与 `tests/test_exitcode.py` 的断言。
> 缺口性质记在 `data/gaps.md`（三态为「部分录」，原因是"POSIX 确实没有"）。

---

## 2. 数据源可获取性记录

### 2.1 底座（编目随包分发，运行时零联网）

| 底座 | 获取方式 | 状态 | 规模 |
|---|---|---|---|
| Linux errno / 信号 | `gh api repos/torvalds/linux/contents/... --jq .content \| base64 -d` | ✅ 可直连 | 两文件 |
| macOS errno / 信号 | `gh api repos/apple-oss-distributions/xnu/contents/...` | ✅ 可直连 | 两文件 |
| Windows errno | 本机运行时实读（Node + Python） | ✅ 可直连 | 134 + 88 项 |
| Node 错误码 | `nodejs.org/api/errors.html` | ✅ 可直连 | 415 KB |
| `sysexits` | `man.openbsd.org/sysexits` | ✅ 可直连 | 单页 |

> **⚠️ 环境坑（已实测，写入 M1 前置条件）**：
> `raw.githubusercontent.com` 在本机 **HTTP 000**（不可达），`github.com` 网页直连亦被重置。
> **必须走 `gh api repos/<owner>/<repo>/contents/<path>`**，不得用 raw 链接。
> `huggingface.co` 同为 000，本案不使用 HF。

### 2.2 检索式与基准日（软论据，非硬锚点）

**检索窗口**：2026-11-01T03:10Z–04:45Z 与 M1 补检索 2026-11-01T09:5xZ，`gh api search/repositories`。

| 检索式 | total | 采用状态 |
|---|---:|---|
| `error code catalog mcp` | 3 | ⬜ 无关（1★ 安装器、0★ 商品目录、0★ learnings 索引） |
| `exit code reference tool` | 16 | ⬜ **全噪声**（头名 321★ 为 FTC 机器人队） |
| `error message database ai agent` | 1 | ⬜ 0★ 无关 |
| `stack trace knowledge base agent` | 4 | ⬜ 最高 1★，形态为 RAG 问答 |
| `errno table multi platform` | 0 | ⬜ **M1 已补检索，空**（`errno cross platform reference` 同为 0） |
| `exit code reference` | 42 | ⬜ M1 补检索：前四名 0★/0★/0★/7★（末名是 sshd 配置检查，非同类）。与上一行的 16 之差来自检索式措辞，两式合计仍无同类项目 |

> **`total≈0` 一律只是软论据。** 本案的硬锚点是 §1.1–1.3 的**逐条原文与实读**，不是检索空白。
> M1 补检的两个检索式（`errno table multi platform` / `errno cross platform reference`）
> 都是 0 命中 —— 它们的价值只在于"没有撞上现成同类项目"这一条弱证据，
> **不能**被写成"这个方向没人做"的强结论（空白可能是检索式措辞问题，`exit code reference`
> 两式 total 差 42↔16 就说明了这一点）。

### 2.3 共享域文件的平台归属（M2 的设计决定，不是失误）

`sysexits.yaml` 与 `node-errors.yaml` **不绑单一平台轴**：它们是"共享文件"，生成时按
`tools/build_catalog.py` 的 `SHARED_SPREAD` 展开到多个平台。**两个文件挂的轴不一样**，
这是事实差异，不是配置遗漏：

| 文件 | 域 | 挂到哪几个平台轴 | 为什么 |
|---|---|---|---|
| `sysexits.yaml` | `exit` | **四个全挂**（`linux` / `macos` / `win32-node` / `win32-python`） | `sysexits` 是**进程退出码**约定，四个平台上的进程都有退出码 |
| `node-errors.yaml` | `node` | **三个**（`linux` / `macos` / `win32-node`），**不挂 `win32-python`** | `ERR_*` 是 **Node 运行时**抛的码：Linux/macOS 上跑 Node 也抛同一批，Python 视角不抛 |

> **两个方向都有假答案，必须选对**：
>
> * **挂少了** → `covered_platforms(域)` 的分母变小。`exit` 只挂一个轴时，
>   `explain 64 --domain exit`（无平台）会把另外三个平台算成"查过、没有这个值"
>   → 凭空造出假 `PLATFORM-ABSENT`；分母缩到 1 时又会变成假 `UNAMBIGUOUS`。
> * **挂多了** → 在根本不存在这套码的平台上造出条目。`win32-python` 挂上 `node` 域，
>   会让 `explain ERR_AMBIGUOUS_ARGUMENT --platform win32-python` 答"有"，
>   而那台运行时根本不抛这个码。
>
> 判据 = **"这套码/约定，在这个平台上真的成立吗？"** —— 成立就挂，不成立就不挂。
> 这一条由 `tests/test_catalog_m2.py` 的 `test_sysexits_covers_all_four_platforms`
> 与 `test_node_domain_covers_three_platforms_not_python_view` 钉死。
>
> **`win32-python` 上查 `ERR_*` 得到的是 `PLATFORM-ABSENT`（exit 1），不是 `UNKNOWN`（exit 3）**
> —— 前者说"这个平台没有这套码"，后者说"我没查到"。这个区分是本题的一等公民。

### 2.4 为什么 `node` 是独立域，不是 `errno` 的子类

`ERR_*` **没有数字码值**，与 OS errno **无映射关系**。若塞进 `errno` 域：

* 要么得给它们编一个假数字（编造数值）；
* 要么让 `errno` 域的"一数多名"索引混进一批没有数字的条目 —— `explain 100` 之类
  会开始把 `ERR_*` 名字当候选吐出来。

所以 `node` 是**无值域**（`contract.VALUELESS_DOMAINS`）：条目的 `value` 缺省，
索引只按名字建，数字查询永远碰不到它。口径编号 = K23；断言在
`tests/test_catalog_m2.py` 的 `test_err_codes_are_not_in_errno_domain` 与
`test_err_codes_have_no_numeric_value`。

---

## 3. 合成数据纪律

- 基准语料全部合成，`fixtures/<case>/` 含 `INPUT.md` 与 `expected.json`；
- 每个 case 声明它验证哪条判定态，覆盖度口径见 §4；
- **跨平台分叉点必须全覆盖**（§1.2 列出的五个信号分叉、§1.1 的 errno 差异点）；
- **`EAGAIN` 只能作为"名字查询"的样本**，不能作为跨平台歧义的样本（§5.2 已改口）；
- **不可归因集是强制项**：`exit 1`、无平台数字、越界值、`PLATFORM-ABSENT` 各至少一例；
  外加 **`UNKNOWN` 的第二种形态**（域内有条目、但无此值）；
- 语料不含用户路径；编目值全部来自公开头文件、官方文档页或本机实读，**可被任何人复现**。

---

## 4. 覆盖度口径

| 域 | 最低覆盖项 | 说明 |
|---|---|---|
| errno | 三平台 × 至少 30 个公共常量 | 含 §1.1 全部差异点 |
| 信号 | 两平台 × 全部 `#define SIG*` | 含 §1.2 五个分叉点 |
| 退出码 | `0` / `1` / `64–78` / `128+n`(n∈{2,9,11,15}) / 越界 | `exit 1` 必须 `UNATTRIBUTABLE` |
| `sysexits`（`exit` 域编目） | **64–78 全部 15 条**，逐条带 `#EX_*` 段锚 | M2 起由编目承载；判定**不依赖它**（K22） |
| Node 错误码（`node` 域） | **页面全部 435 节**（现行 383 + 弃用 52） | 弃用条目必须在释义里点名 legacy；无数字码值 |
| 判定态 | 五态各 ≥2 例 | `UNKNOWN` 与 `UNAMBIGUOUS` 各 ≥3 例 |
| `UNKNOWN` 两形态 | **越界值**与**域内有条目但无此值**各 ≥1 例 | 后者 M2 才成立（`exit` 域为空时两种形态无从区分） |

> 未达上表门槛不得进入 M4 出口。**具体数值以本节为准，`plan/01` 不复述。**

### 4.1 M3 已落实的部分与 M4 承接的部分（分界，不是打折）

| 门槛项 | M3 状态 | 证据 |
|---|---|---|
| 判定态五态各 ≥2 / `UNKNOWN` 与 `UNAMBIGUOUS` 各 ≥3 | ✅ 已在种子语料里达到 | `tests/test_fixtures_meta.py::test_every_verdict_has_at_least_two_cases` 与 `::test_high_bar_verdicts_have_at_least_three_cases` |
| `UNKNOWN` 两形态各 ≥1 | ✅ | `::test_unknown_has_both_shapes`（按真编目查表判定形态，不是只看"给了域"） |
| 退出码 `0` / `1` / `64–78` / `128+n`(n∈{2,9,11,15}) / 越界 | ✅ `64–78` 全 15 条；`128+n` 取 n∈{2,9,11,15,19}；越界含 `-1/256` | `::test_all_fifteen_sysexits_codes_are_covered`、`::test_unattributable_exit_one_is_present`、`::test_128_plus_n_invalid_case_is_present` |
| 信号分叉点五个（`SIGBUS`/`SIGSTKFLT`/`SIGSTOP`/`SIGCHLD`/`SIGUSR1`） | ✅ 各一例（其中 `SIGSTKFLT` 走 `PLATFORM-ABSENT` 形态） | `::test_signal_fork_points_have_a_cross_platform_case`、`::test_sigstkflt_fork_has_platform_absent_case` |
| 三个 Windows 数值差异点 | ✅ 双视角各一例 | `::test_windows_dual_view_numeric_points_are_covered` |
| **errno 三平台 × ≥30 个公共常量** | ⬜ **M4** | 种子语料只取差异点与代表值，未铺满 30 个/平台 |
| **信号两平台 × 全部 `#define SIG*`**（66 条） | ⬜ **M4** | 同上：已覆盖全部分叉点，未逐条铺满 |
| **Node 435 节逐条** | ⬜ **M4** | 种子语料取 3 条代表（现行 / 弃用 / 跨视角缺失） |

> **这张表的存在理由**：`plan/HANDOFF-M3.md` §三把 M3 定义为"判定层收口"、M4 定义为"语料成规模"，
> 而 §六 的 DoD 又写着"覆盖 §4 全部门槛"。两处并存会让人把 M4 的规模活算进 M3。
> 表把"已在种子语料里证明可达"与"还要铺满规模"分开列 —— **不是降级门槛，是把两棒的分界写清楚**。
> `plan/05` §2 的 M3 DoD 三条（五态可达 / `128+n` 有效性 / 判定顺序逐行测）与本节上半张表一致。

---

## 5. ★ 数值口径唯一定义（所有数值只在这里出现一次）

### 5.1 退出码语义（本工具自身）

| 退出码 | 含义 |
|---:|---|
| `0` | 判定完成，结果为 `UNAMBIGUOUS` 或 `SIGNAL-KILLED` / `NORMAL-EXIT` / `SYSEXITS` |
| `1` | 判定完成，结果为**不可唯一归因**（`AMBIGUOUS-*` / `UNATTRIBUTABLE` / `PLATFORM-ABSENT`） |
| `3` | 算不了（编目缺失、参数域不支持） |
| `4` | 用法错误 |

> **硬纪律**：`UNKNOWN`（编目无此值）→ 退出码 `3`，**不得与 `1`（有答案但不可归因）同码**。
> "算不了"与"有答案但不确定"必须是两个语义。

### 5.2 判定态判据（精确口径）

| 判定态 | 判据 |
|---|---|
| `UNAMBIGUOUS` | 在该平台该域下，该数字**唯一**对应一个常量 |
| `AMBIGUOUS-SAME-PLATFORM` | 同平台同域内，**一个数字对应多个常量名**（Linux `6` → `SIGABRT`/`SIGIOT`） |
| `AMBIGUOUS-CROSS-PLATFORM` | **未给平台的数字查询**，且各平台命中集合不一致，或某已覆盖平台上没有这个值（数字 `11` → Linux `EAGAIN`/`EWOULDBLOCK`、macOS `EDEADLK`、Windows `EAGAIN`） |
| `PLATFORM-ABSENT` | 给了常量名，但该平台**无此常量**（macOS 无 `SIGSTKFLT`） |
| `UNKNOWN` | 编目中无此值 |

> **⚠️ 跨平台歧义的样本必须是「数字查询」，不能是「名字查询」**（M2 定稿，关闭 `plan/06` G6）。
>
> 本表原来把 `EAGAIN → 11/35/11` 举作 `AMBIGUOUS-CROSS-PLATFORM` 的样本 —— **那是错的**：
> 问 `EAGAIN` 问的是"这个名字有没有定义"，四个平台都有，答案唯一，所以它判
> `UNAMBIGUOUS`（exit 0）并逐平台列出 11/35/11/11。
> **"同一个名字在不同平台数值不同"是事实，不是歧义** —— 歧义的定义是"一个问题有两个答案"，
> 不是"两个平台给不同的数"。
>
> 判据 = **"这个查询问的是'数字是什么'，还是'名字在不在'？"**
> 只有前者才会因为跨平台而失去唯一性。这一条与 `plan/03` §2.2 序 7/序 8 是同一套口径。

### 5.3 退出码归因判据

| 归因 | 判据 |
|---|---|
| `NORMAL-EXIT` | `0 ≤ code ≤ 127` 且不属于 `64–78` 约定段 |
| `SYSEXITS(n)` | `64 ≤ code ≤ 78`，**须标注"约定非标准"** |
| `SIGNAL-KILLED(n)` | `code = 128 + n` **且 `n` 在该平台确实是有效信号** |
| `UNATTRIBUTABLE` | 其余全部，**含 `exit 1`** |

> **硬纪律**：`128+n` 检查**必须验证 `n` 是该平台有效信号**。
> Linux `SIGKILL`=9 → `137` 成立；但若平台无 `n` 号信号，则 `128+n` **不成立**，须判 `UNATTRIBUTABLE`。
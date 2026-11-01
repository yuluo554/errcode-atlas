# data/gaps.md — 缺口登记（逐行可查，三态可数）

> **纪律**：任何数值**无出处即不入编目**，改记到本表。
> 布局门 `LAYOUT.GAPS` 扫的是 `plan/06` 的缺口表；本表是**数据侧的缺口**，两者用途不同：
> `plan/06` 记项目级缺口（里程碑/口径），本表记"哪条常量为什么没进编目"。
>
> 三态口径（`data/README.md` §4 覆盖度门槛的配套）：**全录** / **部分录** / **未录**。
> 每行必须填 `状态` 与 `为什么没入` —— "待 M1" 不是理由，是进度。
>
> **本表在 M1 已按实测算过一遍**：每一行的"未入"清单都由 `tools/extract_catalog.py --report`
> 数出来（它把原文里每个 `#define` 与入仓条目对账），不是手写的。复现命令见每行的「补的路径」。

## 1. 逐条缺口

| 常量 / 范围 | 平台 | 域 | 状态 | 为什么没入编目 | 补的路径 |
|---|---|---|---|---|---|
| Linux errno 基础段 34 条（`errno-base.h`） | linux | errno | 全录 | — | `py -3.12 tools/extract_catalog.py --report` 应报 raw 34 / distinct 34 |
| Linux errno 扩展段 102 条（`errno.h`，含 4 组别名） | linux | errno | 全录 | — | 同上，应报 raw 102 / distinct 102 |
| `SIGLOST` | linux | signal | 未录 | 原文第 43 行**定义在注释块里**（`/* #define SIGLOST 29 */`），不是有效定义；其值与 `SIGIO` 同为 29，取用会造出假唯一 | 不是缺口：需该名时按 `PLATFORM-ABSENT` 之外的"上游未启用"处理；重新核对上游若取消注释再补 |
| `SIGRTMIN` / `SIGRTMAX` | linux | signal | 未录（**刻意**） | 原文第 49 行自述「These should not be considered constants from userland」；且 `SIGRTMAX` 的值是 `_NSIG`，实际数字由 libc/架构再定。硬编进来会造出跨架构的假精确 | 若将来要收，须按架构分别建条目并各带出处；当前不装作知道 |
| `SIGSTKSZ` / `MINSIGSTKSZ` | linux / macos | signal | 未录（**不是信号**） | 它们是备用信号栈的**字节数**（linux 8192、macos 131072），不是信号编号。混进信号域会让 `128+n` 算出伪归因 | 不是缺口：不入信号域。若将来要回答"栈多大"另开域 |
| macOS 内核伪错误 10 条（`ERESTART` / `EJUSTRETURN` / `ERECYCLE` / `EREDRIVEOPEN` / `EKEEPLOOKING` / `EDATALESS` / `ECVCERORR` / `ECVPERORR` / `EQSUSPENDED` / `EQCONGESTED`） | macos | errno | 未录（**结构性**） | 原文第 273–295 行在 `#ifdef KERNEL` 里，且多处 `#ifdef KERNEL_PRIVATE` / `BSD_KERNEL_PRIVATE` / `PRIVATE`。**用户态程序拿不到这些值**，录进来会让用户以为 `-1`/`-2` 是合法 errno | 不是缺口：内核内部约定，不属本项目范围（域范围见 `plan/00` §2.1） |
| `EOPNOTSUPP`（第 156 行，值 45） | macos | errno | 部分录 | 该行在 `#if !__DARWIN_UNIX03 && !defined(KERNEL)` 里；用户态默认 `__DARWIN_UNIX03 = 1`，走第 253 行的 `102`。**入编目的是 102 那条**，45 那条属非 UNIX03 旧编译环境 | 已按用户态默认口径处理；`tests/test_catalog_data_m1.py` 钉死 `EOPNOTSUPP=102` / `ENOTSUP=45` |
| `SIGPOLL`（第 91 行） | macos | signal | 未录 | 只在 `defined(_POSIX_C_SOURCE) && !defined(_DARWIN_C_SOURCE)` 时可见；默认环境走 `#else` 分支（`SIGIOT` / `SIGEMT`）。macOS 用户态下 7 号是 `SIGEMT`，不是 `SIGPOLL` | 若确实需要 POSIX 口径，须新增一个"编译环境"轴；当前不混入默认口径 |
| `SIGEV_*` 4 条 / `SIG_DFL` `SIG_IGN` `SIG_ERR` `SIG_HOLD` / `SIG_BLOCK` `SIG_UNBLOCK` `SIG_SETMASK` | macos | signal | 未录（**不是信号**） | 分别是 sigevent 的取值、信号处理函数取值、`sigprocmask` 的动作参数。都不是信号编号 | 不是缺口：域边界问题。要覆盖需另开域 |
| macOS errno 用户态 109 条 | macos | errno | 部分录 | 原文 120 行 `#define E*` / 119 个不同名字，去掉 10 条内核伪错误（上一行）即为 109 条入编目。原始数字与文档 E3 的 119 一致 | `py -3.12 tools/extract_catalog.py --report` 应报 raw 120 / catalog 109 |
| macOS 信号 32 条 | macos | signal | 全录（用户态默认口径） | — | 同上，应报 catalog signal 32 |
| `SIGSTKFLT` | macos | signal | 未录（**结构性缺失**） | 该平台**没有**这个信号；不是"查不到" | 不是缺口：入编目后由 `PLATFORM-ABSENT` 承载（`data/README.md` §5.2），`tests/test_catalog_data_m1.py` 有专条断言 linux=16 / macos 无 |
| Windows 信号（Node 11 项 / Python 7 项） | win32-node / win32-python | signal | 部分录 | Windows **没有 POSIX 信号集合**，两个运行时各自只导出能处理的那几个（Node 含 `SIGWINCH`，Python 不含；两者 `SIGABRT` 都是 22）。这是平台事实，不是抽取遗漏 | 不是缺口：`128+n` 在 Windows 上本来就不成立，判定层以编目信号表为准（`plan/03` §3.3） |
| `128+n` 原典 | 全平台 | exit | 部分录（**核过：POSIX 确实没有这条**） | 已核对 POSIX `wait()` 页原文：标准只规定 `WIFSIGNALED` / `WTERMSIG` 取信号号，**没有任何 `128+n` 公式**。`WEXITSTATUS` 只取 `_exit()` 参数的**低 8 位**。所以 `128+n` 确系 shell 实现惯例 | 处置 = `gray` 强度 + 报告强制标"惯例非标准"（`plan/04` §2.3；`selftest._check_gray_markers` 断言字样存在）。原典页码见 `data/README.md` §1.3 X3 |
| `sysexits` 64–78 | 全平台 | exit | **全录**（15 条，`diff` 强度） | — 官方文档页可锚段落，**不是标准正文** | M2 已落 `exit` 域，逐条带 `#EX_*` 段锚；报告强制标"约定非标准"（`selftest._check_gray_markers` 断言字样存在）。复现：`tools/extract_catalog.py --report` 应报 `sysexits.yaml {'exit': 15}` |
| Node 错误码清单 | linux / macos / win32-node | node | **全录**（435 条 = 现行 383 + 弃用 52） | — 页面版式未变（`Legacy Node.js error codes` 小节仍在，抽取器把它当分界锚） | M2 已落 `node` 域，逐条带页内段锚。**不是 `errno` 域**（`ERR_*` 无数字码值，见 `data/README.md` §2.4）。复现：`--report` 应报 `node-errors.yaml {'node': 435}` + `node 页小节数 435（其中 Legacy 小节 52）` |
| `ERR_*` 在 `win32-python` 上不存在 | win32-python | node | 未录（**结构性**） | 该运行时是 Python，不抛 Node 的异常码。给它在编目里编一条会让 `PLATFORM-ABSENT` 这个一等公民结论消失 | 不是缺口：`node` 域**刻意不挂 `win32-python` 轴**（`data/README.md` §2.3）。要的是 `PLATFORM-ABSENT`，不是一条编造的条目 |
| `EX_USAGE` 等 15 条的"是否标准" | 全平台 | exit | 部分录（`gray` 口径） | 官网原文第一句即 "non-portable error codes. Do not use them."（不可移植、不推荐使用）。**它是约定，不是 POSIX 标准正文** | 处置 = 码值与名字按 `diff`（有段锚），"是否标准"按 `gray`（报告标"约定非标准"）。`plan/04` §2.3 已定 |
| `128+n` 原典 | 全平台 | exit | 部分录（**核过：POSIX 确实没有这条**） | 已核对 POSIX `wait()` 页原文：标准只规定 `WIFSIGNALED` / `WTERMSIG` 取信号号，**没有任何 `128+n` 公式**。`WEXITSTATUS` 只取 `_exit()` 参数的**低 8 位**。所以 `128+n` 确系 shell 实现惯例 | 处置 = `gray` 强度 + 报告强制标"惯例非标准"（`plan/04` §2.3；`selftest._check_gray_markers` 断言字样存在）。原典页码见 `data/README.md` §1.3 X3 |

## 2. 计数口径（本表自己也要可数）

- `未录` / `部分录` 行数由本表构造算出，**不写死常量**（新增一行即变）。
  `tests/test_data_gaps.py` 解析本表并断言"每行都有状态与补的路径"，以及三态取值封闭。
- 「为什么没入编目」一栏写的是**原因**，不是进度代号；每一行的原因都能被
  `py -3.12 tools/extract_catalog.py --report` 的输出对上（该报表逐条打印被排除的 `#define`）。

## 3. 关闭缺口的写法

关闭时**只描述不点名文件名**（写"记在发布留档的 §二"），否则布局门的标识符剥离逻辑要额外处理——
这是踩过的假红形态（`plan/06` §3 的同一句）。

> **本表 M1 的关闭动作**：M0 留的 6 行"（全部）未录 / 同上"已按实测**逐行改写为具体理由**
> （内核伪错误 / 非信号宏 / 有条件可见分支 / 平台结构性缺失 / 刻意不收）。"（全部）未录"
> 这类行不再存在 —— 因为编目已经全录了，留它会让"未录"这个状态从此不能被信任。
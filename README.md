# errcode-atlas

> 给 `EACCES`、`ECONNREFUSED`、`exit 137`、`errno 28` 这类问题一张**带出处、能机器校验、并且明说"这里不可唯一归因"**的判定表。
>
> 版本：`v0.1.0`（M0 骨架）。状态与里程碑见 `plan/05-里程碑与发布.md`。

**给定「一个数字 + 一个平台 + 一个语境」，它能不能被唯一归因；能，归到哪一条；不能，为什么要说"不能"。**

不是一个错误码字典检索工具，也不是"帮我修这个 bug"。本工具回答的只有一件事：**这个数字在这个平台上到底是什么意思**。

---

## 为什么需要它

同一台机器、同一时刻，两个运行时对**同一个错误名**给出两个数值：

```console
$ node -e "console.log(require('os').constants.errno.EADDRINUSE)"
100

$ py -c "import errno; print(errno.EADDRINUSE)"
10048
```

同一台机器、同一时刻，三个平台对**同一个常量名**给出三个数值（逐条读自公开头文件，见 `data/README.md` §1）：

| 常量 | Linux | macOS | Windows（Node / VC） |
|---|---:|---:|---:|
| `EAGAIN` | **11** | **35** | 11 |
| `EADDRINUSE` | **98** | **48** | **100** |
| `ECONNREFUSED` | **111** | **61** | **107** |

**同一列的四个数字，没有一个能跨平台通用。** 而模型的默认行为是"记住一个"然后到处用。

`exit 137` 也一样必须先问平台：POSIX 惯例是 `128 + n`，`128 + 9 = 137` → `SIGKILL`。
但这**只是惯例，不是标准**，而且 `SIGSTOP` 在 Linux 是 19、在 macOS 是 17 —— 同一个 `147` 归到的不是同一个信号。

---

## 判定结果有五个态（不是"对/错"两态）

| 判定态 | 含义 |
|---|---|
| `UNAMBIGUOUS` | 该数字在该平台该域下唯一对应一个常量 |
| `AMBIGUOUS-SAME-PLATFORM` | 同平台同域内一数多名（Linux `SIGABRT` 与 `SIGIOT` 同为 6） |
| `AMBIGUOUS-CROSS-PLATFORM` | 给了数字但未给平台，且各平台不一致 |
| `PLATFORM-ABSENT` | 该常量在该平台**不存在**（macOS 无 `SIGSTKFLT`） |
| `UNKNOWN` | 编目内无此值（可能为私有/自定义错误码） |

`AMBIGUOUS-*` 与 `PLATFORM-ABSENT` **不是失败态，是正确的判定结果**。
强制给出一个唯一答案比不答更有害 —— 这是本项目全部设计的出发点。

---

## 安装与用法

M0 骨架期：编目尚未填充（`data/catalog/*.yaml` 只有表头），因此判定会返回 `UNKNOWN`。
这与"工具坏了"是两个不同的信号：`UNKNOWN` 的退出码是 **3**，"有答案但不可归因"是 **1**。

```bash
py -3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"

export PYTHONPATH=src
py -3.12 -m errcode_atlas --version
py -3.12 -m errcode_atlas build --check
py -3.12 -m errcode_atlas explain 98 --platform linux
py -3.12 -m errcode_atlas exitcode 137 --platform linux
```

装上之后 `errcode-atlas` 就是入口：

```bash
errcode-atlas explain EADDRINUSE --platform linux
errcode-atlas exitcode 1 --platform linux --json
errcode-atlas build --check
errcode-atlas selftest
errcode-atlas bench
```

### 平台取值

`linux` / `macos` / `win32-node` / `win32-python`。

**Windows 必须二选一**：`--platform win32` 会被拒绝（退出码 4）并提示两个视角 ——
因为同一台机器上 Node 与 Python 给的 errno 数值**不同**（上面那个 `100` / `10048`）。

### 本工具自身的退出码

见 `data/README.md` §5.1（唯一定义处）。

| 退出码 | 含义 |
|---:|---|
| `0` | 判定完成，结果可唯一归因 |
| `1` | 判定完成，结果**不可唯一归因**（`AMBIGUOUS-*` / `PLATFORM-ABSENT` / `UNATTRIBUTABLE`） |
| `3` | 算不了（编目未覆盖此值 / 域不支持） |
| `4` | 用法错误 |

`1` 与 `3` 必须是两个码：**"有答案但不确定"与"我不知道"不是一件事**。

---

## 开发

```bash
py -3.12 tools/check_sprint_layout.py     # 布局门
py -3.12 tools/check_desensitized.py      # 脱敏门
py -3.12 tools/verify_gates.py            # 两道门的变异验证（逐组必须变红）
py -3.12 tools/build_catalog.py --check   # 生成器冻结态校验
py -3.12 -m pytest -q
```

### 前置条件

* **就地复算编目**：先跑 `py -3.12 tools/build_catalog.py --out src/errcode_atlas/data`
  （`data/catalog/*.yaml` 是唯一编目真相源；`src/errcode_atlas/data/catalog.json` 是它的冻结产物）。
* 本仓使用 `src` 布局：不装包直接跑时 **必须** `PYTHONPATH=src`（CI 每个 job 都设了）。
* 无 `.git` 的解包树同样可跑全部命令（门与测试都不读 git 元数据）。

---

## 免责

> 本工具给出的是**公开头文件与官方文档的编目结果**，不是对任何具体崩溃的成因判断。
> `UNATTRIBUTABLE` / `AMBIGUOUS` 是**正确且常见**的结论，**不代表工具失效**。
> `128+n` 是 **POSIX 惯例而非标准**，`sysexits` 是**约定而非标准** —— 两者在报告中都如此标注。

**纯本地，零上传**：编目随包分发，运行期不联网；报告不含用户路径与进程信息。

---

## 文档索引

| 文件 | 内容 |
|---|---|
| `plan/01-题目文档.md` | 题目与边界 |
| `plan/02-架构与技术选型.md` | 分层、决策 D1–D8 |
| `plan/03-模块详设.md` | 四模块与判定顺序 |
| `plan/04-数据计划.md` | 数据来源与真值纪律 |
| `plan/05-里程碑与发布.md` | 里程碑 DoD 与已知未验证项 |
| `data/README.md` | **口径唯一定义处**（§5） |
| `AGENTS.md` | 仓库锚点：新对话第一件事 |

## License

MIT
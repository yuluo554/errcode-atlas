# data/gaps.md — 缺口登记（逐行可查，三态可数）

> **纪律**：任何数值**无出处即不入编目**，改记到本表。
> 布局门 `LAYOUT.GAPS` 扫的是 `plan/06` 的缺口表；本表是**数据侧的缺口**，两者用途不同：
> `plan/06` 记项目级缺口（里程碑/口径），本表记"哪条常量为什么没进编目"。
>
> 三态口径（`data/README.md` §4 覆盖度门槛的配套）：**全录** / **部分录** / **未录**。
> 每行必须填 `状态` 与 `为什么没入` —— "待 M1" 不是理由，是进度。

## 1. 逐条缺口

| 常量 / 范围 | 平台 | 域 | 状态 | 为什么没入编目 | 补的路径 |
|---|---|---|---|---|---|
| （全部） | linux | errno | 未录 | M0 骨架期：只有表头，逐条抽取在 M1 | `gh api repos/torvalds/linux/contents/include/uapi/asm-generic/errno-base.h` |
| （全部） | linux | signal | 未录 | 同上 | `gh api repos/torvalds/linux/contents/include/uapi/asm-generic/signal.h` |
| （全部） | macos | errno | 未录 | 同上 | `gh api repos/apple-oss-distributions/xnu/contents/bsd/sys/errno.h` |
| （全部） | macos | signal | 未录 | 同上 | `gh api repos/apple-oss-distributions/xnu/contents/bsd/sys/signal.h` |
| （全部） | win32-node | errno | 未录 | 同上 | `node -e "console.log(require('os').constants.errno)"` |
| （全部） | win32-python | errno | 未录 | 同上 | `py -3.12 -c "import errno,json;print(json.dumps({k:getattr(errno,k) for k in dir(errno) if k.isupper()}))"` |
| `SIGSTKFLT` | macos | signal | 未录（**结构性缺失**） | 该平台**没有**这个信号；不是"查不到" | 不是缺口：入编目后由 `PLATFORM-ABSENT` 承载（`data/README.md` §5.2） |
| `128+n` 原典 | 全平台 | exit | 部分录 | 只有惯例，没有 POSIX 正文原句；`data/README.md` §1.3 X3 状态 ⬜ | M1 核对 `wait()` / `WEXITSTATUS` 原文后翻转或降级为 `gray` |
| `sysexits` 64–78 | 全平台 | exit | 部分录（`diff` 强度） | 官方文档页可锚段落，**不是标准正文** | M2 入 `data/catalog/sysexits.yaml`，报告强制标"约定非标准" |
| Node 错误码清单 | win32-node | errno | 未录 | M2 才落位 | M2 逐条抽 `nodejs.org/api/errors.html` |

## 2. 计数口径（本表自己也要可数）

- `未录` 行数由本表构造算出，**不写死常量**（新增一行即变）。
  `tests/test_data_gaps.py` 解析本表并断言"每行都有状态与补的路径"，以及三态取值封闭。

## 3. 关闭缺口的写法

关闭时**只描述不点名文件名**（写"记在发布留档的 §二"），否则布局门的标识符剥离逻辑要额外处理——
这是踩过的假红形态（`plan/06` §3 的同一句）。
# HANDOFF-M2 · 解析（Node 错误码 + `sysexits` + 编目→索引）

> **本文件是 M2 的入口文件**（按里程碑编号命名，不按"哪一棒写完它"命名 —— 见 `AGENTS.md` §一）。
> 状态：**M2 未开工**。下面是"进场须知 + 待办 + 口径"，不是"已完成"。
> 库里一律相对路径；本机绝对路径只出现在用户侧启动命令里。

---

## 一、当前进度 + 证据

**M2 尚未执行。** 本表如实为空，不预填 —— 预填就是给还没跑的棒编记录
（`AGENTS.md` §二 的判据② 正是为了挡住这件事）。

| 项 | 证据（命令 / 文件） |
|---|---|
| 入口文件本身 | 本文件（由 M1 收尾时落盘，满足"M1 收尾必须给 M2 留入口"） |
| M2 的三项产出 | **均未开始**：`sysexits.yaml` / `node-errors.yaml` / 编目→索引接线 |
| 起点基线（M1 交付，可直接用） | 编目 **599 条**（errno 515 / signal 84 / **exit 0**）；`build_catalog.py --check` → 0 |
| 起点门态 | 布局门 / 脱敏门 / `build_catalog.py --check` / `extract_catalog.py --check` / `verify_gates.py` 全绿 |

> **判据入口**：这一节在 M2 收尾时必须被真实证据填满，且每条都写"命令 / 文件"。
> 空着不行，写"已完成"却不给命令也不行 —— 那是本轮 M1 反复躲开的同一种坑。

---

## 二、当前事实·状态不变量（动手前必须知道）

1. **M1 的编目里 `exit` 域是 0 条**，所以现在任何 `exitcode` 归因都**不依赖编目**
   （`sysexits` 段走 `exitcode.SYSEXITS_NAMES` 这张代码内表，`128+n` 走编目信号表）。
   M2 一落 `sysexits.yaml`，`exit` 域就有条目了 —— **`entry_count` 会变，这是预期**，
   改完必须重跑 `build_catalog.py --out` 再 `--check`。
2. **数据链三步不可颠倒**：`fetch_sources.py`（联网）→ `extract_catalog.py`（零网络）→ `build_catalog.py`（冻结）。
   M2 要在**第一条**里加通路，在**第二条**里加共享域处理。
3. **`build_catalog.py` 的 `SHARED_FILES` 目前是空接线**：字典里已写好
   `{"sysexits.yaml": "exit", "node-errors.yaml": "errno"}`，但 `collect()` 只遍历
   `PLATFORM_FILES`（第 131 行 `for platform, filename in PLATFORM_FILES.items()`）。
   **共享文件根本不会被读到** —— 这是 M2 必须补的第一处接线。
4. **`SOURCE_DOC` 分支至今零实战**：`contract.SOURCE_REQUIRED_FIELDS["doc"] = ("url","anchor","verified_at")`，
   `catalog._validate_source` 里有校验，但**没有任何一条真实数据走过它**。
   `sysexits` 与 Node 错误码是它的首次实战 —— 校验写错会在这里第一次暴露。
5. **`source.url` 必须 `https://`**（`catalog._validate_source` 的硬判据），且 `anchor` 非空。
6. **判定层不许写死信号表，也不该开始写死错误码表**（K9 的延伸）：
   `exitcode.SYSEXITS_NAMES` 是"码值→名字"的**报告用**表，判定只看区间；
   M2 不要把 Node 错误码也造成第二张代码内表。
7. **`covered_platforms` 的分母会被共享文件直接影响**（K15）：
   `sysexits` 若只挂在某一个平台轴上，`explain` 的跨平台判定就会把另外三个平台算成
   "没有这个值" → 造出假 `PLATFORM-ABSENT`。**这是 M2 最危险的一处**，处置见 §三 第 3 条。
8. **`plan/06` G6 未关闭**：`plan/03` §2.2 的七行判定顺序表缺"名字 + 无平台 + 各平台值发散"
   这一行。M2 会引入更多跨平台同名的名字（`EX_USAGE` 等），**G6 不先拍板就会放大**。
9. **415 KB 的 HTML 不要进仓**：Node 错误码页抽取后只剩常量表，原文进 `_headers/`（已 `.gitignore`）。

---

## 三、待办（M2 执行序）

0. **先读并处置 `plan/06` G6**（优先于下面全部）：`plan/03` §2.2 缺一行判定顺序。
   M2 进去之后跨平台同名只会更多，这道口子会放大。要么给 §2.2 补第 8 行，
   要么把 `data/README.md` §5.2 那句举例改口，**不许两边都留着**。
1. **`fetch_sources.py` 加非 `contents/` 通路**：`sysexits` 页与 `nodejs.org/api/errors.html`
   不是任何 GitHub 仓库里的文件，现有 `fetch_one` 只认 `repos/<o>/<r>/contents/<path>`。
   两条可选路径：加一个 `--url` 通路（仍然不吃 raw 链接、也不吃本地代理），
   或明确登记为"手工取 + 记 sha256 进 `SOURCES.json`"。
   **不许默默降级成"凭记忆抄"** —— 那会毁掉"每条数值能重跑出来"这条纪律。
2. **`data/catalog/sysexits.yaml`**：64–78 共 15 条，`kind: doc`，`url` 指向 OpenBSD `sysexits` 页，
   `anchor` 写段锚。注意报告措辞必须是**"约定非标准"**（`contract.GRAY_MARKERS`），
   由 `selftest._check_gray_markers` 断言。
3. **`sysexits` 的平台归属（这是设计决定，别顺手定）**：
   `exit` 域目前 `covered_platforms("exit") == ()`。两种落法：
   - **A（建议）**：`sysexits.yaml` 作为共享文件，在**四个平台轴上都登记**。
     理由：`sysexits` 对四个平台的进程都成立；这样 `covered_platforms("exit")` = 4 个平台，
     跨平台判定不会伪造"另外三平台没有"的假 `PLATFORM-ABSENT`。
   - **B**：新增一个"全平台"轴。代价 = 改 `contract.PLATFORMS`，而那会动五态/平台封闭性，
     M0 的 K 口径里"四平台值已冻结"要跟着改 —— **不建议**。
   > 无论选哪个，都要在 `data/README.md` 里写明，否则下一棒无法判断这是设计还是失误。
4. **`data/catalog/node-errors.yaml`**：`nodejs.org/api/errors.html` 逐条抽 `ERR_*`（157 类量级），
   `kind: doc`。**注意它和 errno 不是一回事**：`ERR_*` 是 Node 自己抛的异常码，
   与 OS errno 无映射关系。落进哪个域要先定（建议新增 `node` 域或明确标 `errno` 域的"非 OS 码"子类），
   **不要硬塞进 errno 域污染 OS errno 的判定**。
5. **接线 `SHARED_FILES`**：`collect()` 要读共享文件，且**每条要能挂到多个平台轴**。
   注意 `build()` 的 `entry_count` 由构造算出 —— 共享条目按轴重复计入时，
   分母会变成"条目数 × 平台数"，要确认那是你要的语义（若不是，得在 manifest 里分开记）。
6. **编目→查询索引**：`catalog.build_indexes` 已建好三索引，M2 只需确认共享条目进索引后，
   `names_at` / `value_of` / `covered_platforms` 三个查询面的行为符合 §二 第 7 条。
7. **`UNKNOWN` 路径补齐**：现在只有"越界数字 → exit 3"。M2 要补
   **"编目有该域但没有该值"** 的用例（`explain 99999 --platform linux --domain exit`）。
8. **`data/gaps.md` 改状态**：`sysexits` 与 Node 错误码两行从"未录/部分录"改为实际状态，
   关闭理由按"M2 实测"写，不写"待 M2"。
9. **收尾**：DoD 验证 → `plan/00`/`plan/05`/`plan/06` 状态回写 → **写 `plan/HANDOFF-M3.md`**
   （M3 的入口，不是 M2 的收官单）→ commit。

---

## 四、既定口径清单（K 编号 —— 动了会打挂测试的约定）

M0 的 K1–K15 与 M1 的 K16–K19 **全部仍然有效**，另加 M2 新增：

| K | 口径 | 动了会红的东西 |
|---|---|---|
| K20 | **共享条目必须能让 `covered_platforms(domain)` 覆盖到全部注册平台** —— 否则假 `PLATFORM-ABSENT` | `tests/test_explain.py` 的跨平台用例 |
| K21 | **`kind: doc` 的条目拿不到 `hard`**（`contract.SOURCE_MAX_STRENGTH` 已写死 `diff`），且 `url` 必须 https、`anchor` 非空 | `tests/test_catalog.py` 的出处校验组 |
| K22 | **`exit` 域判定不许依赖编目条目是否存在**（`sysexits` 是区间判定 + 报告用名字表），编目只提供"这个名字存在"的事实 | `selftest._check_gray_markers`、`tests/test_exitcode.py` |
| K23 | **Node 的 `ERR_*` 不许混进 OS errno 域** —— 它们不是 errno，混进去会让 `explain 100` 之类开始编造 | 待 M2 落测试（**本组现在还没有测试，落位时必须同笔补上**） |

---

## 五、本机环境坑（只写实测过的，2026-11-01 续）

M0 §五、M1 §五 全部仍有效，另加：

- **`fetch_sources.py` 的 `fetch_one` 只认 `contents/` 接口**：给 HTML 页取数必须另开通路，
  且**同样不许走 `raw.githubusercontent.com`**（本机 HTTP 000）。
- **本机 Bash 用 `>` 重定向写仓库文件会被本地安全钩子拦下**：取数与抽取一律让脚本自己写文件。
- **`plan/HANDOFF-M<k>.md` 是入口文件名，不是收尾单名**：M2 收尾要产出的是 `HANDOFF-M3.md`。
  本项目**实测踩过**：M1 收尾时没写 `HANDOFF-M2.md`，而首版布局门只遍历已 ✅ 的里程碑，
  于是"漏了当前棒入口"完全看不见（门报"2 份交接单齐 全绿"）。
  现在门有 `L6c`（当前入口缺失）与 `L6d`（超前入口）两组变异守着。

---

## 六、DoD 逐项 checklist

> **全部未打勾** —— M2 未开工。这一节是**验收清单**，不是成绩单。
> 收尾时才允许逐项打勾，且每项要能指到命令或文件。

- [ ] `sysexits.yaml` 入编目（64–78 共 15 条），`kind: doc`，抽样对账一致
- [ ] `node-errors.yaml` 入编目，`ERR_*` 与 OS errno **不混域**
- [ ] `build_catalog.py` 的 `SHARED_FILES` 接线完成（`collect()` 真读共享文件）
- [ ] `sysexits` 的平台归属已定并写进 `data/README.md`（`covered_platforms("exit")` 不再是空集）
- [ ] 索引在装载期一次建好，判定层无二次扫描
- [ ] `UNKNOWN` 路径两种形态都可用（越界值 / 域内有但无此值），且都 exit 3
- [ ] `plan/06` G6 已关闭（§2.2 补行 **或** §5.2 改口，二选一）
- [ ] `pytest` 双通道全绿；`verify_gates.py` 全组 CAUGHT（含新增 L6c/L6d）
- [ ] `build_catalog.py --check` 与 `extract_catalog.py --check` 双跑逐字节一致
- [ ] **`plan/HANDOFF-M3.md` 已落盘**（M3 入口；不是 M2 收官单）
- [ ] ~~CI 绿~~ → 仍不适用：无远端、未推送（`plan/05` §4 U1）

---

## 七、关键命令速查

```bash
# 门（对外）
py -3.12 tools/check_sprint_layout.py
py -3.12 tools/check_desensitized.py

# 门自己是否在验东西（逐组变异；M2 起共 19 组）
py -3.12 tools/verify_gates.py

# 数据链（三步，顺序不能颠倒）
py -3.12 tools/fetch_sources.py --out _headers        # 1) 取原文（联网，gh api）
py -3.12 tools/fetch_sources.py --check               #    已取件 sha256 对账
py -3.12 tools/extract_catalog.py --out data/catalog   # 2) 抽取 YAML（零网络）
py -3.12 tools/extract_catalog.py --check              #    与仓库 YAML 逐字节比对
py -3.12 tools/extract_catalog.py --report             #    取数事实 + 被排除项
py -3.12 tools/build_catalog.py --out src/errcode_atlas/data   # 3) 冻结 JSON
py -3.12 tools/build_catalog.py --check

# 判定面（M1 基线：exit 域仍是空的）
PYTHONPATH=src py -3.12 -m errcode_atlas explain 6 --platform linux --domain signal
PYTHONPATH=src py -3.12 -m errcode_atlas explain SIGSTKFLT --platform macos --domain signal
PYTHONPATH=src py -3.12 -m errcode_atlas exitcode 137 --platform linux
PYTHONPATH=src py -3.12 -m errcode_atlas exitcode 64 --platform linux    # SYSEXITS，必带"约定非标准"

# 测试（两条通道）
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 py -3.12 -m pytest -q
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 py -3.8 -m pytest -q
```
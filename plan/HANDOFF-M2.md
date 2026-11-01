# HANDOFF-M2 · 解析（Node 错误码 + `sysexits` + 编目→索引）

> **本文件是 M2 的入口文件**（按里程碑编号命名，不按"哪一棒写完它"命名 —— 见 `AGENTS.md` §一）。
> 状态：**M2 已完成（✅）**。§一 已按实测填满，§三 的待办逐条有处置，§六 的 checklist 已逐项打勾。
> 下一棒入口见 `plan/HANDOFF-M3.md`。
> 库里一律相对路径；本机绝对路径只出现在用户侧启动命令里。

---

## 一、当前进度 + 证据

| 项 | 证据（命令 / 文件） |
|---|---|
| 入口文件本身 | 本文件（由 M1 收尾时落盘，满足"M1 收尾必须给 M2 留入口"） |
| `fetch_sources.py` 网页通路 | 新增 `Source.url` → `fetch_url()`：`py -3.12 tools/fetch_sources.py --out _headers` 报 **7 份**（5 头文件 + `sysexits.html` 12,127 B + `node-errors.html` 415,009 B）；`--check` → 7 份 sha256 一致 |
| `data/catalog/sysexits.yaml` | **15 条**（64–78 连续），`kind: doc` + `#EX_*` 段锚；`extract_catalog.py --report` 报 `sysexits.yaml {'exit': 15}` |
| `data/catalog/node-errors.yaml` | **435 条** = 现行 383 + 弃用 52；`kind: doc` + 页内锚；`--report` 报 `node-errors.yaml {'node': 435}` / `node 页小节数 435（其中 Legacy 小节 52）` |
| `SHARED_FILES` 接线 | `build_catalog.collect()` 现在真读共享文件并按键 `SHARED_SPREAD` 展开到多平台轴；冻结件 `entry_count` 里 `exit` 60 / `node` 1305 不再是 0 |
| 两个分母分开记 | 冻结编目：逐平台 **1964** 条 / 去重 **702** 条（errno 215 / signal 37 / exit 15 / node 435）；manifest 同时记 `entry_count` + `distinct_count` + `shared_files` |
| 索引装载期一次建好 | `Catalog.by_key` / `covers` / `covered` 都在 `build_indexes()` 建好；`entry_for` / `covered_platforms` 改成查表。判据两条：清空 `entries` 后查询面仍答得出来 + AST 断言判定层不遍历 `.entries` |
| `UNKNOWN` 两形态 | `explain 99999 --domain exit` → UNKNOWN/3；**`explain 1 --domain exit`**（域内有条目、无此值）→ UNKNOWN/3；`explain ERR_<不存在> --domain node` → UNKNOWN/3 |
| G6 已关闭 | `plan/03` §2.2 补序 7（名字+无平台+值发散 → UNAMBIGUOUS）与序 8（某平台没有 → PLATFORM-ABSENT）；`data/README.md` §5.2 举例改成**数字** `11`；`plan/00` §6 招牌动词表同笔改正 |
| 起点基线（M1 → M2） | M1 交付 599 条（errno 515 / signal 84 / exit 0）→ M2 交付 6 个源文件 / 1049 条 |
| 复现性 | `extract_catalog.py --check` **双通道（3.12 / 3.8）** 都报「6 个文件 / 1049 条」一致；`build_catalog.py --check` 一致 |
| 新增测试 | `tests/test_catalog_m2.py`（25 条）：原文逐条对账 / K20 / K21 / K22 / K23 / UNKNOWN 两形态 / 索引无二次扫描 |
| 全量测试双通道 | `py -3.12` **231 passed**；`py -3.8` **230 passed + 1 skip**（3.10+ 属性） |
| 两道门 + 变异验证 | 布局门 / 脱敏门全绿；`verify_gates.py` **19 组全 CAUGHT**，还原后复绿 |

**本轮抓到并修掉的真缺陷（不是"写完就绿"）**：

| # | 形态 | 是谁抓出来的 |
|---|---|---|
| ① | Node 页正则 `class=mark id=([a-z0-9_]+)>` 漏了 `id=xxx href=...` 中间的空格 → **435 节解析出 0 条** | `collect_shared()` 的"读到 0 条即错误"兜住了 —— 没有静默写出空表 |
| ② | 切到 `</section>` 时那 10 个字符已被切掉 → 每组的**最后一条**（`MODULE_NOT_FOUND`）释义为空串 | `test_every_yaml_entry_has_complete_source_block` 报"缺 description_zh" |
| ③ | `build()` 收到的是 `SHARED_FILES`（文件名→域）而不是 `SHARED_SPREAD`（文件名→平台轴）→ manifest 把 `"exit"` 当成列表展开成 `["e","x","i","t"]` | `test_build_catalog_collects_shared_files` |
| ④ | `entry_for` 一直是线性扫描 —— "索引在装载期一次建好"在它身上是空话 | 写 M2 索引测试时发现，改成 `by_key` 查表 |
| ⑤ | 无值域（`node`）逐平台渲染成 `None`，与"查不到值"同形 | CLI 实跑时看到 `PLATFORM-ABSENT` 的逐平台表全是 `None`，改成"（无数字码值）" |
| ⑥ | 测试自己写的 sysexits 正则 `<a[^>]*>[^<]*</a>` 匹配 0 条（`<a>` 里还套着 `<code>`） | 同上 —— 正好证明"两条通路各自在验" |

> **判据入口**：这一节在 M2 收尾时必须被真实证据填满，且每条都写"命令 / 文件"。
> 空着不行，写"已完成"却不给命令也不行 —— 那是本轮 M1 反复躲开的同一种坑。
> **本节已填**（2026-11-01，M2 收尾）。

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

## 三、待办（M2 执行序）——**逐条处置**（收尾时回填）

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

**处置结果（收尾回填）**：

| # | 待办 | 结果 |
|---:|---|---|
| 0 | `plan/06` G6 | **已关闭**：`plan/03` §2.2 补序 7/序 8，`data/README.md` §5.2 举例改口为数字 `11`，`plan/00` §6 同笔改正 |
| 1 | `fetch_sources.py` 非 `contents/` 通路 | **走 `--url` 通路**（不吃 raw、显式禁本地代理、记 sha256）：7 份原文，`--check` 一致 |
| 2 | `sysexits.yaml` | **15 条**，`kind: doc`（`SOURCE_DOC` 首次实战），`anchor: #EX_*` |
| 3 | `sysexits` 平台归属 | **选 A 的扩展版**：`exit` 四轴全挂；`node` 三轴（不挂 `win32-python`）。理由见 `data/README.md` §2.3 |
| 4 | `node-errors.yaml` | **新增独立 `node` 域**（不是 `errno` 子类）：435 条，无 `value` |
| 5 | 接线 `SHARED_FILES` | **已接线**；`entry_count`（逐平台）与 `distinct_count`（去重）**分开记**，manifest 另记 `shared_files` |
| 6 | 编目→查询索引 | 三索引扩成六个结构（`by_value`/`by_name`/`signals`/`covers`/`covered`/`by_key`），全部装载期建好 |
| 7 | `UNKNOWN` 路径补齐 | **两形态都通**：`99999`（越界）与 `1 --domain exit`（域内有条目、无此值）；另加 `node` 域无此名 |
| 8 | `data/gaps.md` | `sysexits` → **全录**、Node 错误码 → **全录**；另加三行（`win32-python` 结构性不录 / 约定非标准 / `128+n` 原典） |
| — | **本轮新增**（原 §三 未列） | ① 无值域（`VALUELESS_DOMAINS`）与两侧 fail-closed 校验；② 报告层无值占位符；③ `explain` 探测序按域分叉（数字不探测 `exit`/`node`）；④ `SYSEXITS_NAMES` 与编目双向一致断言 |

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

> **已逐项打勾**（2026-11-01，M2 收尾）。每项都能指到命令或文件 —— 见 §一。
> ~~CI 绿~~ 仍不适用：无远端、未推送。

- [x] `sysexits.yaml` 入编目（**15 条**，64–78 连续），`kind: doc` + `#EX_*` 段锚，逐条对账一致
- [x] `node-errors.yaml` 入编目（**435 条**），`ERR_*` 与 OS errno **不混域**（独立 `node` 域，无数字值）
- [x] `build_catalog.py` 的 `SHARED_FILES` 接线完成（`collect()` 真读共享文件，按 `SHARED_SPREAD` 展开）
- [x] `sysexits` 的平台归属已定并写进 `data/README.md` §2.3（`exit` 挂四轴 / `node` 挂三轴；`covered_platforms("exit")` 是四个平台）
- [x] 索引在装载期一次建好，判定层无二次扫描（`by_key` / `covers` / `covered` 查表；AST 守门）
- [x] `UNKNOWN` 路径两种形态都可用（越界值 / 域内有但无此值），且都 exit 3
- [x] `plan/06` G6 已关闭（**两边都做了且方向一致**：§2.2 补序 7/8 + §5.2 举例改口为数字查询）
- [x] `pytest` 双通道全绿（231 / 230+1skip）；`verify_gates.py` **19 组全 CAUGHT**（含 L6c/L6d）
- [x] `build_catalog.py --check` 与 `extract_catalog.py --check` 双跑逐字节一致（后者双通道）
- [x] **`plan/HANDOFF-M3.md` 已落盘**（M3 入口；不是 M2 收官单）
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
py -3.12 tools/fetch_sources.py --out _headers        # 1) 取原文（联网：gh api + https 网页通路，7 份）
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
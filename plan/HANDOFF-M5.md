# HANDOFF-M5 · 交付（`SKILL.md` 契约块 + 技术报告 + demo GIF + 裸 clone 可复现）

> **本文件是 M5 的入口文件**（按里程碑编号命名，不按"哪一棒写完它"命名 —— 见 `AGENTS.md` §一）。
> 状态：**M5 未开工**。下面是"进场须知 + 待办 + 口径"，不是"已完成"。
> 库里一律相对路径；本机绝对路径只出现在用户侧启动命令里。

---

## 一、当前进度 + 证据

**M4 已收口（✅），M5 尚未执行。** 下表是**真跑过的起点基线**，每行都指得到命令或文件。

| 项 | 证据（命令 / 文件） |
|---|---|
| M4 入口 | `plan/HANDOFF-M4.md`（已收口，其 §一 证据表可直接接手） |
| 基准语料（规模） | `fixtures/` **746 个 case / 1492 个文件**；`PYTHONPATH=src py -3.12 -m errcode_atlas bench` → `扫了 746 个 case，0 项不符`（中位 **0.22 s**） |
| 语料覆盖判据 | `tests/test_fixtures_meta.py`：五态计数 / `UNKNOWN` 两形态 / 分叉点 / sysexits 15 / **errno 4 轴 × 31** / **信号 66 条逐条** / **Node 435 逐条 + legacy 52 点名** / **反向样本压过歧义**（`UNAMBIGUOUS` 700 vs `AMBIGUOUS-*` 10） |
| 五态可达性 | `PYTHONPATH=src py -3.12 -m errcode_atlas selftest` → `selftest: 全绿` |
| 测试双通道 | `py -3.12` **4021 passed**；`py -3.8` **4020 passed + 1 skip**（3.10+ 属性） |
| 两道门 | `py -3.12 tools/check_sprint_layout.py` / `check_desensitized.py` 全绿 |
| 门自己在验东西 | `py -3.12 tools/verify_gates.py` → **19 组全 CAUGHT**，还原后复绿 |
| 数据链 | `fetch_sources.py --check`（7 份）/ `extract_catalog.py --check`（6 源 / 1049 条）/ `build_catalog.py --check`（1964 条 / 去重 702）三个 exit 0 |
| **M5 的三件交付物现状** | `SKILL.md` **不存在**；`docs/技术报告.md` **不存在**；`docs/demo/demo.gif` **不存在**（`docs/demo/` 目录为空） |
| `src/errcode_atlas/api.py` | **不存在**（`plan/00` §5 的四格表点名了 `api.py::run()` —— M5 必须落它，或把那张表改口，两处不许各说一套） |

> **判据入口**：这一节在 M5 收尾时必须被真实证据填满，且每条都写"命令 / 文件"。

---

## 二、当前事实·状态不变量（动手前必须知道）

1. **M5 是"交付面"，不是"判定面"**。判定层（`explain` / `exitcode`）、编目、语料在 M4 已收口。
   **M5 不许改判定逻辑**：改它会让 M3 的 `tests/test_judgement_order.py` 与 M4 的 746 case 一起动。
2. **契约块的位置与围栏是已定的**（`plan/03` §5）：`SKILL.md` 用
   `<!-- contract:begin -->` / `<!-- contract:end -->` 界定扫描面。断言要**集合相等**，
   不是包含（单向包含会漏"文档多写一个已废弃值"）。现有 `tests/test_contract.py` 断的是
   `data/README.md` §5 两张表 ↔ `contract.py`；**M5 要把同一套判据搬到 `SKILL.md` 契约块上**
   （新增测试，不是改现有的那几条 —— 现有那几条守的是口径真相源）。
3. **`plan/00` §5 四格表点名 `src/errcode_atlas/api.py::run()`，但该文件不存在**。
   M5 有两条路，**二选一且要一次性做完**：
   - 落 `api.py`（把 `explain` / `exitcode` / `bench` / `selftest` 收成一个 Python 级入口，供 Skill 调用）；
   - 或把 `plan/00` §5 那一格改成实际存在的入口（如 `cli.py::main`），并说明为什么不设 API 层。
   **不许留着"文档点名、实物没有"** —— 那正是 `LAYOUT.DOC_TOOLS` 同一族的缺陷（只是这一条打的是 `.py` 里的符号，不是 `tools/` 目录，所以门没抓到）。
4. **`fixtures/` 是 746 个目录**：`tests/test_fixtures_meta.py` 因此是 **3762 条**参数化 case。
   M5 若再加语料，pytest 时间会跟着涨（当前 3.12 全量 **12 s** 量级）。
5. **`bench` 只比对结果对象，不比对渲染文本**（K27）。技术报告里若要贴渲染样例，
   那是**文本**，`bench` 不管它 —— 报告里的样例必须**从真跑输出复制**，不许手写。
6. **`candidate_values` 只在"名字 → 号码"那一支出现**（M4 定）。数字查询的 case 不写它
   （恒等于查询值，写了就是自我参照）。M5 加 case 时别把这条口径搞反。
7. **`docs/demo/demo.gif` 必须是真跑录制**（`plan/05` §2 M5 DoD）。录之前先跑一遍命令，
   确认每条都 exit 0（否则 GIF 里就录进了红）。
8. **`data/README.md` §4.1 的四行 M4 证据已翻 ✅**；M5 不要回退它。
9. **`README.md` 不承载里程碑状态**（`AGENTS.md` §二）。M5 写 README 时**不许**加"当前进度 M5"。
10. **`py -3.8` 只验语法面**（`plan/06` §5）。M5 新写的测试若用 3.9+ 语法，3.8 通道会 SyntaxError
    —— 那不是"3.8 不支持本工具"，是本仓的下限纪律（`tests/test_version_floor.py` 有 AST 守门）。

---

## 三、待办（M5 执行序）

0. **先跑门**：`check_sprint_layout.py` / `check_desensitized.py` / `pytest` / `bench` / `selftest`。
   起点全绿，红了先修再干活。
1. **`SKILL.md` + 契约块双向断言**（这是 M5 的主体之一）：
   - 契约块声明四件事：五个 `verdict` / 四个 `attribution` / 四个平台值 / `0/1/3/4` 退出码；
   - 新增 `tests/test_contract.py` 里的**契约块**那几条（围栏扫描 + 集合相等 + 数量相等），
     **不改**现有的 `data/README.md` §5 那几条；
   - 契约块之外的正文档写**怎么用**（用户会怎么问 → 哪条命令 → 输出怎么读），
     但**不许复述数值**（数值只在 `data/README.md` §5 出现一次）。
2. **`plan/00` §5 四格表的 `api.py` 问题**：落 `api.py` 或改表（见 §二 第 3 条）。**二选一，做完就一致**。
3. **`docs/技术报告.md`**：判据写在 `plan/06` §1 的"综合表现 20"那一行 ——
   报告要能回答"为什么这么设计"，不是复述 README。样例一律**从真跑输出复制**。
4. **`docs/demo/demo.gif`**：真跑录制。至少覆盖五态各一次 + 一条 `exitcode`。
   **录制前逐条命令先手跑一遍**，确认 exit code 与预期一致（录进红比不录更糟）。
5. **裸 clone 可复现**：在**无 `.git`** 的导出树里逐条敲 README 的命令（`git archive` 或复制工作树）。
   判据 = `tests/test_readme_commands.py` 的口径 + 人工逐步（那条测试只验 parser 认不认参数，
   **不验命令能不能跑出结果** —— 后者只能真跑）。
6. **收尾**：DoD 验证 → `plan/00`/`plan/05`/`plan/06` 状态回写 → **写 `plan/HANDOFF-M6.md`**
   （M6 的入口，不是 M5 的收官单）→ commit。

> **M5 与 M6 的分界**：M5 = **交付面**（`SKILL.md` 契约块、技术报告、demo GIF、裸 clone 可复现）；
> M6 = **发布**（建仓首推 + tag + Release 附产物 + `plan/RELEASE-M6.md` + `tools/check_release.py`）。
> M6 一样要先有入口文件再动工，且 `tools/check_release.py` 是 `PENDING_TOOLS` 里唯一还挂着的登记项。

---

## 四、既定口径清单（K 编号 —— 动了会打挂测试的约定）

M0 的 K1–K15、M1 的 K16–K19、M2 的 K20–K23、M3 的 K24–K26、M4 的 K27–K29 **全部仍然有效**，
另加 M5 新增：

| K | 口径 | 动了会红的东西 |
|---|---|---|
| K30 | **`SKILL.md` 契约块与 `contract.py` 必须集合相等 + 数量相等**；契约块之外的正文**不参与**契约扫描（围栏是唯一扫描面） | `tests/test_contract.py` 的契约块断言；放宽成"包含"会漏"文档多写一个已废弃值" |
| K31 | **`docs/demo/demo.gif` 必须是真跑录制**，录制前逐条命令先手跑一遍 | `plan/05` §2 M5 DoD；录进红帧的 demo 比没有 demo 更减分 |
| K32 | **`plan/00` §5 四格表点名的入口必须真实存在**（`api.py::run()` 落实物，或改表改口） | `plan/00` §5 的自洽性；不设门，靠人复核 —— 所以**一次做完，别留半套** |

---

## 五、本机环境坑（只写实测过的，2026-11-01 续）

M0 §五、M1 §五、M2 §五、M3 §五、M4 §五 全部仍有效，另加：

- **`fixtures/` 746 个目录让 `pytest` 的参数化 ids 很长**：`test_fixtures_meta.py` 用
  `ids=[c.name for c in CASES]`，跑起来是 **3762 条** case。看计数时去掉 `-q`。
- **`.gif` 已在 `.gitattributes` 里声明 `binary`**（`*.gif binary`）：git 不许碰它，
  所以 `demo.gif` 的字节是稳定的。但这也意味着**它不能被 `text=auto` 归一** ——
  录制工具写什么字节，库里就是什么字节。
- **`docs/demo/` 现在是空目录**：git 不跟踪空目录，落 GIF 之前 `git ls-files docs/demo/`
  会返回空。这不是"文件丢了"。
- **`git archive` 导出的树里没有 `_headers/`**（被 `.gitignore` 封）：
  于是 `tests/test_catalog_data_m1.py` 的 28 条"回原文取行号"的测试会 **skip**（不是 fail）。
  裸 clone 验证时看到 skip 是**预期**，不是缺件。

---

## 六、DoD 逐项 checklist

> **全部未打勾** —— M5 未开工。这一节是**验收清单**，不是成绩单。

- [ ] `SKILL.md` 存在，契约块（`<!-- contract:begin -->` / `<!-- contract:end -->`）与
      `contract.py` **集合相等 + 数量相等**（`tests/test_contract.py` 新增断言全绿）
- [ ] `plan/00` §5 四格表的入口名与实物一致（`api.py::run()` 落盘，或那张表改口）
- [ ] `docs/技术报告.md` 存在，且**不复制** `data/README.md` §5 的数值
- [ ] `docs/demo/demo.gif` 存在且是**真跑录制**（录制前逐条命令手跑过）
- [ ] 裸 clone（无 `.git` 树）里 README 每条命令都能真跑出结果（`_headers/` 相关的 skip 属预期）
- [ ] `bench` 全绿（746 case）、`selftest` 全绿、`pytest` 双通道全绿
- [ ] 两道门全绿；`verify_gates.py` 全组 CAUGHT
- [ ] **`plan/HANDOFF-M6.md` 已落盘**（M6 入口；不是 M5 收官单）
- [ ] ~~CI 绿~~ → 仍不适用：无远端、未推送（`plan/05` §4 U1）

---

## 七、关键命令速查

```bash
# 门（对外）
py -3.12 tools/check_sprint_layout.py
py -3.12 tools/check_desensitized.py

# 门自己是否在验东西（逐组变异）
py -3.12 tools/verify_gates.py

# 判定面 + 基准 + 自测（交付面要演示的就是这几条）
PYTHONPATH=src py -3.12 -m errcode_atlas explain 98 --platform linux            # UNAMBIGUOUS → 0
PYTHONPATH=src py -3.12 -m errcode_atlas explain 11                            # AMBIGUOUS-CROSS-PLATFORM → 1
PYTHONPATH=src py -3.12 -m errcode_atlas explain SIGSTKFLT --platform macos    # PLATFORM-ABSENT → 1
PYTHONPATH=src py -3.12 -m errcode_atlas explain 99999 --platform linux        # UNKNOWN → 3
PYTHONPATH=src py -3.12 -m errcode_atlas exitcode 1 --platform linux           # UNATTRIBUTABLE → 1
PYTHONPATH=src py -3.12 -m errcode_atlas exitcode 64 --platform linux          # SYSEXITS，带 doc:#EX_USAGE → 0
PYTHONPATH=src py -3.12 -m errcode_atlas bench                                 # 扫了 746 个 case
PYTHONPATH=src py -3.12 -m errcode_atlas selftest                              # 六条不变量全绿

# 数据链（三步，顺序不能颠倒；M5 不改数据，只用来确认起点没坏）
py -3.12 tools/fetch_sources.py --check
py -3.12 tools/extract_catalog.py --check
py -3.12 tools/build_catalog.py --check

# 裸 clone 验证（无 .git 树）
git archive --format=zip -o ../errcode-atlas-src.zip HEAD   # 或复制工作树并删 .git
# 解包后逐条敲 README 的命令

# 测试（两条通道；看计数时去掉 -q）
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 py -3.12 -m pytest
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 py -3.8 -m pytest
```
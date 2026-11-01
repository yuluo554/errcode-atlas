# HANDOFF-M3 · 判定（五判定态收口 + 退出码归因 + 基准语料）

> **本文件是 M3 的入口文件**（按里程碑编号命名，不按"哪一棒写完它"命名 —— 见 `AGENTS.md` §一）。
> 状态：**M3 未开工**。下面是"进场须知 + 待办 + 口径"，不是"已完成"。
> 库里一律相对路径；本机绝对路径只出现在用户侧启动命令里。

---

## 一、当前进度 + 证据

**M3 尚未执行。** 本表如实为空，不预填 —— 预填就是给还没跑的棒编记录
（`AGENTS.md` §二 的判据② 正是为了挡住这件事）。

| 项 | 证据（命令 / 文件） |
|---|---|
| 入口文件本身 | 本文件（由 M2 收尾时落盘，满足"M2 收尾必须给 M3 留入口"） |
| M3 的核心产出 | **均未开始**：`fixtures/` 基准语料、`bench` 全态覆盖、`selftest` 扩项 |
| 起点基线（M2 交付，可直接用） | `data/catalog/` **6 个源文件 / 1049 条**；冻结编目逐平台 1964 条 / 去重 702 条（errno 215 / signal 37 / exit 15 / node 435） |
| 起点门态 | 布局门 / 脱敏门 / `build_catalog.py --check` / `extract_catalog.py --check`（双通道）/ `fetch_sources.py --check` / `verify_gates.py` 全绿 |
| 起点测试 | `py -3.12` **231 passed**；`py -3.8` **230 passed + 1 skip**（3.10+ 属性） |

> **判据入口**：这一节在 M3 收尾时必须被真实证据填满，且每条都写"命令 / 文件"。
> 空着不行，写"已完成"却不给命令也不行。

---

## 二、当前事实·状态不变量（动手前必须知道）

1. **编目现在是四域，不是三域**：`errno` / `signal` / `exit` / `node`。`node` 是**无值域**
   （`contract.VALUELESS_DOMAINS`）—— 条目只有名字、没有 `value`。数字查询**永远不探测**
   `node` 与 `exit`（`explain._domains_for`）。M3 判的仍然是"数字 + 平台 + 语境"，
   名字查询是另一条通路。
2. **两个共享文件的平台轴不一样**（这是事实，不是漏配）：
   `sysexits.yaml` 挂四轴、`node-errors.yaml` 挂三轴（不挂 `win32-python`）。
   依据与判据见 `data/README.md` §2.3；断言见 `tests/test_catalog_m2.py`。
   **动这张轴表会同时改变 `covered_platforms` 的分母** → 跨平台判定全盘变。
3. **`covered_platforms` 现在是查表**（`Catalog.covered`），`entry_for` 也是（`Catalog.by_key`）。
   判定层**不许**遍历 `.entries` —— 有 AST 守门（`test_judgement_layer_has_no_entries_scan`）。
   加功能时若需要新的查询面，**在装载期把索引建好**，不要在判定层扫。
4. **`exit` 域判定不依赖编目**（K22）：`exitcode 64` 在**空编目**上仍是 `SYSEXITS`。
   编目只提供"这个名字存在 + 出处锚"。`SYSEXITS_NAMES`（代码内表）与 `sysexits.yaml`
   是两份副本，双向一致由 `test_code_table_and_catalog_are_two_copies_that_agree` 守。
5. **`128+n` 的 `n` 有效性仍只来自编目信号表**（M1 不变）。`attribute()` 的判定顺序
   （越界 → sysexits → 0 → 128+n → 1 → 1–127 → 其余）**不许重排**。
6. **G6 已关闭（M2 定稿）**：`plan/03` §2.2 现在是九行表，序 7 = 名字 + 无平台 + 值发散
   → `UNAMBIGUOUS`；序 8 = 名字 + 无平台 + 某平台没有 → `PLATFORM-ABSENT`。
   `data/README.md` §5.2 的举例同步改成**数字查询**（`11`）。**M3 不许把它们改回去。**
7. **`UNKNOWN` 现在有两种形态**，两种都必须 exit 3：越界值 / **域内有条目但无此值**。
   M3 的 `fixtures/` 至少要各一例（`data/README.md` §4 门槛已加这一行）。
8. **`fixtures/` 现在完全为空**（`docs/demo/` 也是）。`bench` 在没有 case 时返回
   `EXIT_UNDECIDABLE`（3）并打印"这是空跑，不是全绿" —— 那个行为是对的，别改成返回 0。
9. **`entry_count` 与 `distinct_count` 是两个分母**：前者逐平台（共享条目按轴重复计），
   后者按 `(domain, name)` 去重。写报告/断言时**点名用哪个**，不许含糊。
10. **`kind: doc` 的条目强度恒为 `diff`**（K21），`source_label` 形态是 `doc:#<anchor>`。
    人读表**不输出 URL**（零外链，`plan/03` §4.1）。

---

## 三、待办（M3 执行序）

0. **先读 `plan/06` 的 R8 与 `data/README.md` §3/§4**：真值必须**手写 + 对照原文**，
   `expected.json` **不许**从 `explain` 的输出回填（那是循环论证，bench 恒绿）。
   M2 的独立对账通路（`tests/test_catalog_m2.py` 的两条正则）就是"另一条腿"的样子。
1. **建 `fixtures/`**：每 case 一目录，含 `INPUT.md`（用户会怎么问）+ `expected.json`
   （**结果对象级**真值，不是渲染文本）。覆盖门槛见 `data/README.md` §4，M2 新增的两行别漏：
   `sysexits` 15 条、Node 435 条、`UNKNOWN` 两形态。
2. **跨平台分叉点全覆盖**：`data/README.md` §1.2 的五个信号分叉 + §1.1 的三个 Windows 数值差异，
   逐点至少一例。**`EAGAIN` 只能作"名字查询"的样本**，不能作跨平台歧义样本（§5.2 已改口）。
3. **不可归因集**：`exit 1`、无平台数字、越界值、`PLATFORM-ABSENT` 各至少一例；
   外加 `win32-python` 上查 `ERR_*` → `PLATFORM-ABSENT`（不是 `UNKNOWN`）。
4. **`exit` 域与 `node` 域各至少一例**：
   - `exitcode 64 --platform linux` → `SYSEXITS`，`notes` 必带"约定非标准"，`sources` 带 `doc:#EX_USAGE`；
   - `explain EX_USAGE --domain exit` → 四平台都是 64，`UNAMBIGUOUS`；
   - `explain ERR_AMBIGUOUS_ARGUMENT --platform linux` → `UNAMBIGUOUS`，候选值渲染成"（无数字码值）"。
5. **`selftest` 扩项**：现五条不变量（确定性 / 退出码映射 / `exit 1` / 信号有效性 / gray 字样）。
   M3 应加"五态可达性"断言 —— 用真编目跑出五种 verdict 各一次，任一跑不出来就 FAIL。
6. **`bench` 的判据是结果对象**（`plan/02` D4）。`bench.py` 已支持 `explain` / `exitcode` 两类
   `input.kind`，**不需要为 M3 扩新 kind** —— 除非发现某条门槛表达不出来，
   那时先改 `expected.json` 的形状与 `bench._check_case`，**不要**把判定塞回 bench。
7. **收尾**：DoD 验证 → `plan/00`/`plan/05`/`plan/06` 状态回写 →
   **写 `plan/HANDOFF-M4.md`**（M4 的入口，不是 M3 的收官单）→ commit。

> **M3 与 M4 的分界**（容易混）：M3 = **判定层收口**（五态各一条真数据用例跑通 + `selftest` 扩项）；
> M4 = **基准语料成规模**（`fixtures/` 达到 `data/README.md` §4 的全部门槛 + `bench` 可跑）。
> 若两棒在本轮合并，仍要**先写 `HANDOFF-M4.md` 再动 M4** —— 入口文件按里程碑编号命名。

---

## 四、既定口径清单（K 编号 —— 动了会打挂测试的约定）

M0 的 K1–K15、M1 的 K16–K19、M2 的 K20–K23 **全部仍然有效**，另加 M3 新增：

| K | 口径 | 动了会红的东西 |
|---|---|---|
| K24 | **`fixtures/*/expected.json` 是手写真值，不许由 `explain` 输出回填** | `bench` 恒绿（结构性失效，只有 review 能发现 —— 所以写 case 时**先在 INPUT.md 里写来源**） |
| K25 | **`exit` / `node` 域不许出现在数字查询的探测链里** —— `explain 100` 不得多出 `ERR_*` 候选 | `tests/test_catalog_m2.py::test_err_code_number_lookup_does_not_bleed_into_node_domain` |
| K26 | **`selftest` 的期望值写字面量**（`0/1/3/4`），不写 `contract.EXIT_*` 常量 | 自我参照：改错常量时"实测"与"期望"一起错（M0 K12 的同一类，M1 已实测过） |

---

## 五、本机环境坑（只写实测过的，2026-11-01 续）

M0 §五、M1 §五、M2 §五 全部仍有效，另加：

- **`pytest -q` 在 Git Bash 里看不到 passed 计数行**（它把最后一行也吞了）。
  要看计数就去掉 `-q`：`PYTHONPATH=src py -3.12 -m pytest` → "231 passed in 11.01s"。
- **网页原文的解析正则，两种写法都会"匹配出 0 条"**（本项目 M2 各踩一次）：
  ① `<a>` 里面还套着 `<code>` —— 用 `[^<]*</a>` 当锚会失败；
  ② 名字与码值之间有换行缩进。
  所以**抽取器与测试各用一套独立正则**，一边红只说明那一边的判据没在验，不是"数据错了"。
- **HTML 里 `<p>` 闭合不严格**（大量 `<p>` 直接接下一个 `<p>`）：按 `</p>` 找段落会得到空串，
  要用 `(?=<p>|</section>)` 前瞻。且**切片到 `</section>` 时那 10 个字符已被切掉**，
  匹配前要补回去 —— 否则每组的**最后一条**（如 `MODULE_NOT_FOUND`）释义为空。
- **`Path.read_text()` 不接受 `newline=` 参数**（那是 `open()` 的）。批量改带 CRLF 的文件时，
  用 `Edit` 工具或 `open(..., newline='')`，别指望 `read_text`。
- **`tuple[str, ...]` 是 3.9+ 下标**，模块级普通赋值在 3.8 上直接 TypeError
  （M1 已记；M2 的 `Entry.value: int | None` 在**注解**里，有 `from __future__ import annotations` 兜着）。

---

## 六、DoD 逐项 checklist

> **全部未打勾** —— M3 未开工。这一节是**验收清单**，不是成绩单。
> 收尾时才允许逐项打勾，且每项要能指到命令或文件。

- [ ] `fixtures/` 覆盖 `data/README.md` §4 的全部门槛，含 M2 新增的 `sysexits` / `node` / `UNKNOWN` 两形态
- [ ] 五判定态全部可达且各有 case；`bench` 断言 `exit 1` → `UNATTRIBUTABLE`
- [ ] 跨平台分叉点全覆盖（§1.2 五个信号点 + §1.1 三个 Windows 数值点）
- [ ] `128+n` 的 `n` 有效性有专门 case（`n` 无效 → `UNATTRIBUTABLE`）
- [ ] `plan/03` §2.2 九行表与 §3.2 六行表**逐行**各有一条测试
- [ ] `selftest` 扩到"五态可达性"，且期望值写字面量（K26）
- [ ] `pytest` 双通道全绿；`verify_gates.py` 全组 CAUGHT
- [ ] `build_catalog.py --check` 与 `extract_catalog.py --check` 双跑逐字节一致
- [ ] **`plan/HANDOFF-M4.md` 已落盘**（M4 入口；不是 M3 收官单）
- [ ] ~~CI 绿~~ → 仍不适用：无远端、未推送（`plan/05` §4 U1）

---

## 七、关键命令速查

```bash
# 门（对外）
py -3.12 tools/check_sprint_layout.py
py -3.12 tools/check_desensitized.py

# 门自己是否在验东西（逐组变异）
py -3.12 tools/verify_gates.py

# 数据链（三步，顺序不能颠倒）
py -3.12 tools/fetch_sources.py --out _headers        # 1) 取原文（联网：gh api + https 网页通路）
py -3.12 tools/fetch_sources.py --check               #    已取件 sha256 对账（7 份）
py -3.12 tools/extract_catalog.py --out data/catalog   # 2) 抽取 YAML（零网络，6 个文件）
py -3.12 tools/extract_catalog.py --check              #    与仓库 YAML 逐字节比对
py -3.12 tools/extract_catalog.py --report             #    取数事实 + 被排除项 + 共享域条目数
py -3.12 tools/build_catalog.py --out src/errcode_atlas/data   # 3) 冻结 JSON
py -3.12 tools/build_catalog.py --check

# 判定面（M2 基线：四域已可用）
PYTHONPATH=src py -3.12 -m errcode_atlas explain 6 --platform linux --domain signal   # AMBIGUOUS-SAME-PLATFORM → 1
PYTHONPATH=src py -3.12 -m errcode_atlas explain SIGSTKFLT --platform macos --domain signal  # PLATFORM-ABSENT → 1
PYTHONPATH=src py -3.12 -m errcode_atlas exitcode 137 --platform linux   # SIGNAL-KILLED(9) → 0
PYTHONPATH=src py -3.12 -m errcode_atlas exitcode 64 --platform linux    # SYSEXITS，带 doc:#EX_USAGE → 0
PYTHONPATH=src py -3.12 -m errcode_atlas explain EX_USAGE --domain exit  # 四平台都 64 → 0
PYTHONPATH=src py -3.12 -m errcode_atlas explain ERR_AMBIGUOUS_ARGUMENT --platform linux  # UNAMBIGUOUS → 0
PYTHONPATH=src py -3.12 -m errcode_atlas explain ERR_AMBIGUOUS_ARGUMENT --platform win32-python  # PLATFORM-ABSENT → 1
PYTHONPATH=src py -3.12 -m errcode_atlas explain 99999 --platform linux --domain exit  # UNKNOWN → 3

# 测试（两条通道；看计数时去掉 -q）
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 py -3.12 -m pytest
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 py -3.8 -m pytest
```
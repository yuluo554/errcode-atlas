# HANDOFF-M4 · 基准（语料成规模 + 跨平台零错判 + `bench`/`selftest` 加固）

> **本文件是 M4 的入口文件**（按里程碑编号命名，不按"哪一棒写完它"命名 —— 见 `AGENTS.md` §一）。
> 状态：**M4 未开工**。下面是"进场须知 + 待办 + 口径"，不是"已完成"。
> 库里一律相对路径；本机绝对路径只出现在用户侧启动命令里。

---

## 一、当前进度 + 证据

**M3 已收口（✅），M4 尚未执行。** 下表 M3 那几行是**真跑过的**，每行都指得到命令或文件；
M4 那一栏如实为空，不预填。

| 项 | 证据（命令 / 文件） |
|---|---|
| M3 入口 | `plan/HANDOFF-M3.md`（已收口，其 §一 的"起点基线"可直接接手） |
| 判定顺序逐行锁死 | `tests/test_judgement_order.py`：`plan/03` §2.2 九行、§3.2 六行各一条；另有 `::test_documented_table_row_counts` 断言两表仍是 **9 / 6 行** |
| 五态可达性 | `PYTHONPATH=src py -3.12 -m errcode_atlas selftest` → `selftest: 全绿`（`_check_verdict_reachability` 在真编目上五态各真跑一遍） |
| 基准语料（种子） | `fixtures/` **59 个 case / 118 个文件**；`PYTHONPATH=src py -3.12 -m errcode_atlas bench` → `扫了 59 个 case，0 项不符` |
| 语料自身判据 | `tests/test_fixtures_meta.py`：形状 / `source` / 五态计数（≥2，其中 `UNKNOWN`、`UNAMBIGUOUS` ≥3）/ `UNKNOWN` 两形态 / 分叉点 / sysexits 15 条 / `exit 1` / `n` 无效 |
| 测试双通道 | `py -3.12` **577 passed**；`py -3.8` **576 passed + 1 skip**（3.10+ 属性） |
| 两道门 | `py -3.12 tools/check_sprint_layout.py` / `check_desensitized.py` 全绿 |
| 门自己在验东西 | `py -3.12 tools/verify_gates.py` → **19 组全 CAUGHT**，还原后复绿 |
| 数据链 | `fetch_sources.py --check`（7 份）/ `extract_catalog.py --check`（6 源 / 1049 条）/ `build_catalog.py --check`（1964 条 / 去重 702）三个 exit 0 |

> **判据入口**：这一节在 M4 收尾时必须被真实证据填满，且每条都写"命令 / 文件"。
> 空着不行，写"已完成"却不给命令也不行。

---

## 二、当前事实·状态不变量（动手前必须知道）

1. **M3 修掉了三处真缺陷，且都是新判据抓出来的**（别回退，回退会让对应测试红）：
   - 序 3「缺席平台」进 `Explanation.platform_absent_in`，不再只写在 `distinguish` 散文里；
   - 「名字 + 无平台」这一支的 `gray` 强制字样，按**命中的域**给（不是按探测的域）；
     数字形态用 `_maybe_gray_notes`（"惯例非标准"），名字形态用 `_name_gray_notes`（"约定非标准"）
     —— 两者不许合并成一句，理由见 `explain.py` 的 docstring；
   - 序 8 的分母改成**该域已覆盖的平台**（原先 `catalog.platforms()` 让 `ERR_*` 每次无平台查询
     都判假 `PLATFORM-ABSENT`）。
2. **`fixtures/*/expected.json` 里有 `source` 字段，`bench` 不比对它**。那是给人 review 的
   （K24 的唯一落地判据：说不出源就没法复核）。`tests/test_fixtures_meta.py::test_expected_declares_source`
   把它变成可跑红的门。
3. **真值不是 `explain` 的输出**。M3 的做法 = 一份**不 import `errcode_atlas`** 的独立推导
   （只读 `data/catalog/*.yaml` + `data/README` §5 判据）算出全部真值，再与实现对照。
   **那份脚本刻意不入仓**：入仓后任何人改完编目重跑一次就能让 `expected.json` 跟着变，
   `bench` 于是恒绿 —— 那正是 K24 要挡的循环论证。M4 铺规模时**沿用这个做法**（写脚本、
   跑一遍、删脚本、只留 case 两个文件 + INPUT.md 里的来源）。
4. **`bench` 现在会比对 `per_platform`**（M3 补）。跨平台 case 若只写 `verdict`，逐平台真值
   没有任何断言在看 —— 新增 case 时优先写 `per_platform`。
5. **`entry_count`（1964，逐平台）与 `distinct_count`（702，按 `(domain, name)` 去重）是两个分母**。
   写报告/断言时点名用哪个，不许含糊。§4 的"Node 435 节"指 **distinct**。
6. **`fixtures/` 目录名是 case id，不是分类号**。现有前缀只是可读性：`u-`（UNAMBIGUOUS）、
   `a-`（AMBIGUOUS-*）、`p-`（PLATFORM-ABSENT）、`n-`（UNKNOWN）、`e-`（exitcode 归因）、
   `s-`（sysexits）、`x-`（跨平台数字分叉）。**没有任何代码读前缀** —— 别把它当 schema。
7. **`data/README.md` §4.1 是新加的分界表**：它把"M3 已证明可达"与"M4 还要铺满规模"
   分开列。M4 收尾时要**逐行把 ⬜ 改成 ✅** 并把证据补进"证据"列，不是删掉那张表。
8. **`exit` 域判定不依赖编目（K22）与 `node` 无值域（K23）仍有效**；`node` 域不挂
   `win32-python`（事实，不是漏配）。
9. **`128+n` 的 `n` 有效性只来自编目**；`147` 在 linux 是 `SIGSTOP`、macos 是 `SIGCONT`
   —— 同一退出码两平台不同名，M4 加 case 时别在代码里写死信号名。

---

## 三、待办（M4 执行序）

0. **先跑门**：`check_sprint_layout.py` / `check_desensitized.py` / `pytest` / `bench` / `selftest`。
   起点全绿，红了先修再干活。
1. **把 `data/README.md` §4.1 里三个 ⬜ 铺满**（这是 M4 的主体）：
   - **errno 三平台 × ≥30 个公共常量**：优先取 `data/README.md` §1.1 E1–E5 已列的事实，
     平台间**同值同义**与**同值异义**都要有（`98` 在 linux 是 `EADDRINUSE`、在 macos 是 `ENOSR`
     —— 这条已经在 `u-macos-98-is-enosr` 里，是"同值异义"的现成样本）；
   - **信号两平台 × 全部 `#define SIG*`**（linux 34 / macos 32 已入编目）：逐条一条 case，
     分叉点已覆盖，剩下的是"同值同名"的常规项；
   - **Node 435 节逐条**：`node` 是无值域，case 只能是"名字 + 平台"形态；
     弃用的 52 条要**点名 legacy**（`description_zh` 里已有 `Legacy Node.js error codes` 字样）。
2. **每个 case 的真值仍走"独立推导 + 人工对照原文"**（见 §二 第 3 条）。
   铺量时**先写 `tmp/truth/cases.json` 的条目**（含 `source`），再跑推导，再删脚本。
3. **跨平台零错判**：M3 已有 §1.2 五个信号分叉 + §1.1 三个 Windows 数值差异点。
   M4 要补的是**反向样本** —— 同值同义（不该判歧义）的 case 数量要压过歧义样本，
   否则语料会系统性地偏向"歧义"，`bench` 全绿反而证明不了"不该歧义时不歧义"。
4. **`bench` / `selftest` 加固**（只在发现门槛表达不出来时才动，且**不许把判定塞回 bench**，
   `plan/03` §6）：
   - 若某条门槛需要新字段，先改 `expected.json` 形状与 `bench._check_case`；
   - `selftest` 的五态可达性用的是**真编目**，M4 铺量后它不该变红；
     若变红通常是"某态在真编目上确实跑不出来了"，不要靠改探针绕过。
5. **报告与时间成本**：59 case 跑一次 `bench` 是毫秒级；铺到 §4 全门槛后记一次真实耗时
   （`plan/06` R8 只要求"真值不是编的"，但"跑得完"也是交付面的一部分）。
6. **收尾**：DoD 验证 → `plan/00`/`plan/05`/`plan/06` 状态回写 → `data/README.md` §4.1 逐行翻 ✅
   → **写 `plan/HANDOFF-M5.md`**（M5 的入口，不是 M4 的收官单）→ commit。

> **M4 与 M5 的分界**：M4 = **语料成规模 + `bench`/`selftest` 加固**；
> M5 = **交付面**（`SKILL.md` 契约块双向断言、`docs/技术报告.md`、`docs/demo/demo.gif`、裸 clone 可复现）。
> M5 一样要先有入口文件再动工。

---

## 四、既定口径清单（K 编号 —— 动了会打挂测试的约定）

M0 的 K1–K15、M1 的 K16–K19、M2 的 K20–K23、M3 的 K24–K26 **全部仍然有效**，另加 M4 新增：

| K | 口径 | 动了会红的东西 |
|---|---|---|
| K27 | **`bench` 只比对结果对象，不比对渲染文本**；新门槛表达不出来时改 `expected.json` 形状与 `_check_case`，**不许把判定塞回 bench** | `plan/02` D4 / `plan/03` §6 的口径；塞回去会让"呈现层零判定"那条也失去意义 |
| K28 | **`fixtures/*/expected.json` 的 `source` 字段是必填**（真实来源，不是"见 data/README"） | `tests/test_fixtures_meta.py::test_expected_declares_source`（M3 变异验证：删掉该字段 → CAUGHT） |
| K29 | **`fixtures/` 目录名的前缀没有语义**（`u-`/`a-`/`p-`/`n-`/`e-`/`s-`/`x-` 只是可读性） | 没有任何代码读它 —— 但如果有人开始读，就会把"新增 case 必须按前缀命名"变成隐式约束 |

---

## 五、本机环境坑（只写实测过的，2026-11-01 续）

M0 §五、M1 §五、M2 §五、M3 §五 全部仍有效，另加：

- **`fixtures/` 下 59 个目录会让 `pytest` 的参数化 ids 变长**：`test_fixtures_meta.py` 用
  `ids=[c.name for c in CASES]`，跑起来是 170+ 条 case。看计数时去掉 `-q`。
- **`Path.read_text()` 不接受 `newline=`**；批量读 case 文件时一律 `encoding="utf-8"`。
  `\r\n` 会让 `expected.json` 的 `json.loads` 仍然成功（JSON 允许），但 `bench` 的
  逐字节比较类断言会红（摘要类的东西都按行尾归一，见 `catalog.sha256_of_text`）。
- **`pytest` 里 fixture 名叫 `cat` 会和参数名 `cat` 打架**：M3 踩过一次
  （`AttributeError: 'FixtureFunctionDefinition' object has no attribute ...`）。
  新测试里如果用模块级常量拿真编目，就叫 `CATALOG`，别叫 `cat`。
- **变异验证要"先写判据、再制造故障"**：M3 的 `test_unknown_has_both_shapes` 首版只判
  `domain` 非空，把形态二的 domain 换成 `signal` 仍绿 —— 那是假门，靠变异验证当场抓到。
  M4 加判据后，**至少做一次 injection** 再宣布它成立。

---

## 六、DoD 逐项 checklist

> **全部未打勾** —— M4 未开工。这一节是**验收清单**，不是成绩单。

- [ ] `fixtures/` 覆盖 `data/README.md` §4 全部门槛（§4.1 三个 ⬜ 全部翻 ✅ 且带证据）
- [ ] errno 三平台 × ≥30 公共常量；信号两平台 × 全部 `#define SIG*`；Node 435 节逐条
- [ ] 跨平台分叉点全覆盖，且**同值同义的 case 数量压过歧义样本**
- [ ] 每条 `expected.json` 带 `source`（`test_fixtures_meta.py` 全绿）
- [ ] `bench` 全绿；`selftest` 全绿且五态可达性未变红
- [ ] `pytest` 双通道全绿；`verify_gates.py` 全组 CAUGHT
- [ ] `build_catalog.py --check` 与 `extract_catalog.py --check` 双跑逐字节一致
- [ ] 记一次 `bench` 在完整语料上的真实耗时
- [ ] **`plan/HANDOFF-M5.md` 已落盘**（M5 入口；不是 M4 收官单）
- [ ] ~~CI 绿~~ → 仍不适用：无远端、未推送（`plan/05` §4 U1）

---

## 七、关键命令速查

```bash
# 门（对外）
py -3.12 tools/check_sprint_layout.py
py -3.12 tools/check_desensitized.py

# 门自己是否在验东西（逐组变异）
py -3.12 tools/verify_gates.py

# 判定面 + 基准 + 自测（M3 交付的三条主命令）
PYTHONPATH=src py -3.12 -m errcode_atlas explain 98 --platform linux            # UNAMBIGUOUS → 0
PYTHONPATH=src py -3.12 -m errcode_atlas explain 11                            # AMBIGUOUS-CROSS-PLATFORM → 1
PYTHONPATH=src py -3.12 -m errcode_atlas explain SIGSTKFLT --platform macos    # PLATFORM-ABSENT → 1
PYTHONPATH=src py -3.12 -m errcode_atlas explain 1 --platform linux --domain exit  # UNKNOWN → 3
PYTHONPATH=src py -3.12 -m errcode_atlas exitcode 1 --platform linux           # UNATTRIBUTABLE → 1
PYTHONPATH=src py -3.12 -m errcode_atlas exitcode 137 --platform win32-python  # UNATTRIBUTABLE（n=9 无效）→ 1
PYTHONPATH=src py -3.12 -m errcode_atlas exitcode 64 --platform linux          # SYSEXITS，带 doc:#EX_USAGE → 0
PYTHONPATH=src py -3.12 -m errcode_atlas bench                                 # 扫了 59 个 case
PYTHONPATH=src py -3.12 -m errcode_atlas selftest                              # 六条不变量全绿

# 数据链（三步，顺序不能颠倒）
py -3.12 tools/fetch_sources.py --check
py -3.12 tools/extract_catalog.py --check
py -3.12 tools/build_catalog.py --check

# 测试（两条通道；看计数时去掉 -q）
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 py -3.12 -m pytest
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 py -3.8 -m pytest
```
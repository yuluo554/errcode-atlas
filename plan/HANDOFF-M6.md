# HANDOFF-M6 · 发布（建仓首推 + tag + Release 附产物 + 发布留档 + `check_release.py`）

> **本文件是 M6 的入口文件**（按里程碑编号命名，不按"哪一棒写完它"命名 —— 见 `AGENTS.md` §一）。
> 状态：**M6 未开工**。下面是"进场须知 + 待办 + 口径"，不是"已完成"。

> **收尾追加（M6 完工时）**：本文件已按里程碑入口的语义**完成使命** —— 它写的"未开工"
> 是**进场时**的事实，保留原样不回填（否则下一棒读不到"当时的起点"）。
> 真实结果在 `plan/RELEASE-M6.md`：tag `v0.1.0`（annotated）、Release 附 2 个手工附件、
> CI run `41320856857` 8/8 全绿。**本仓里程碑到 M6 为止**，没有 `HANDOFF-M7.md`。
> 库里一律相对路径；本机绝对路径只出现在用户侧启动命令里。

---

## 一、当前进度 + 证据

**M5 已收口（✅），M6 尚未执行。** 下表是**真跑过的起点基线**，每行都指得到命令或文件。

| 项 | 证据（命令 / 文件） |
|---|---|
| M5 入口 | `plan/HANDOFF-M5.md`（已收口，其 §一 证据表可直接接手） |
| **M5 三件交付物** | `SKILL.md`（契约块 + 用法）/ `docs/技术报告.md` / `docs/demo/demo.gif`（51 帧，真跑录制） |
| Skill 的 Python 级入口 | `src/errcode_atlas/api.py::run()`（`plan/00` §5 四格表点名的那个） |
| 契约块双向断言 | `tests/test_contract.py` 契约块那六条：围栏恰好一对 / 四节各 >0 行 / 三组集合相等 + 数量相等 / 退出码 / 平台值四个无别名 / 不复述数值 |
| 信封同源断言 | `tests/test_api.py` 七条参数化：`api.run` 的两路文本与 `cli.main` **逐字节**相同 |
| 报告样例对账 | `tests/test_docs.py`：报告里每条 `console` 样例与真跑**逐字节**比对（当前 5 条） |
| GIF 判据 | `tests/test_docs.py`：GIF 文件头 / ≥10 帧标记 / 无本机路径特征 / 录制脚本必须带脱敏提示符 |
| 测试双通道 | `py -3.12` **4070 passed**；`py -3.8` **4069 passed + 1 skip**（3.10+ 属性） |
| 基准语料 | `bench` → `扫了 746 个 case，0 项不符`；`selftest` → `全绿` |
| 两道门 | `check_sprint_layout.py` / `check_desensitized.py` 全绿 |
| 门自己在验东西 | `verify_gates.py` → **19 组全 CAUGHT**，还原后复绿 |
| 数据链 | `fetch_sources.py --check` / `extract_catalog.py --check` / `build_catalog.py --check` 三个 exit 0 |
| **M6 的唯一登记项** | `tools/check_release.py` **不存在**（`check_sprint_layout.py` 的 `PENDING_TOOLS` 里唯一还挂着的一条） |

> **判据入口**：这一节在 M6 收尾时必须被真实证据填满，且每条都写"命令 / 文件"。

---

## 二、当前事实·状态不变量（动手前必须知道）

1. **M6 是"发布面"，不是"交付面"**。`SKILL.md` / 报告 / GIF 已在 M5 定稿。
   **M6 不许改判定逻辑**，也不许重写交付物 —— 只在发布流程上推进。
2. **口径 A 自 M1 起不得删改或降级**（`plan/00` §4）：**Release 附 ≥1 个手工上传附件**，
   本地留副本 + sha256。这不是"可选加分项"，是 M6 DoD 的第一条。
3. **`plan/RELEASE-M6.md` 必须在 `git tag` 之前落盘**。tag 树里不许写自指值
   （附件 sha256、run id 这类"tag 之后才知道"的事实）。tag 后**追加**，不回填。
4. **`tools/check_release.py` 三档**：`--pre-tag` / `--offline` / `--online`，无 FAIL。
   它落盘后**同笔删掉** `check_sprint_layout.py` 的 `PENDING_TOOLS` 登记项 ——
   只落脚本不删登记，`LAYOUT.DOC_TOOLS` 的 stale 分支会报"已 ✅ 的里程碑名下还挂着待办"。
5. **名字占用必须在建仓之前重核一次**：`plan/06` §4.1 记的"PyPI 404 / GitHub 0 命中"是
   **2026-11-01 的快照**，结果可能变。核过再建仓，别建完才发现要改名。
6. **CI 未跑过之前，任何文档都不许写"CI 绿"**（`plan/05` §4 U1）。
   首推之后**追加**真实 run id，保留"本地等价校验"原措辞，不做回填美化。
7. **`README.md` 不承载里程碑状态**（`AGENTS.md` §二）。M6 写 README 时**不许**加"当前进度"。
8. **`.gif` 已在 `.gitattributes` 声明 `binary`**：git 不许碰它，字节稳定；
   但这也意味着它不能被 `text=auto` 归一 —— 录制工具写什么字节，库里就是什么字节。
9. **`git archive` 导出的树里没有 `_headers/`**（被 `.gitignore` 封）：
   `tests/test_catalog_data_m1.py` 的 28 条"回原文取行号"测试会 **skip**（不是 fail）。
   裸 clone 验证时看到 skip 是**预期**，不是缺件。
10. **`py -3.8` 只验语法面**（`plan/06` §5）。M6 若新增测试，3.9+ 语法会让 3.8 通道
    SyntaxError —— 那是本仓的下限纪律，不是"3.8 不支持本工具"。

---

## 三、待办（M6 执行序）

0. **先跑门**：`check_sprint_layout.py` / `check_desensitized.py` / `pytest`（双通道）/ `bench` / `selftest`。
   起点全绿，红了先修再干活。
1. **建仓前重核名字占用**：`gh api -X GET search/repositories -f q='errcode-atlas in:name'`，
   PyPI `errcode-atlas` / `errcode_atlas` 两个 404。结果写进 `plan/RELEASE-M6.md` §一。
2. **落 `tools/check_release.py`**（三档），并**同笔删掉** `PENDING_TOOLS` 里那条登记。
   变异验证要跟着补一组：改坏发布留档的某一栏，`--offline` 必须变红。
3. **`plan/RELEASE-M6.md` 落盘**（tag 之前）：两栏结构（`## 一、tag 前事实` / `## 二、tag 后追加`）
   + `## 覆盖对账` 小节 + ≥3 条三态行（`实现` / `不适用` / `待首推`）——
   `LAYOUT.RELEASE` 在 M6 翻 ✅ 后会逐项判这三件。
4. **commit → 建远端 → push → 首推 CI**（预期至少一轮诊断）。
   CI 红了就修，**别在文档里写"CI 绿"直到它真绿**。
5. **`git tag -a v0.1.0`** → 从 **tag 树**构建附件 `errcode-atlas-<ver>.zip` → `SHA256SUMS`
   → GitHub Release 上传（≥1 个手工附件）。
6. **回下载对账**：`gh release download` → `sha256sum -c` → 与本地副本 `cmp`。
   附件与 `git archive <tag>` 导出树的**共有文件**逐字节同源。
7. **tag 后追加事实**（新 commit）：run id / 下载件 sha256 / 首推结果。
8. **收尾**：DoD 验证 → 状态回写（`plan/00` + `plan/05`）→ commit。
   **M6 是末棒**：`HANDOFF_EXEMPT_LAST = False`，所以**仍要写 `plan/HANDOFF-M7.md`**？
   **不是** —— 本仓里程碑到 M6 为止。末棒的收尾物是 `plan/RELEASE-M6.md` 本身（两栏齐）。

> **M6 与 M5 的分界**：M5 = 交付面（`SKILL.md` 契约块、技术报告、demo GIF、裸 clone 可复现）；
> M6 = 发布（建仓首推 + tag + Release 附产物 + 发布留档 + `check_release.py`）。

---

## 四、既定口径清单（K 编号 —— 动了会打挂测试的约定）

M0 的 K1–K15、M1 的 K16–K19、M2 的 K20–K23、M3 的 K24–K26、M4 的 K27–K29、
M5 的 K30–K32 **全部仍然有效**，另加 M6 新增：

| K | 口径 | 动了会红的东西 |
|---|---|---|
| K33 | **`plan/RELEASE-M6.md` 必须在 tag 之前落盘**；tag 树内不写自指值（附件 sha256 / run id 属"tag 后"事实，追加不回填） | `LAYOUT.RELEASE` 的两栏结构 + `check_release.py --pre-tag` |
| K34 | **口径 A 不可降级**：Release 必须附 ≥1 个手工上传附件，本地留副本 + sha256 | `plan/05` §2 M6 DoD 第一条；`check_release.py --online` |
| K35 | **附件与 `git archive <tag>` 导出树的共有文件逐字节同源** | `check_release.py --offline`（下载件与本地副本 `cmp`） |
| K36 | **`check_release.py` 落盘的同笔删掉 `PENDING_TOOLS` 登记项** | `LAYOUT.DOC_TOOLS` 的 stale 分支（只落脚本不删登记 = 红） |

---

## 五、本机环境坑（只写实测过的，2026-11-01 续）

M0 §五、M1 §五、M2 §五、M3 §五、M4 §五、M5 §五 全部仍有效，另加：

- **`gh` 在 PATH（2.93.0）**，但 `raw.githubusercontent.com` 与 `github.com` 网页直连在本机被重置 ——
  一律走 `gh api repos/<owner>/<repo>/contents/<path>`，别用 raw 链接（`data/README.md` §2.1）。
- **`.gif` 的字节由录制工具决定**，git 不做归一。所以"重录一次 GIF"会改字节，
  但那不该让任何测试变红（判据只看帧数与文件头，不看字节）。
- **录制通道的两个坑（M5 实测）**：
  (a) Windows Terminal 会覆盖 `title` —— 用 `wt -w <名> "cmd /c …"` 启动时按标题找窗口**落空**，
  必须用 `start "" <脚本>`；
  (b) 150% 缩放下不开 `SetProcessDpiAwareness(2)`，`PrintWindow` 抓到的是缩放位图、右边被裁一截
  （本机实测：逻辑 1180×780 vs 真实 1770×1170）。
- **demo 的提示符必须脱敏**（`prompt errcode-atlas$G`）：默认提示符会把本机绝对路径录进帧，
  而 `*.gif` 在脱敏门的 `SKIP_EXTS` 里 —— **门抓不到**，随包发出去就是真泄露。
- **`tmp/` 被 `.gitignore` 封**，录制脚本与帧都在那里。`tests/test_docs.py` 里那条
  "脚本必须带脱敏提示符"在导出树里会 skip（脚本不存在），那是预期。

---

## 六、DoD 逐项 checklist

> **全部未打勾** —— M6 未开工。这一节是**验收清单**，不是成绩单。
>
> **收尾追加（M6 完工时）**：本节已全部落实到 `plan/RELEASE-M6.md` 与 `plan/05` §2 M6 DoD。
> 勾选状态以那两处为准，本节保持"进场时"的原样。

- [ ] 名字占用在建仓**之前**重核（`gh api` + PyPI 两个 404），结果写进 `plan/RELEASE-M6.md` §一
- [ ] `tools/check_release.py` 三档（`--pre-tag` / `--offline` / `--online`）无 FAIL，
      且 `PENDING_TOOLS` 登记项已删
- [ ] `plan/RELEASE-M6.md` 在 tag **之前**落盘（两栏 + 覆盖对账 + ≥3 条三态行）
- [ ] 首推 CI 真绿（**写 run id，不写"预期绿"**）
- [ ] `git tag -a v0.1.0`（annotated）
- [ ] GitHub Release 附 ≥1 个手工上传附件（`errcode-atlas-<ver>.zip`）+ `SHA256SUMS`
- [ ] 附件与 `git archive <tag>` 导出树的共有文件**逐字节同源**
- [ ] 回下载 `sha256sum -c` 通过，且与本地副本 `cmp` 一致
- [ ] tag 后追加提交写事实（run id / 下载件 sha256）
- [ ] 两道门全绿；`verify_gates.py` 全组 CAUGHT；`bench` / `selftest` / `pytest` 双通道全绿

---

## 七、关键命令速查

```bash
# 门（对外）
py -3.12 tools/check_sprint_layout.py
py -3.12 tools/check_desensitized.py

# 门自己是否在验东西（逐组变异）
py -3.12 tools/verify_gates.py

# 判定面 + 基准 + 自测
PYTHONPATH=src py -3.12 -m errcode_atlas bench            # 扫了 746 个 case
PYTHONPATH=src py -3.12 -m errcode_atlas selftest         # 全绿

# 数据链（三步，顺序不能颠倒）
py -3.12 tools/fetch_sources.py --check
py -3.12 tools/extract_catalog.py --check
py -3.12 tools/build_catalog.py --check

# 测试（两条通道；看计数时去掉 -q）
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 py -3.12 -m pytest
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 py -3.8 -m pytest

# 发布（M6）
gh api -X GET search/repositories -f q='errcode-atlas in:name'   # 名字占用
git tag -a v0.1.0 -m "errcode-atlas v0.1.0"
git archive --format=zip -o errcode-atlas-0.1.0.zip v0.1.0       # 从 tag 树构建附件
sha256sum errcode-atlas-0.1.0.zip > SHA256SUMS
gh release create v0.1.0 --title "v0.1.0" --notes-file plan/RELEASE-M6.md \
   errcode-atlas-0.1.0.zip SHA256SUMS
gh release download v0.1.0 --dir dist-release                     # 回下载对账
sha256sum -c SHA256SUMS
```

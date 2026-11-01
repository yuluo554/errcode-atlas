# RELEASE-M6 · errcode-atlas v0.1.0

> **两栏结构**（K33）：§一 只写 **tag 之前**就能知道的事实；§二 写 **tag 之后**才知道的事实。
> tag 树里**不得**出现自指值（附件 sha256 / CI run id）—— 那些只能在 tag 之后的新提交里追加。
>
> 状态：本文在 `git tag` **之前**落盘。§二 现在是骨架，收尾时据实追加，**不回填、不美化**。

---

## 一、tag 前事实

### 1.1 名字占用（建仓之前重核）

`plan/06` §4.1 记的是 **2026-11-01 的快照**，结果可能变，所以建仓前按 M6 DoD 第一条重核一次。

| 核对项 | 命令 | 2026-11-01 复核结果 |
|---|---|---|
| GitHub 仓库名 | `gh api -X GET search/repositories -f q='errcode-atlas in:name'` | `total_count = 0` |
| GitHub 变体 | `gh api -X GET search/repositories -f q='errcode_atlas in:name'` | `total_count = 0` |
| 目标仓库本身 | `gh api repos/yuluo554/errcode-atlas` | HTTP **404**（尚未建仓） |
| PyPI 包名（连字符） | `curl -o /dev/null -w '%{http_code}' https://pypi.org/pypi/errcode-atlas/json` | **404** |
| PyPI 包名（下划线） | `curl -o /dev/null -w '%{http_code}' https://pypi.org/pypi/errcode_atlas/json` | **404** |

结论：**名字未被占用**，可按 `yuluo554/errcode-atlas` 建仓，包名 `errcode-atlas` 无映射冲突。

### 1.2 版本与 tag 名

| 项 | 值 | 出处 |
|---|---|---|
| 版本 | `0.1.0` | `src/errcode_atlas/__init__.py::__version__` 与 `pyproject.toml` `[project] version` 两处相等 |
| tag 名 | `v0.1.0` | 由版本推出（annotated tag） |
| 附件名 | `errcode-atlas-0.1.0.zip` | 由版本推出，**从 tag 树构建** |
| PyPI 发布 | **不适用** | M6 DoD 只要求 GitHub Release 附产物；本里程碑不做 PyPI 上传（仅核名字未被占用） |

### 1.3 tag 之前已跑过的门与测试

| 项 | 命令 | 结果 |
|---|---|---|
| 布局门 | `py -3.12 tools/check_sprint_layout.py` | 全绿（8 项 PASS） |
| 脱敏门 | `py -3.12 tools/check_desensitized.py` | 扫 1561 个文本文件，0 命中 |
| 门的变异验证 | `py -3.12 tools/verify_gates.py` | 逐组 CAUGHT，还原后复绿（组数见 §二 收尾记录） |
| 生成器冻结态 | `py -3.12 tools/build_catalog.py --check` | exit 0 |
| 发布门（pre-tag 档） | `py -3.12 tools/check_release.py --pre-tag` | 全绿 |
| 全量测试 3.12 通道 | `PYTHONPATH=src py -3.12 -m pytest` | **4060 passed** |
| 全量测试 3.8 通道 | `PYTHONPATH=src py -3.8 -m pytest` | **4059 passed + 1 skip**（3.10+ 属性，见 `plan/06` §5） |
| 基准语料 | `PYTHONPATH=src py -3.12 -m errcode_atlas bench` | 扫 **746** 个 case，**0 项不符** |
| 自测 | `PYTHONPATH=src py -3.12 -m errcode_atlas selftest` | 全绿 |

> **CI 在首推之前不作任何"绿"的表述**（`plan/05` §4 U1）。上表全部是**本地等价校验**；
> 真实 run id 属 tag 之后的事实，记在 §二。

### 1.4 覆盖对账

`plan/05` §2 的 M6 DoD 共六条，逐条对到"证据在哪、这次做到什么程度"。
**三态的含义**：`实现` = 已有可指认证据；`不适用` = 本里程碑范围内确实不做；`待首推` = 依赖远端，尚未发生。

| DoD 条目 | 态 | 证据 / 原因 |
|---|---|---|
| 名字占用核对在建仓**之前** | 实现 | §1.1 五项命令与结果，复核日期 2026-11-01 |
| `tools/check_release.py` 三档（`--pre-tag` / `--offline` / `--online`）无 FAIL | 实现 | `tools/check_release.py` 已落盘；`--pre-tag` 与 `--offline` 本地全绿，`--online` 待远端 |
| `plan/RELEASE-M6.md` 在 tag **之前**落盘（两栏 + 覆盖对账 + 三态行） | 实现 | 即本文；两栏齐、本章即覆盖对账、三态行见本表 |
| PyPI 包发布 | 不适用 | M6 DoD 不含 PyPI 上传；本里程碑只核名字未被占用（§1.1），不做 `twine upload` |
| `git tag -a v0.1.0` + GitHub Release 附 ≥1 个手工上传附件 + `SHA256SUMS` | 待首推 | 依赖已建的远端与已打的 tag；执行记录写 §二 |
| 附件与 `git archive <tag>` 导出树的共有文件逐字节同源 + 回下载 `sha256sum -c` | 待首推 | 同属 tag 之后；判据是 `check_release.py --offline` 的 `RELEASE.SOURCE` / `RELEASE.DOWNLOAD` |
| 首推 CI 真绿（写 run id，不写"预期绿"） | 待首推 | `plan/05` §4 U1 的关闭条件；run id 记 §二 |

---

## 二、tag 后追加

> 本节在 tag **之后**的提交里填充。填充前保持骨架原样 —— 提前写数字就是"用未来的事实写了过去"。

### 2.1 tag 事实

| 项 | 值 |
|---|---|
| tag | 待追加 |
| tag 类型 | 待追加（必须是 annotated） |
| tag 指向的提交 | 待追加 |

### 2.2 附件事实

| 项 | 值 |
|---|---|
| 附件名 | `errcode-atlas-0.1.0.zip` |
| 本地副本 | `dist-release/errcode-atlas-0.1.0.zip` |
| 附件 sha256 | 待追加 |
| 附件与 tag 树同源 | 待追加（由 `--offline` 的 `RELEASE.SOURCE` 判定） |
| 回下载对账 | 待追加（由 `--offline` 的 `RELEASE.DOWNLOAD` 判定） |

### 2.3 首推 CI 与 Release

| 项 | 值 |
|---|---|
| GitHub Release | 待追加 |
| run id | 待追加 |
| 首推结果 | 待追加（红了几轮、修了什么，据实写） |
| `--online` 档结论 | 待追加 |

### 2.4 收尾时的本地等价校验

| 项 | 值 |
|---|---|
| 布局门 / 脱敏门 / 发布门（`--pre-tag` / `--offline`） | 待追加 |
| `verify_gates.py` 组数 | 待追加 |
| 全量测试双通道 | 待追加 |
`
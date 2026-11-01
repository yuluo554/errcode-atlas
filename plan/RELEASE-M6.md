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
| 名字占用核对在建仓**之前** | 实现 | §1.1 五项命令与结果，复核日期 2026-11-01；重核在 `gh repo create` **之前**执行 |
| `tools/check_release.py` 三档（`--pre-tag` / `--offline` / `--online`）无 FAIL | 实现 | 三档均无 FAIL：pre-tag 5 项、offline 9 项、online 11 项（见 §2.4） |
| `plan/RELEASE-M6.md` 在 tag **之前**落盘（两栏 + 覆盖对账 + 三态行） | 实现 | 本文即证据：tag `v0.1.0` 指向的提交里已含本文件（`RELEASE.TREE` 判过），两栏齐、本章即覆盖对账 |
| PyPI 包发布 | 不适用 | M6 DoD 不含 PyPI 上传；本里程碑只核名字未被占用（§1.1），不做 `twine upload` |
| `git tag -a v0.1.0` + GitHub Release 附 ≥1 个手工上传附件 + `SHA256SUMS` | 实现 | tag 为 annotated（§2.1）；Release 附 **2 个**手工附件（§2.3），口径 A 满足 |
| 附件与 `git archive <tag>` 导出树的共有文件逐字节同源 + 回下载 `sha256sum -c` | 实现 | `RELEASE.SOURCE` 比过 1566/1566 个文件的字节；回下载 `sha256sum -c` → OK、`cmp` 逐字节相同（§2.2） |
| 首推 CI 真绿（写 run id，不写"预期绿"） | 实现 | run **`41320856857`** = success，8/8 job（§2.3 含三轮红的真因与修法） |

---

## 二、tag 后追加

> 本节在 tag **之后**的提交里填充。以下是**真实跑过的事实**，不是预填。

### 2.1 tag 事实

| 项 | 值 |
|---|---|
| tag | `v0.1.0` |
| tag 类型 | **annotated**（`git cat-file -t v0.1.0` → `tag`；tag 对象 `07e28f9…`） |
| tag 指向的提交 | `a380f11e1316b71d1c7531c84c427bb3d09750a7`（= CI run 41320856857 的 head） |
| tag 里 `plan/RELEASE-M6.md` | 在（`git cat-file -e v0.1.0:plan/RELEASE-M6.md` 成功），且**无自指值** |

### 2.2 附件事实

| 项 | 值 |
|---|---|
| 附件名 | `errcode-atlas-0.1.0.zip`（2,642,577 字节 / 1566 个文件） |
| 本地副本 | `dist-release/errcode-atlas-0.1.0.zip`（`dist-release/` 在 `.gitignore` 里，不入仓） |
| 附件 sha256 | `4fc72f52c16ee8fa3d92320e9ba6a4924a9ce93e76b3c3342ac3a8cf3f916819` |
| 构建方式 | `git archive --format=zip --prefix=errcode-atlas-0.1.0/ -o … v0.1.0`（**从 tag 树**） |
| 附件与 tag 树同源 | **通过**：`--offline` 的 `RELEASE.SOURCE` —— 文件集合相等 + 每文件字节相等（1566/1566）。zip 的单一顶层前缀由 `_strip_single_root` 剥掉再比，包装层不算内容差异 |
| 回下载对账 | **通过**：`gh release download v0.1.0` → `sha256sum -c SHA256SUMS` → `errcode-atlas-0.1.0.zip: OK`；回下载件与本地副本 `cmp` 逐字节相同（zip 与 SUMS 两个文件都比过） |

> **附件 sha256 为什么可以直接写在 §二**：它是 tag **之后**才算出的事实。tag 树里的
> `plan/RELEASE-M6.md` 仍是骨架 —— `RELEASE.TREE` 判据同时看两个面（§一 与 tag 树），
> 追加进 §二 不会让那条判据变红。

### 2.3 首推 CI 与 Release

| 项 | 值 |
|---|---|
| GitHub Release | <https://github.com/yuluo554/errcode-atlas/releases/tag/v0.1.0>（public） |
| 手工上传附件 | **2 个**：`errcode-atlas-0.1.0.zip` + `SHA256SUMS`（口径 A 满足，K34） |
| **成功的 run id** | **`41320856857`**（success，8/8 job：layout ×2、test ×4、offline ×1） |
| 首推结果 | **红了三轮**，三轮红的都是**作业边界**，不是判定逻辑：见下表 |

| 轮次 | run id | 结论 | 真因 | 修法 |
|---|---|---|---|---|
| 一推 | `41319976671` | 4 个 test job 绿；layout ×2 + offline 红 | `build_catalog.py --check` 是 dev 侧工具要 PyYAML：layout job 从不装 dev 依赖（本机系统 Python 恰好装着，掩盖了）；offline 镜像按纪律**故意不装**，却也被要求跑它 | layout 补"安装生成侧依赖"步；offline 改为只跑运行期路径 |
| 二推 | `41320337728` | 7/8 绿，只剩 offline | 替换进去的发布门要 `git ls-tree` / `git cat-file`，而 `python:3.12-slim` **没有 git 二进制**（报 `FileNotFoundError: 'git'`） | 发布门移回 layout job；`git_text` 缺位时抛 `GateEnvError` 报"环境缺件" |
| 三推 | `41320856857` | **8/8 全绿** | — | 补 `test_offline_ci_job_does_not_run_git_dependent_or_dev_side_commands` 作回归判据（已做阴性验证：塞回去当场红） |

> **两推是同一族真缺陷**：判别式不是"命令跑得动吗"，而是
> **"这条命令只需要运行期路径吗？"** —— 两条入选判据：不吃第三方包、不读 git 元数据。
> 离线镜像里只该有"两条都满足"的命令。写进 `ci.yml` 的注释与那条回归判据。

> **U1/U2/U3/U4 的关闭证据**（`plan/05` §4）：
> * U1（CI 实跑）→ run **41320856857** success；
> * U2（3.10/3.11/3.13）→ 矩阵 `3.10` 与 `3.12` 在 ubuntu/windows 四格全绿（3.11/3.13 仍未测）；
> * U3（`--network none`）→ offline job 绿：无网络容器里两道门 + `build --check` + `selftest` 全过；
> * U4（windows runner 编码）→ windows 两格绿：`PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8` 生效，中文输出正常。

### 2.4 收尾时的本地等价校验

| 项 | 值 |
|---|---|
| 布局门 | 全绿（8 项 PASS，扫 11 文档 / 7 交接单 / 3 状态副本 / 7 文档点名工具） |
| 脱敏门 | 扫 1565 个文本文件，0 命中（豁免 1 份） |
| 发布门 `--pre-tag` / `--offline` / `--online` | 三档全绿（online 11 项、offline 9 项） |
| `verify_gates.py` | **27 组**全 CAUGHT（布局门 14 + 脱敏门 5 + 发布门 8），还原后三道门复绿 |
| 全量测试 `py -3.12` | **4085 passed** |
| 全量测试 `py -3.8` | **4084 passed + 1 skip**（3.10+ 属性，见 `plan/06` §5） |
| `bench` / `selftest` | 扫 **746** 个 case，0 项不符 / 全绿 |

> **一次发布面真缺陷（由回下载对账当场抓到）**：我第一次写出的 `SHA256SUMS` 是 **CRLF**
> ——Windows 上写文件默认如此。`sha256sum -c` 把文件名读成 `errcode-atlas-0.1.0.zip\r`
> → `No such file or directory`，**下载者的第一条校验命令就失败**（附件本身没问题，坏的是
> 那个校验清单）。修法 = 归一成 LF 重传，并给 `RELEASE.DIGEST` 加"字节里不许有 CR"的判据
> + 一条测试（判据落在**字节**上而不是行内容上 —— 后者会把 `\r` 当空白吃掉，静默通过）。

> **另一次（同属发布面，由收尾提交当场抓到）**：`dist-release/` 在脱敏门的 `SKIP_DIRS` 里
> 却**不在 `.gitignore`** 里 —— 对齐测试只查了「gitignore → 门」一个方向，于是这个缺口
> 两个方向都看不见，收尾时 `git add -A` 把 **2.6 MB 的附件与回下载件一起提交了进去**。
> 附件是 tag 树的派生件、已在 Release 上；入库等于同一份内容存三遍。
> 修法 = `.gitignore` 补 `dist-release/`（与 `dist/` / `build/` 同列）、把已入库的那批 `git rm --cached`，
> 并补两条判据：`test_publish_artifact_dirs_are_ignored_and_skipped`（双向对齐，已做阴性验证）
> 与 `test_release_attachments_are_not_tracked_in_git`（问的是 **git 索引**，不是磁盘）。
`
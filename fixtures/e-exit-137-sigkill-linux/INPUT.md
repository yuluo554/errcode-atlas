# e-exit-137-sigkill-linux

## 用户会怎么问

> 进程退出码 137，平台 linux，怎么解释？

## 来源（写真值之前先写这一节 —— K24）

128+9 = 137；linux signal.h:20 `#define SIGKILL 9`

## 判定面

- 命令：`errcode-atlas exitcode 137 --platform linux`
- 判据：`data/README.md` §5.3 + `plan/03` §3.2 判定顺序表

## 真值怎么写的（不是从实现回填）

`expected.json` 的每条都由**独立的第二份推导**从 `data/catalog/*.yaml` 出发、按上表判据算出，
全程 **不 import `errcode_atlas`**（所以不是 `explain` 的输出回填 —— K24）。
分叉点数值另与 `_headers/` 原文逐条对过一遍。

> 那份推导脚本**刻意不入仓**：一旦入库，任何人改完编目重跑一次就能让 `expected.json`
> 跟着变，`bench` 于是恒绿 —— 那正是 K24 要挡的循环论证。真值的落点只有本 case 的
> 两个文件，来源见上一节。

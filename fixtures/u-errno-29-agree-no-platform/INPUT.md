# u-errno-29-agree-no-platform

## 用户会怎么问

> errno 29 在四个平台上是不是同一个意思？（各平台一致 → 不该判歧义）

## 来源（写真值之前先写这一节 —— K24）

ESPIPE=29 四轴同值同名（linux/macos 头文件 + 两个运行时视角）

## 判定面

- 命令：`errcode-atlas explain 29 --domain errno`
- 判据：`data/README.md` §5.2 + `plan/03` §2.2 判定顺序表

## 真值怎么写的（不是从实现回填）

`expected.json` 由**独立的第二份推导**从 `data/catalog/*.yaml` 出发、按 §5.2 判据算出，
全程 **不 import `errcode_atlas`**（K24）。那条推导脚本刻意不入仓 —— 一旦入库，
改完编目重跑一次就能让 `expected.json` 跟着变，`bench` 于是恒绿。

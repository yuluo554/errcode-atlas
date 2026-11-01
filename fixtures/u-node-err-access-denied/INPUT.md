# u-node-err-access-denied

## 用户会怎么问

> ERR_ACCESS_DENIED 是什么错误？（node 无数字码值，只有名字）

## 来源（写真值之前先写这一节 —— K24）

nodejs.org/api/errors.html#err_access_denied（现行小节）

## 判定面

- 命令：`errcode-atlas explain ERR_ACCESS_DENIED --platform linux --domain node`
- 判据：`data/README.md` §5.2 + `plan/03` §2.2 判定顺序表

## 真值怎么写的（不是从实现回填）

`expected.json` 由**独立的第二份推导**从 `data/catalog/*.yaml` 出发、按 §5.2 判据算出，
全程 **不 import `errcode_atlas`**（K24）。那条推导脚本刻意不入仓 —— 一旦入库，
改完编目重跑一次就能让 `expected.json` 跟着变，`bench` 于是恒绿。

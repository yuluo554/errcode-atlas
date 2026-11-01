"""errcode-atlas —— 三平台错误码与退出码判定表。

判定对象：给定「一个数字 + 一个平台 + 一个语境」，它能不能被唯一归因。
口径的唯一定义处是 ``data/README.md`` §5；本包的 ``contract.py`` 是它的**解析结果**，
由 ``tests/test_contract.py`` 做集合相等的双向断言。
"""

__version__ = "0.1.0"
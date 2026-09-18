# -*- coding: utf-8 -*-
u"""印出这个仓今天允许的答案值 —— **给说明书一个可指的地方,别再手抄。**

为什么有这个文件:设计文档里写了一句「答案域三个:`是` / `否` / `答不了`」。
后来加了找反例那一档(「过」=「没找到」),答案值变成两组,说明书跟着改了,
设计文档没有 —— 而且**全篇一次都没提过新那组**。照设计文档那句写出来的报告,
实跑当场被判决那一步拒掉。没有任何东西发现这件事,直到一个人逐句去核。

它什么都不检查,只印。真正的闸在 `tools/readme_cmds.py`:那份会把
README / CLAUDE.md / docs/DESIGN.md 里印的每条命令都起一遍 ——
所以这条指路的命令一旦死了,当场就红。

    python3 tools/answerdomain.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from done.judge import 答域  # noqa: E402


def main():
    for 过 in (u"是", u"否", u"没找到"):
        print(u"「过」写「%s」的那一条,答案只能是:%s" % (过, u" / ".join(答域(过))))
    return 0


if __name__ == u"__main__":
    sys.exit(main())

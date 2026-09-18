# -*- coding: utf-8 -*-
u"""印出开卡那道门认的那两个承重栏名 —— **给说明书一个可指的地方,别再手抄。**

这两个名字是「开工前查了记忆库没有」那条记录里真正承重的两栏:数数的工具
(`tools/lookupstat.py`)只读它们,写岔一个字,那个数就静默归零。说明书抄过一份,
抄一份漂一份 —— 这个仓在手抄的值上已经栽过四轮。

它什么都不检查,只印 —— 这样为什么还拦得住漂移,写在 `tools/answerdomain.py` 顶上,
**不在这儿抄第二份**(抄了就会被 `tools/saidtwice.py` 当场逮住,那正是它管的事)。

**这段原来住在 `tools/opencheck.py` 里。** 那个文件开头写着「只判一件事:拦还是放」,
而这段什么都不判、永远返回 0,当时给它写了一句豁免。审阅人把两个方向都量了一遍:
删掉它,那道闸一行不用改;把闸整个搬走,它也一行不用改 —— 两边只共用一个常量。
压垮它的是同一天加的 `tools/answerdomain.py`:形状一模一样(只印、指路、不检查),
而那个是单独一个文件。**同一条标准,对一块执行、对另一块例外,那就不是标准。**

    python3 tools/lookupcols.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from done.opencheck import 承重栏  # noqa: E402


def main():
    # **这不是白名单。** 别的栏随便写,那是给人看的备注;这两个是承重的,至少得有一个。
    print(u"\n".join(承重栏))
    return 0


if __name__ == u"__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
u"""规矩表里点名的那个执行器,盘上真有这个东西吗。

**为什么要有这道。** R4 的执行器一度写着 `ledger.ReadOnly.append`。审阅人把那段代码
整个删掉,开卡、判决、沉淀、验账四步全部照常跑通 —— 全仓没有任何真实路径构造过它。
也就是说那一栏点的是一个谁也没接上的东西,而**一条没接上的防线和一条不存在的防线是一样的**。

盘上当时没有任何东西发现:那一栏只是一串**打印出来给人看的字**,谁也没去解析它。
于是「执行器还活着」和「执行器这个名字是编的」在开机那一屏上逐字同形。现在去解一遍。

**这道只管「这个名字指得着东西」,不管「它真的在那条路上被调用」**——后者要读懂那件活,
那是判官那一档的事(体检卡上「有没有文件在干多件事」旁边那几条)。别把这道说成它不是的东西。

名字怎么解:`check.main` 按仓库根上的模块解,其余按 `done.<模块>` 解。
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from done.rules import RULES  # noqa: E402


def 解(名):
    u"""`ledger.verify` → done.ledger.verify。解不开就说清卡在哪一截。"""
    段 = 名.split(u".")
    模块 = 段[0] if 段[0] == u"check" else u"done." + 段[0]
    try:
        o = importlib.import_module(模块)
    except ImportError:
        return u"找不到模块 %s" % 模块
    走过 = 模块
    for 名字 in 段[1:]:
        if not hasattr(o, 名字):
            return u"%s 里没有 %s" % (走过, 名字)
        o = getattr(o, 名字)
        走过 += u"." + 名字
    return None


def 查(rules):
    return [(r[u"id"], r[u"执行器"], 话)
            for r in rules for 话 in [解(r[u"执行器"])] if 话]


def main(argv=None):
    坏 = 查(RULES)
    for i, 名, 话 in 坏:
        sys.stderr.write(u"%s 的执行器点着 %s,可是 %s —— "
                         u"这一栏点的是个不存在的东西\n" % (i, 名, 话))
    print(u"规矩表 %d 条,执行器解不开的 %d 条" % (len(RULES), len(坏)))
    return 1 if 坏 else 0


if __name__ == u"__main__":
    sys.exit(main())

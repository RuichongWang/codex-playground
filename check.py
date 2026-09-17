# -*- coding: utf-8 -*-
u"""R7 的执行器:遍历规矩册,每条跑一次必红用例和一次绿对照。

**必红用例没红 = 判红。** 一条永远绿的用例证明不了执行器还活着;
一条因为错的理由而通过的检查,比没有检查更糟。
"""
import sys

import redcases
from done.rules import RULES, check_cap


def main(argv=None):
    check_cap()
    bad = []
    for r in RULES:
        red = getattr(redcases, r[u"必红"])()
        green = getattr(redcases, r[u"绿对照"])()
        mark = u"绿"
        if red is not True:
            bad.append((r[u"id"], u"必红用例没红 —— 执行器 %s 今天拦不住它该拦的" % r[u"执行器"]))
            mark = u"红"
        if green is not True:
            bad.append((r[u"id"], u"绿对照没绿 —— %s 在正常那条路上误伤" % r[u"执行器"]))
            mark = u"红"
        print(u"%s %-3s %-34s 执行器 %s" % (mark, r[u"id"], r[u"规矩"], r[u"执行器"]))
    # 沉淀那一步不产生 done,所以它不占规矩位 —— 但没有「会报错的例子」的东西不许进,
    # 所以它在这儿单独跑一遍,只是不算进规矩数。
    for 名, fn in ((u"必红", redcases.reflect_red), (u"绿对照", redcases.reflect_green)):
        if fn() is not True:
            bad.append((u"沉淀", u"%s 没过" % 名))
    print(u"绿 沉淀  写不写二选一,不写也要说为什么          (不是规矩,不计数)")
    for rid, why in bad:
        sys.stderr.write(u"红 %s:%s\n" % (rid, why))
    print(u"\n规矩 %d 条(上限 %d),红 %d" % (len(RULES), 7, len(bad)))
    return 1 if bad else 0


if __name__ == u"__main__":
    sys.exit(main())

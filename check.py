# -*- coding: utf-8 -*-
u"""把每一对「会报错的例子 / 正常通过的例子」各跑一遍。

规矩册里那七条是主体(这是 R7 的执行器);**后面还有几块不在规矩册里的**
(沉淀 · 订正 · 存账 · 说明书范例 · 开卡体检 · 笔记目录树)—— 它们不决定一件活算不算完成,所以不占规矩位,
但「写不出会报错的例子的东西不许进」对它们一样管用,所以在这儿一起跑。

**必红用例没红 = 判红。** 一条永远绿的用例证明不了执行器还活着;
一条因为错的理由而通过的检查,比没有检查更糟。
"""
import sys
import unicodedata

import redcases
from done.rules import RULES, check_cap

# 不在规矩册里的几块。它们不决定一件活算不算完成,所以不占规矩位 ——
# 但「写不出会报错的例子的东西不许进」对它们一样管用,所以在这儿一起跑。
# 这张表就是为了别再出现第四份复制粘贴的 if-else。
非规矩 = [
    (u"沉淀", u"写不写二选一,不写也要说为什么", u"reflect"),
    (u"订正", u"改得动,但每处都要过一次纯模型评审", u"correct"),
    (u"存账", u"账要进 git —— 只在本机的账等于没有账", u"ledger"),
    (u"范例", u"说明书里的判据范例要能真开卡", u"doccards"),
    (u"开卡", u"写坏的判据在开卡那一刻就拦住", u"opencheck"),
    (u"目录", u"笔记里那块目录树要跟盘上对得上", u"notesdirs"),
    (u"命令", u"说明书里印的命令今天还立得住", u"readmecmds"),
    (u"接上", u"规矩表点名的执行器盘上真有", u"rulewired"),
    (u"重话", u"同一句话存了几份,每份都得有人认领", u"saidtwice"),
]


def _宽(s, n):
    u"""按屏幕宽度补空格(一个汉字占两格),让那几行的尾巴对齐。"""
    w = sum(2 if unicodedata.east_asian_width(c) in u"WF" else 1 for c in s)
    return s + u" " * max(1, n - w)


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
    for 名, 说明, 前缀 in 非规矩:
        坏 = [标 for 标, 尾 in ((u"必红", u"_red"), (u"绿对照", u"_green"))
             if getattr(redcases, 前缀 + 尾)() is not True]
        bad.extend((名, u"%s 没过" % 标) for 标 in 坏)
        # 这一行以前是写死的「绿」—— 用例真红了屏幕上照样印绿,只有退出码是对的。
        print(u"%s %s  %s(不是规矩,不计数)" % (u"红" if 坏 else u"绿", 名, _宽(说明, 44)))
    for rid, why in bad:
        sys.stderr.write(u"红 %s:%s\n" % (rid, why))
    print(u"\n规矩 %d 条(上限 %d),红 %d" % (len(RULES), 7, len(bad)))
    return 1 if bad else 0


if __name__ == u"__main__":
    sys.exit(main())

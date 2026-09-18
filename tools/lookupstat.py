# -*- coding: utf-8 -*-
u"""数一数:开过的卡里,开工前真去查过记忆库的有几张,查到有用的有几张,明说没查的有几张。

**这个数没有阈值,也不判红** —— 它是给人看趋势的。
库到底有没有被用上,应当是一个数,不是一种感觉。

**「明说没查」那一栏是后补的。** 开卡那道门放行的条件是「查了什么」「查了没有」至少有一个,
而这份从前只读前者 —— 于是一条老老实实写了「查了没有」的记录,过了门,在这张表上却
和一条栏名写岔了的记录完全同形(两边都是 0),说明书里还写着「数数的工具只读这两个栏名」。
现在两栏都读:门认哪两栏,这儿就数哪两栏。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from done.opencheck import 承重栏  # noqa: E402

L = os.path.join(u".done", u"ledger.jsonl")

# 开卡那道门放行的条件,和这儿数的那两栏,**必须是同一份名单**。
# 上一次它们悄悄分了家:门认两栏,这儿只读一栏,于是一条合法记录在这张表上归零,
# 而说明书还写着「数数的工具只读这两个栏名」—— 没有任何东西发现。现在对不上就当场喊。
认得 = (u"查了什么", u"查了没有")
if set(承重栏) != set(认得):
    sys.stderr.write(u"开卡那道门的承重栏是 %s,这份只会数 %s —— 两边分家了,"
                     u"先把这儿补上再说\n" % (u"、".join(承重栏), u"、".join(认得)))
    sys.exit(2)


def main():
    if not os.path.exists(L):
        print(u"还没有账")
        return 0
    卡, 查过, 有用, 明说没查 = [], 0, 0, 0
    for line in open(L, encoding=u"utf-8"):
        r = json.loads(line)
        if r.get(u"kind") != u"open":
            continue
        q = (r[u"body"] or {}).get(u"查库") or {}
        卡.append(r[u"body"][u"card"])
        if q.get(u"查了什么"):
            查过 += 1
            if q.get(u"用上了"):
                有用 += 1
        elif q.get(u"查了没有"):
            明说没查 += 1
    print(u"开过 %d 张卡:开工前查过库的 %d 张,其中查到并真用上的 %d 张;"
          u"明说没查的 %d 张,剩下 %d 张这一栏根本没记"
          % (len(卡), 查过, 有用, 明说没查, len(卡) - 查过 - 明说没查))
    return 0


if __name__ == u"__main__":
    sys.exit(main())

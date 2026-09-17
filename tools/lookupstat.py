# -*- coding: utf-8 -*-
u"""数一数:开过的卡里,开工前真去查过记忆库的有几张,查到有用的有几张。

**这个数没有阈值,也不判红** —— 它是给人看趋势的。
库到底有没有被用上,应当是一个数,不是一种感觉。
"""
import json
import os
import sys

L = os.path.join(u".done", u"ledger.jsonl")


def main():
    if not os.path.exists(L):
        print(u"还没有账")
        return 0
    卡, 查过, 有用 = [], 0, 0
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
    print(u"开过 %d 张卡:开工前查过库的 %d 张,其中查到并真用上的 %d 张" % (len(卡), 查过, 有用))
    return 0


if __name__ == u"__main__":
    sys.exit(main())

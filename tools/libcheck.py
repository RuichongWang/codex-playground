# -*- coding: utf-8 -*-
u"""查某一批新进记忆库的条目:数够了没有、有没有只记事不猜的。

用来源(`source`)认这一批 —— 谁写进去的,写的时候就标死了。
"""
import json
import os
import sys

DB = os.path.join(u"pattern", u"runs", u"r3", u"library.json")
SRC = u"ONE考据"


def main():
    if not os.path.exists(DB):
        sys.stderr.write(u"库文件不在:%s\n" % DB)
        return 1
    d = json.load(open(DB, encoding=u"utf-8"))
    nodes, links = d[u"nodes"], d[u"links"]
    这批 = [n for n in nodes.values() if n.get(u"kind") == u"item" and n.get(u"source") == SRC]
    挂过 = set(l[u"src"] for l in links) | set(l[u"dst"] for l in links)
    光记事 = [n[u"id"] for n in 这批 if n[u"id"] not in 挂过]
    print(u"来源「%s」的事件 %d 条,其中一条猜测都没挂的 %d 条" % (SRC, len(这批), len(光记事)))
    for i in 光记事:
        sys.stderr.write(u"只记事不猜:%s %s\n" % (i, nodes[i][u"what"][:60]))
    return 1 if (len(这批) < 15 or 光记事) else 0


if __name__ == u"__main__":
    sys.exit(main())

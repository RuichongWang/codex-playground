# -*- coding: utf-8 -*-
u"""说要往记忆库里写的那几轮,到底有几轮真落进去了 —— **只印数,不拦人。**

说明书上原来写着「每次验收产出一条带硬结局的经历写回库里,而一条被反复撞上的
猜测凝固成判据包里的一条」。两句都不是当时的实情:账上三条沉淀全写着「写」,
库里只追得到一条;判据包那一侧一条都没有。**「说要写」和「真写了」在账上完全同形** ——
沉淀那一步落的是决定,落地是后来在库那一侧发生的事,中间没有任何东西把两头对上。

所以这儿不写成一道闸:一条今天决定要写的,明天才落地是正常的,拿它当闸门
要么恒红要么恒绿。它只把两头的数摆出来,让说明书有个可指的地方,别再手抄。

    python3 tools/reflectland.py
"""
import io
import json
import os
import re
import sys

账 = os.path.join(u".done", u"ledger.jsonl")
库 = os.path.join(u"pattern", u"runs", u"r3", u"library.json")
包 = os.path.join(u"packs")
自省 = u"自省"


def 沉淀们(p=账):
    if not os.path.exists(p):
        return []
    出 = []
    for l in io.open(p, encoding=u"utf-8"):
        r = json.loads(l)
        if r.get(u"kind") == u"reflect":
            出.append(r[u"body"])
    return 出


def 挂的猜测(b):
    u"""这一条沉淀点名挂到了哪几条猜测上。写法有两种:一个字符串,或者一串对象。"""
    x = b.get(u"挂到") or []
    if isinstance(x, (str, type(u""))):
        x = [{u"pattern": x}] if x.strip() else []
    return [y.get(u"pattern") for y in x if isinstance(y, dict) and y.get(u"pattern")]


def 库里认领的(p=库):
    u"""库里那些标着「来自自省」的边,碰过哪几条猜测。"""
    if not os.path.exists(p):
        return set()
    d = json.loads(io.open(p, encoding=u"utf-8").read())
    出 = set()
    for e in d.get(u"links") or []:
        if 自省 in u"%s" % (e.get(u"source") or u""):
            出.add(e.get(u"src"))
            出.add(e.get(u"dst"))
    return 出


def 包里引库的(d=包):
    u"""判据包里有几条能追回库里某一条猜测(写法是文里出现 P123 这样的号)。"""
    if not os.path.isdir(d):
        return 0, 0
    条, 引 = 0, 0
    for f in sorted(os.listdir(d)):
        if not f.endswith(u".json"):
            continue
        pk = json.loads(io.open(os.path.join(d, f), encoding=u"utf-8").read())
        for c in pk.get(u"判据") or []:
            条 += 1
            if re.search(u"\\bP[0-9]+\\b", json.dumps(c, ensure_ascii=False)):
                引 += 1
    return 条, 引


def main():
    认领 = 库里认领的()
    要写 = [b for b in 沉淀们() if b.get(u"写不写") == u"写"]
    追得到, 追不到 = [], []
    for b in 要写:
        (追得到 if [x for x in 挂的猜测(b) if x in 认领] else 追不到).append(b.get(u"card"))
    print(u"沉淀 %d 条,其中说「写」的 %d 条;库里真追得回来的 %d 条"
          % (len(沉淀们()), len(要写), len(追得到)))
    if 追不到:
        # 不判红:今天决定、明天落地是正常的。但得说出来,别让沉默读成「都落地了」。
        print(u"  这几张卡说了写、库里还追不回来:%s" % u"、".join(追不到))
    条, 引 = 包里引库的()
    print(u"判据包 %d 条,其中追得回库里某一条猜测的 %d 条" % (条, 引))
    return 0


if __name__ == u"__main__":
    sys.exit(main())

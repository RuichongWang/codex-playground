# -*- coding: utf-8 -*-
u"""账:一行一个事实,hash 链把「改过」和「没改过」分开(R1)。

链头必须从外部传进来。**它挡的是静默篡改,不是有决心的对手** —— 读得到头的进程
就能把它传对(`U2`)。写下这句是因为一个被高估的防线比没有防线更坏。
"""
import hashlib
import json
import os
import time

GENESIS = u"0" * 64


class Refused(Exception):
    u"""一次拒绝。`code` 给机器看,`why` 给人看,两样都要。"""

    def __init__(self, code, why):
        self.code = code
        self.why = why
        Exception.__init__(self, u"[%s] %s" % (code, why))


def canon(obj):
    u"""规范化字节。hash 认的是字节,所以这一处不许有第二种写法。"""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(u",", u":")).encode(u"utf-8")


def _hash(prev, core):
    h = hashlib.sha256()
    h.update(prev.encode(u"utf-8"))
    h.update(canon(core))
    return h.hexdigest()


def read(path):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, u"rb") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line.decode(u"utf-8")))
    return rows


def head(path):
    rows = read(path)
    return rows[-1][u"hash"] if rows else GENESIS


def verify(path):
    u"""顺着链走一遍。返回 (ok, 哪一行坏了)。"""
    prev = GENESIS
    for i, r in enumerate(read(path)):
        try:
            core = dict((k, r[k]) for k in (u"seq", u"ts", u"kind", u"body"))
        except KeyError as e:
            return False, u"第 %d 行缺字段 %s" % (i, e)
        if r.get(u"prev") != prev:
            return False, u"第 %d 行 prev 接不上上一行" % i
        if r.get(u"hash") != _hash(prev, core):
            return False, u"第 %d 行 hash 对不上 —— 这一行被改过" % i
        prev = r[u"hash"]
    return True, u""


def append(path, kind, body, chain_head):
    u"""只此一处写入。链头对不上、或者账本身已经断了,一律不写(R1)。"""
    rows = read(path)
    cur = rows[-1][u"hash"] if rows else GENESIS
    if chain_head != cur:
        raise Refused(u"chain-head-stale",
                      u"传进来的链头不是账上的头。现在的头是 %s" % cur)
    ok, why = verify(path)
    if not ok:
        raise Refused(u"ledger-broken", why)
    core = {u"seq": len(rows), u"ts": int(time.time()), u"kind": kind, u"body": body}
    row = dict(core)
    row[u"prev"] = cur
    row[u"hash"] = _hash(cur, core)
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, u"ab") as f:
        f.write(canon(row) + b"\n")
    return row


class ReadOnly(object):
    u"""判决那只手拿到的句柄:读得到,写不了(R4 的进程内那一半)。"""

    def __init__(self, path):
        self._p = path

    def read(self):
        return read(self._p)

    def head(self):
        return head(self._p)

    def append(self, *a, **k):
        raise Refused(u"judge-cannot-append", u"判的那只手写不到账")

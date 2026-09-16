# -*- coding: utf-8 -*-
u"""卡:accept criteria 在干活之前就定死,落账即冻结(R2 · R3 · R6)。"""
import hashlib
import json

from done.ledger import Refused, append, canon, read

档表 = (u"auto", u"eye")
# 「谁」这一格写成下面这些,等于没写 —— 一个不指向具体人的兜底不是兜底。
无人词 = (u"人工", u"人工复核", u"人", u"相关人员", u"大家", u"以后再说", u"tbd")


def spec_hash(accept):
    return hashlib.sha256(canon(accept)).hexdigest()


def load(path):
    with open(path, u"rb") as f:
        return json.loads(f.read().decode(u"utf-8"))


def validate(accept):
    u"""一张卡的 accept 合不合法。至少一条 auto,否则 done 退化成自评(R2)。"""
    if not isinstance(accept, list) or not accept:
        raise Refused(u"accept-empty", u"一张卡必须至少有一条 accept")
    seen = set()
    autos = 0
    for c in accept:
        cid = c.get(u"id")
        if not cid:
            raise Refused(u"accept-id", u"每条 accept 要有 id")
        if cid in seen:
            raise Refused(u"accept-id", u"id 重了:%s" % cid)
        seen.add(cid)
        if not c.get(u"判据"):
            raise Refused(u"accept-claim", u"%s 没写判据" % cid)
        arch = c.get(u"档")
        if arch not in 档表:
            raise Refused(u"accept-arch", u"%s 的档要是 auto 或 eye" % cid)
        if arch == u"auto":
            autos += 1
            v = c.get(u"怎么验") or {}
            if not v.get(u"cmd"):
                raise Refused(u"accept-cmd", u"%s 是 auto,要给一条 cmd" % cid)
            if not v.get(u"期望") and not v.get(u"stdout_contains"):
                raise Refused(u"accept-expect", u"%s 要写期望:exit0 或 stdout_contains" % cid)
        else:
            d = c.get(u"靠什么兜") or {}
            who, what = (d.get(u"谁") or u"").strip(), (d.get(u"看什么") or u"").strip()
            if not who or not what:
                raise Refused(u"accept-eye", u"%s 是 eye,要写「谁」和「看什么」" % cid)
            if who.lower() in 无人词:
                raise Refused(u"accept-eye-nobody",
                              u"%s 的「谁」写成了 %s —— 不指向一个具体的人,等于没写" % (cid, who))
    if autos == 0:
        raise Refused(u"no-auto",
                      u"一张卡至少要有一条 auto —— 全是 eye 的卡,done 就退化成自评")
    return True


def registered(ledger_path, card_id):
    u"""这张卡当前生效的 spec_hash:最后一条 open/amend 说了算。没开过返回 None。"""
    cur = None
    for r in read(ledger_path):
        b = r.get(u"body") or {}
        if b.get(u"card") != card_id:
            continue
        if r.get(u"kind") == u"open":
            cur = b.get(u"spec_hash")
        elif r.get(u"kind") == u"amend":
            cur = b.get(u"new_spec_hash")
    return cur


def open_card(ledger_path, card_file, by, chain_head):
    card = load(card_file)
    validate(card[u"accept"])
    if registered(ledger_path, card[u"id"]) is not None:
        raise Refused(u"card-already-open", u"%s 已经开过了,要改走 amend" % card[u"id"])
    body = {u"card": card[u"id"], u"题面": card.get(u"题面", u""),
            u"spec_hash": spec_hash(card[u"accept"]), u"by": by}
    return append(ledger_path, u"open", body, chain_head)


def amend(ledger_path, card_file, why, by, chain_head):
    u"""改 accept 要留疤:落一行,且这张卡此前的 verdict 当场作废(R6)。"""
    card = load(card_file)
    validate(card[u"accept"])
    old = registered(ledger_path, card[u"id"])
    if old is None:
        raise Refused(u"card-not-open", u"%s 还没开过" % card[u"id"])
    new = spec_hash(card[u"accept"])
    if new == old:
        raise Refused(u"amend-noop", u"accept 一个字都没动,不用 amend")
    if not (why or u"").strip():
        raise Refused(u"amend-why", u"改判据必须写为什么")
    body = {u"card": card[u"id"], u"old_spec_hash": old, u"new_spec_hash": new,
            u"why": why, u"by": by, u"作废": u"这张卡此前的 verdict 全部作废"}
    return append(ledger_path, u"amend", body, chain_head)


def effective_verdicts(ledger_path, card_id):
    u"""这张卡**现在还算数**的判决:spec_hash 不等于当前注册值的,一律不算(R6 的作废)。"""
    cur = registered(ledger_path, card_id)
    out = []
    for r in read(ledger_path):
        b = r.get(u"body") or {}
        if r.get(u"kind") == u"verdict" and b.get(u"card") == card_id \
                and b.get(u"spec_hash") == cur:
            out.append(r)
    return out

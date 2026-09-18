# -*- coding: utf-8 -*-
u"""卡:一组判据,在干活之前就定死,落账即冻结(R2 · R3 · R6)。

**一条判据 = 一个只能答「是 / 否 / 答不了」的问题 + 凭什么答 + 哪边算过。**
判者只有两种:一条命令,或者一个读者。没有 rubric 这个概念,它并进来了。
"""
import hashlib
import io
import json
import os

from done.ledger import Refused, append, canon, read
from done.opencheck import 拦
from done.openrun import 开卡实况

# 「过」写成「没找到」的,是一条**找反例**的判据:答域换成 找到 / 没找到 / 答不了。
# 为什么要分开:「有没有哪一条…」答「是」只要举一个反例,答「否」要穷举 ——
# 而报告只装得下一段引文,于是「否」结构上是个免费答案。实测被这么过过一次。
#
# **命令也可以答这类判据,而且答得最硬** —— 一次全量扫描就是最彻底的搜。
# (上一版规定只许人答,理由是「命令不会搜」,那是错的,`tools/deps.py` 当场反证。)
# 约定:这类判据由命令答时,退出码 0 = 没找到,非 0 = 找到。


def spec_hash(accept):
    return hashlib.sha256(canon(accept)).hexdigest()


def load(path):
    return json.loads(io.open(path, encoding=u"utf-8").read())


def expand(card, packs=u"packs"):
    u"""把引的判据包摊开,和本卡自己那几条并在一起。

    `spec_hash` 算的是展开之后那一份,所以**包的内容一改而版本没升,判的时候当场对不上**
    —— 包只能靠升版本演进,改不动老卡。
    """
    out = []
    for ref in card.get(u"引") or ():
        name, _, ver = ref.partition(u"@")
        p = os.path.join(packs, name + u".json")
        if not os.path.exists(p):
            raise Refused(u"pack-missing", u"找不到判据包 %s" % ref)
        pk = load(p)
        if unicode_(pk.get(u"version")) != ver:
            raise Refused(u"pack-version", u"%s 引的是 v%s,盘上是 v%s —— 包只能升版本"
                          % (name, ver, pk.get(u"version")))
        out.extend(pk[u"判据"])
    out.extend(card.get(u"accept") or [])
    return out


def unicode_(x):
    return u"%s" % x


def validate(accept):
    u"""判据合不合法。至少一条由命令来答,否则 done 退化成自评(R2)。"""
    if not isinstance(accept, list) or not accept:
        raise Refused(u"accept-empty", u"一张卡必须至少有一条判据")
    seen, cmds = set(), 0
    for c in accept:
        cid = c.get(u"id")
        if not cid or cid in seen:
            raise Refused(u"accept-id", u"判据要有 id,且不许重:%s" % cid)
        seen.add(cid)
        for k in (u"问", u"过", u"判者", u"凭什么答"):
            if not c.get(k):
                raise Refused(u"accept-field", u"%s 缺「%s」" % (cid, k))
        if c[u"过"] not in (u"是", u"否", u"没找到"):
            raise Refused(u"accept-side", u"%s 的「过」要是「是」「否」或「没找到」" % cid)
        j = c[u"判者"]
        if isinstance(j, dict) and j.get(u"cmd"):
            cmds += 1
        elif not (isinstance(j, dict) and j.get(u"读者")):
            raise Refused(u"accept-judge",
                          u"%s 的判者要么是 {cmd: …},要么是 {读者: 哪一个读者} —— "
                          u"得写明是谁,不然会问出一个他结构上答不了的问题" % cid)
        elif j[u"读者"].strip() in (u"读者", u"判官", u"人"):
            # 设计文档一直写着「只写『读者』会被当场拒」,而拒的只有裸字符串 `"读者"`;
            # 写成 {"读者":"读者"} 照收 —— 说明书教的边界和代码划的边界差了一格,
            # 而这一格正好是这条检查存在的理由:**它没写明是哪一个人**。
            raise Refused(u"accept-judge",
                          u"%s 的判者写成 {读者: %s} —— 这没写明是哪一个人。"
                          u"要写「冷读者」「说明书审阅人」这样的具体名字,"
                          u"不然会问出一个他结构上答不了的问题" % (cid, j[u"读者"]))
    if cmds == 0:
        raise Refused(u"no-cmd",
                      u"一张卡至少要有一条由命令来答 —— 全靠读者的卡,done 就退化成自评")
    return True


def accept_of(card_file, packs=u"packs"):
    a = expand(load(card_file), packs)
    validate(a)
    return a


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


def open_card(ledger_path, card_file, by, chain_head, packs=u"packs", 查库=None,
              repo=u"."):
    u"""开卡。

    `查库` 是开工前那一步的记录:**这类活别处踩过什么坑**。
    它不是验收条件(干活之前的事没法验收),但它落账 —— 于是「库到底有没有被用上」
    是可数的,不是靠感觉。**查了什么都没查到,照样要记**:
    一次空手而归和一次根本没查,不记下来在账面上完全同形。
    """
    card = load(card_file)
    a = accept_of(card_file, packs)
    if registered(ledger_path, card[u"id"]) is not None:
        raise Refused(u"card-already-open", u"%s 已经开过了,要改走 amend" % card[u"id"])
    # 账上改判据的次数一直在长(`python3 -m done.cli log | grep amend` 现数,别在这儿抄),
    # 其中绝大多数是判据自己写坏了。能在这一刻看出来的那几种,在这儿拦住 ——
    # 开卡之后再改就要留疤,而且这张卡之前的判决全部作废,代价差一个量级。
    拦(a, 查库)
    body = {u"card": card[u"id"], u"题面": card.get(u"题面", u""), u"引": card.get(u"引", []),
            u"spec_hash": spec_hash(a), u"条数": len(a), u"by": by,
            u"查库": 查库 or {u"查了没有": u"没查"},
            u"开卡实况": 开卡实况(a, repo)}
    return append(ledger_path, u"open", body, chain_head)


def amend(ledger_path, card_file, why, by, chain_head, packs=u"packs"):
    u"""改判据要留疤:落一行,且这张卡此前的 verdict 当场作废(R6)。"""
    card = load(card_file)
    a = accept_of(card_file, packs)
    old = registered(ledger_path, card[u"id"])
    if old is None:
        raise Refused(u"card-not-open", u"%s 还没开过" % card[u"id"])
    new = spec_hash(a)
    if new == old:
        raise Refused(u"amend-noop", u"判据一个字都没动,不用 amend")
    if not (why or u"").strip():
        raise Refused(u"amend-why", u"改判据必须写为什么")
    body = {u"card": card[u"id"], u"old_spec_hash": old, u"new_spec_hash": new,
            u"why": why, u"by": by, u"作废": u"这张卡此前的 verdict 全部作废"}
    return append(ledger_path, u"amend", body, chain_head)


def effective_verdicts(ledger_path, card_id):
    u"""这张卡**现在还算数**的判决:spec_hash 不等于当前注册值的,一律不算(R6 的作废)。"""
    cur = registered(ledger_path, card_id)
    return [r for r in read(ledger_path)
            if r.get(u"kind") == u"verdict" and (r.get(u"body") or {}).get(u"card") == card_id
            and (r.get(u"body") or {}).get(u"spec_hash") == cur]

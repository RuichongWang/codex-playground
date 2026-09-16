# -*- coding: utf-8 -*-
u"""七条规矩。**每条同时有执行器 · 必红用例 · 绿对照,三样缺一这条规矩不存在。**

硬顶:七条封顶。要加一条,先砍一条 —— 这一行就是那个闸门。
必红用例返回 True = 「它确实红了」;绿对照返回 True = 「正常那条路走通了」。
"""
RULES = (
    {u"id": u"R1", u"规矩": u"账只能追加",
     u"执行器": u"ledger.verify", u"必红": u"r1_red", u"绿对照": u"r1_green"},
    {u"id": u"R2", u"规矩": u"至少一条判据由命令来答",
     u"执行器": u"card.validate", u"必红": u"r2_red", u"绿对照": u"r2_green"},
    {u"id": u"R3", u"规矩": u"判据预注册即冻结",
     u"执行器": u"judge.judge", u"必红": u"r3_red", u"绿对照": u"r3_green"},
    {u"id": u"R4", u"规矩": u"判的那只手写不到账",
     u"执行器": u"ledger.ReadOnly.append", u"必红": u"r4_red", u"绿对照": u"r4_green"},
    {u"id": u"R5", u"规矩": u"逐条 · 带证据 · 引文对得上 · 不合成",
     u"执行器": u"judge.validate_verdict", u"必红": u"r5_red", u"绿对照": u"r5_green"},
    {u"id": u"R6", u"规矩": u"改判据必须留疤",
     u"执行器": u"card.amend", u"必红": u"r6_red", u"绿对照": u"r6_green"},
    {u"id": u"R7", u"规矩": u"每条规矩必须有一条会红的用例",
     u"执行器": u"check.main", u"必红": u"r7_red", u"绿对照": u"r7_green"},
)

CAP = 7


def check_cap():
    if len(RULES) > CAP:
        raise AssertionError(u"规矩超过 %d 条了 —— 要加一条,先砍一条" % CAP)
    return True

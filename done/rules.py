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
     # **原来写的是 `ledger.ReadOnly.append`,那是假的。** 审阅人把那段代码整个删掉,
     # 开卡、判决、沉淀、验账四步全部照常跑通 —— 全仓没有任何真实路径构造过它,
     # 唯一会疼的是测它自己的那条用例。**一条没接上的防线和一条不存在的防线是一样的。**
     # 真正拦住「判决污染账」的一直是这个:判据里的命令跑在临时副本里,账不在那棵树上。
     u"执行器": u"worktree.临时副本", u"必红": u"r4_red", u"绿对照": u"r4_green"},
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

# -*- coding: utf-8 -*-
u"""开卡这一刻,把每条命令判据先跑一遍,记下它现在是什么颜色。

**这一条记,不拦。** 它对的是账上第 10 · 12 · 13 次改判据 —— 那三次的毛病都是
「这条判据的答案永远是同一个」,而恒绿的判据和不存在的判据在判决那一刻一模一样。
这种毛病机械拦不住(体检卡就该一开卡全绿),但它能变成一个读数:
开卡时是什么颜色、判决时是什么颜色,两边都记下来,常数就看得见了。

**为什么它单独一个文件。** 它原来住在 `done/opencheck.py` 里,跟那边的纯文字检查
零共用 —— 那边是看判据自己的文字、没有副作用、出口是拒绝;这边是起临时副本、
跑别人写的命令、产一份读数。审阅人逐条点出这是两户人家,而**上一轮放行它的理由,
正是这一轮重写文件开头时自己删掉的那句话** —— 没有任何东西发现这件事。
"""
from done.worktree import 临时副本, 起不来, 跑


def 开卡实况(accept, repo=u".", timeout=120):
    u"""每条命令判据在开卡这一刻的退出码。起不了临时副本就整段跳过,只记一句为什么。"""
    cmds = [c for c in accept
            if isinstance(c.get(u"判者"), dict) and c[u"判者"].get(u"cmd")]
    if not cmds:
        return []
    try:
        with 临时副本(repo) as wt:
            出 = []
            for c in cmds:
                cmd = c[u"判者"][u"cmd"]
                码, _ = 跑(cmd, wt, timeout)
                出.append({u"id": c.get(u"id"), u"cmd": cmd, u"exit": 码,
                           u"开卡就绿": 码 == 0})
            return 出
    except 起不来 as e:
        return [{u"跑不了": u"起不了 worktree:%s" % e}]

# -*- coding: utf-8 -*-
u"""沉淀:卡判完之后的一步,由一个 agent 自己决定要不要往记忆库写。

**从 `judge.py` 里拆出来的** —— 那个文件原来同时住着「判」和「沉淀」两件事,
两边零共用内部函数,而它开头的自述只写了「判」。审阅人逐字逮到的。
"""
from done.card import load
from done.ledger import Refused, append, read

def reflect(ledger_path, card_file, chain_head, note):
    u"""卡判完之后的一步:由一个 agent 看完这一轮,**自己决定要不要往库里写**。

    **「不写」是正常结果,不是失败** —— 绝大多数轮次本来就没什么值得记的,
    自动沉淀只会把库灌满废话。但「不写」必须落账并写明理由:
    一个正确的零和一次根本没跑过,在盘面上完全同形。

    这一步**不产生 done**,所以它不占规矩位;真正写进库的动作归 pattern 那一侧。
    """
    card = load(card_file)
    cid = card[u"id"]
    if not [r for r in read(ledger_path)
            if r.get(u"kind") == u"verdict" and (r.get(u"body") or {}).get(u"card") == cid]:
        raise Refused(u"no-verdict", u"%s 还没判过,没什么可沉淀的" % cid)
    validate_note(note)
    body = dict(note)
    body[u"card"] = cid
    return append(ledger_path, u"reflect", body, chain_head)


def validate_note(n):
    u"""沉淀报告的形状。写与不写二选一,两边各自要交的东西不同。"""
    if not (n or {}).get(u"by"):
        raise Refused(u"reflect-by", u"沉淀报告要写明是谁做的")
    w = (n or {}).get(u"写不写")
    if w not in (u"写", u"不写"):
        raise Refused(u"reflect-choice", u"「写不写」要么「写」要么「不写」")
    if w == u"不写":
        why = (n.get(u"为什么不写") or u"").strip()
        if len(why) < 10:
            raise Refused(u"reflect-why",
                          u"「不写」也要写明为什么 —— 一个正确的零和一次没跑过,盘面上同形")
        return True
    if not ((n.get(u"事件") or {}).get(u"what") or u"").strip():
        raise Refused(u"reflect-what", u"要写就得有一件具体的事:发生了什么")
    if not (n.get(u"挂到") or n.get(u"新猜测")):
        raise Refused(u"reflect-link",
                      u"要么挂到库里已有的猜测上,要么提一条新的 —— 只记事不猜,库长不起来")
    return True

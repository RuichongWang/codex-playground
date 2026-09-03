# -*- coding: utf-8 -*-
"""共享 pattern 库：item / pattern / condition 三类节点 + 有向有符号 link + prescription。

prescription 是 TRIZ 矩阵格子的一般化：(现象 pattern, 条件集合) -> 解法 pattern。
条件本身是节点，跟 pattern 一样可以被猜、被 link、被汇聚验证。

**没有 domain 字段。** 「域」太大：一条解法在「电力」里成立，不代表在电力的任何场景都成立，
它只是在「光伏傍晚出力下降」这一个事件上成立。而且「上升到域」本身也是一次抽象 ——
域标签就不该是预先给定的，它跟 pattern 一样应该是被猜出来的东西。

所以证据的单位是 **item（一个具体事件）**。「这两条证据算不算互相独立」不用相似度函数，
也不用 embedding —— **由 agent 在 link 的时候自己声明**：
「已经挂在这个 pattern 下的事件里，有没有跟我这件事本质上是同一个情境？」
有就 novel=False（同情境的又一次确认），没有就是新的独立事件。

这跟整个系统的哲学一致：所有判断都是模型做的、靠汇聚验证，不靠写死的阈值。
风险是自报可能不准或被刷，对冲是后来的 agent 看到不对可以打负 link 或提合并。
"""
import json
import time
from collections import defaultdict

POS, NEG = "+", "-"


class Store:
    def __init__(self):
        self.nodes = {}
        self.links = []          # {src, dst, polarity, why, source}
        self.prescriptions = {}  # id -> {phenomenon, conditions[], solution, evidence[]}
        self._c = defaultdict(int)

    # ---------- 写 ----------
    def _new(self, prefix, **kw):
        self._c[prefix] += 1
        nid = f"{prefix}{self._c[prefix]}"
        self.nodes[nid] = dict(id=nid, ts=time.time(), **kw)
        return nid

    def add_item(self, what, source, facts=None, intervention=None, outcome="unknown"):
        """一件具体的事。facts 是这次事件的具体事实，用来判断两个事件像不像。"""
        return self._new("I", kind="item", what=what, facts=facts or {},
                         intervention=intervention, outcome=outcome, source=source)

    def add_pattern(self, claim, side, source, order=1):
        assert side in ("phenomenon", "solution")
        return self._new("P", kind="pattern", side=side, claim=claim,
                         order=order, proposed_by=source)

    def add_condition(self, claim, test, source):
        return self._new("C", kind="condition", claim=claim, test=test, proposed_by=source)

    def link(self, src, dst, why, source, polarity=POS, novel=True, same_as=None):
        """novel=False 表示「我这件事跟 same_as 本质上是同一个情境」，只算又一次确认，不算新独立事件。"""
        assert src in self.nodes and dst in self.nodes, (src, dst)
        self.links.append(dict(src=src, dst=dst, polarity=polarity, why=why, source=source,
                               novel=bool(novel), same_as=same_as))

    def prescribe(self, phenomenon, conditions, solution, source):
        key = (phenomenon, tuple(sorted(conditions)), solution)
        for pid, p in self.prescriptions.items():
            if (p["phenomenon"], tuple(sorted(p["conditions"])), p["solution"]) == key:
                return pid
        self._c["R"] += 1
        pid = f"R{self._c['R']}"
        self.prescriptions[pid] = dict(id=pid, phenomenon=phenomenon, conditions=list(conditions),
                                       solution=solution, proposed_by=source, evidence=[])
        return pid

    def record_application(self, prescription, item, outcome, source, note=""):
        """套用之后的硬反馈。outcome: worked | failed。证据挂在具体 item 上，不挂在域上。"""
        self.prescriptions[prescription]["evidence"].append(
            dict(item=item, outcome=outcome, source=source, note=note))

    # ---------- 读 ----------
    def search(self, text, kind=None, side=None, limit=8):
        def ok(n):
            return (kind is None or n["kind"] == kind) and (side is None or n.get("side") == side)
        def txt(n):
            base = n.get("claim") or n.get("what", "")
            if n["kind"] == "item":
                base += " " + " ".join(f"{k}{v}" for k, v in n.get("facts", {}).items())
                base += " " + (n.get("intervention") or "")
            elif n["kind"] == "condition":
                base += " " + n.get("test", "")
            return base
        scored = [(_sim(text, txt(n)), n) for n in self.nodes.values() if ok(n)]
        return [n for s, n in sorted(scored, key=lambda x: -x[0])[:limit] if s > 0]

    def supporters(self, nid, polarity=POS):
        return [l for l in self.links if l["dst"] == nid and l["polarity"] == polarity]

    def up(self, nid):
        return [self.nodes[l["dst"]] for l in self.links if l["src"] == nid and l["polarity"] == POS]

    def down(self, nid):
        return [self.nodes[l["src"]] for l in self.links if l["dst"] == nid and l["polarity"] == POS]

    def grounding_items(self, nid, _seen=None):
        """一个 pattern 真正的证据基底：顺着正 link 往下走到 item。

        高阶 pattern 的支持者是 pattern，不是 item —— 但它的独立性要按最终落地的事件算，
        否则「三个 pattern 支持我」可能其实只对应一个事件。
        """
        _seen = _seen if _seen is not None else set()
        if nid in _seen:
            return []
        _seen.add(nid)
        out = []
        for n in self.down(nid):
            if n["kind"] == "item":
                out.append(n["id"])
            else:
                out += self.grounding_items(n["id"], _seen)
        return list(dict.fromkeys(out))

    def prescriptions_for(self, phenomenon, satisfied=None):
        """矩阵查表。satisfied=None 则不过滤，把条件一起交给 agent 自己判断。"""
        out = [p for p in self.prescriptions.values() if p["phenomenon"] == phenomenon
               and (satisfied is None or set(p["conditions"]) <= set(satisfied))]
        return sorted(out, key=lambda p: -self.prescription_score(p["id"])["score"])

    # ---------- 可信度：数独立事件（agent 自报），不数 link，也不用域 ----------
    def _novel(self, item_ids):
        """只留下「自己声明是新情境」的事件。被声明为同情境的不重复计独立性。"""
        out = []
        for i in item_ids:
            ls = [l for l in self.links if l["src"] == i and l["polarity"] == POS]
            if not ls or any(l.get("novel", True) for l in ls):
                out.append(i)
        return out

    def credibility(self, nid):
        pos, neg = self.supporters(nid, POS), self.supporters(nid, NEG)
        items = self.grounding_items(nid)
        novel = self._novel(items)
        return dict(events=len(novel), items=len(items), dup=len(items) - len(novel),
                    sources=len({l["source"] for l in pos}), links=len(pos), refutes=len(neg))


    def score(self, nid):
        """只由独立事件数和来源数决定。link 总数不计分 —— 否则同一个情境反复写就能刷。"""
        c = self.credibility(nid)
        return c["events"] * 3 + c["sources"] * 2 - c["refutes"] * 2

    def prescription_score(self, pid):
        ev = self.prescriptions[pid]["evidence"]
        w = [e for e in ev if e["outcome"] == "worked"]
        f = [e for e in ev if e["outcome"] == "failed"]
        wg = self._novel([e["item"] for e in w])
        return dict(score=len(wg) * 3 - len(f) * 2, worked_events=len(wg),
                    tried=len(ev), failed=len(f),
                    worked_on=[self.nodes[e["item"]]["what"][:24] for e in w])

    # ---------- 持久化 ----------
    def save(self, path):
        json.dump(dict(nodes=self.nodes, links=self.links, prescriptions=self.prescriptions,
                       counters=dict(self._c)), open(path, "w"), ensure_ascii=False, indent=1)

    @classmethod
    def load(cls, path):
        d = json.load(open(path))
        s = cls()
        s.nodes, s.links, s.prescriptions = d["nodes"], d["links"], d["prescriptions"]
        s._c = defaultdict(int, d["counters"])
        return s


def _sim(a, b):
    x = {a[i:i + 2] for i in range(len(a) - 1)}
    y = {b[i:i + 2] for i in range(len(b) - 1)}
    return len(x & y) / max(1, len(x | y))

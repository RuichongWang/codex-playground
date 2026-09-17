# -*- coding: utf-8 -*-
"""共享 pattern 库：item / pattern / condition 三类节点 + 有向有符号 link + prescription。

prescription 是 TRIZ 矩阵格子的一般化：(现象 pattern, 条件集合) -> 解法 pattern。
条件本身是节点，跟 pattern 一样可以被猜、被 link、被汇聚验证。

**域不是证据的单位。** 「域」太大：一条解法在「电力」里成立，不代表在电力的任何场景都成立，
它只是在「光伏傍晚出力下降」这一个事件上成立。而且「上升到域」本身也是一次抽象 ——
域标签就不该是预先给定的，它跟 pattern 一样应该是被猜出来的东西。

item 上确实有一个 domain 字段，但它**只是实验器材**：测跨域迁移要能把某个域的痕迹
整体从库里拿掉（见 mask），而永久冻结六个域的老办法会让库长不动。
credibility / score / search 一个字都不看它 —— 它进不了知识结构。

证据的单位仍然是 **item（一个具体事件）**。「这两条证据算不算互相独立」不用相似度函数，
也不用 embedding —— **由 agent 在 link 的时候自己声明**：
「已经挂在这个 pattern 下的事件里，有没有跟我这件事本质上是同一个情境？」
有就 novel=False（同情境的又一次确认），没有就是新的独立事件。

这跟整个系统的哲学一致：所有判断都是模型做的、靠汇聚验证，不靠写死的阈值。
风险是自报可能不准或被刷，对冲是后来的 agent 看到不对可以打负 link 或提合并。
"""
import copy
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

    def add_item(self, what, source, facts=None, intervention=None, outcome="unknown", domain=None):
        """一件具体的事。facts 是这次事件的具体事实，用来判断两个事件像不像。

        domain 是这条事件来自哪个语料域，只给 mask 用（见模块头）。写入时就带上，
        免得日后还要靠文字模糊匹配倒推 —— 倒推一旦错标，被屏蔽域的证据会偷偷留在库里。
        """
        return self._new("I", kind="item", what=what, facts=facts or {},
                         intervention=intervention, outcome=outcome, source=source,
                         domain=domain)

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
        """矩阵查表。

        satisfied 给了也**不硬过滤** —— 按满足比例排序，并把没满足的条件一并返回。
        硬过滤会让条件多的 prescription 永远匹配不上（第一条真实数据就挂了 4 个条件的合取），
        而「差一个条件」对 agent 是有用的信息：它可以去想办法让那个条件成立。
        """
        out = []
        for p in self.prescriptions.values():
            if p["phenomenon"] != phenomenon:
                continue
            unmet = [] if satisfied is None else [c for c in p["conditions"] if c not in satisfied]
            frac = 1.0 if not p["conditions"] else 1 - len(unmet) / len(p["conditions"])
            out.append(dict(p, _unmet=unmet, _frac=frac))
        return sorted(out, key=lambda p: (-p["_frac"], -self.prescription_score(p["id"])["score"]))

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
        # 来源也必须按**落地事件**算，不能只数直接 link ——
        # 高阶 pattern 的直接支持者是 pattern（往往只有两三条边），
        # 只数直接 link 会把「21 个事件、21 个提出者」误报成「2 个来源」，
        # 恰恰在高阶抽象上系统性低估。
        return dict(events=len(novel), items=len(items), dup=len(items) - len(novel),
                    sources=len({self.nodes[i]["source"] for i in novel}),
                    direct=len({l["source"] for l in pos}), links=len(pos), refutes=len(neg))


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

    # ---------- 运行时屏蔽：把某几个域的痕迹整体拿掉 ----------
    def domains(self):
        """{域: item 数}。没打标的算在 "?" 下。"""
        out = defaultdict(int)
        for n in self.nodes.values():
            if n["kind"] == "item":
                out[n.get("domain") or "?"] += 1
        return dict(out)

    def mask(self, domains, strict=False, same_batch=900):
        """屏蔽掉这几个语料域，返回 (新 Store, 统计)。原库一个字都不动。

        为什么不能只删 item：一条 pattern 如果**全部**证据来自被屏蔽的域，它本身就是那个域
        的产物 —— 留着它就等于把答案漏给了「从未见过这个域」的测试。所以顺 grounding_items
        往下追到 item，全被屏蔽的节点整个删掉；还剩别域证据的留着，可信度自然会掉
        （credibility 是现算的，不用额外处理）。

        grounding 在**原库**上算一遍就够，不用迭代到不动点：通向存活 item 的那条路径上的
        每个中间节点，自己的 grounding 里都含着那个存活 item，所以它必然也存活 ——
        路径不会被从中间打断。

        strict=True 再多删一层措辞泄露：一条 pattern 即使还有别域证据撑着，只要提出它的
        agent **写过**某条被屏蔽的 item，它的措辞就可能是被那条案例塑造出来的。
        条件同理（claim/test 一样是那个 agent 写的字），所以两类一起删。
        默认 False —— 这一刀砍得很深，是否要用取决于测的是「证据泄露」还是「措辞泄露」。

        **agent id 不是全局唯一的**：每轮 pipeline 都从 B1A1 重新编号，r3 库里 55 个 source
        有 30 个横跨多个域 —— 光按 source 匹配会把三轮里的同名 agent 当成一个人，
        屏蔽 software 会连坐删掉 41 条 pattern 而不是该删的那些。所以再加一道时间闸：
        一次批写入里的节点时间戳只差毫秒，轮与轮之间隔着小时，same_batch 秒内才算同一个人。
        """
        domains = set(domains)
        masked_items = {i for i, n in self.nodes.items()
                        if n["kind"] == "item" and (n.get("domain") or "?") in domains}
        drop = set(masked_items)
        by_grounding = defaultdict(int)
        for nid, n in self.nodes.items():
            if n["kind"] == "item":
                continue
            g = self.grounding_items(nid)
            # 一条证据都没有的节点跟这次屏蔽无关，别拿「全都被屏蔽了」的空真去误伤它
            if g and all(i in masked_items for i in g):
                drop.add(nid)
                by_grounding[n["kind"]] += 1

        by_author = defaultdict(int)
        if strict:
            tainted = defaultdict(list)
            for i in masked_items:
                tainted[self.nodes[i]["source"]].append(self.nodes[i].get("ts", 0))
            for nid, n in self.nodes.items():
                if n["kind"] not in ("pattern", "condition") or nid in drop:
                    continue
                ts = n.get("ts", 0)
                if any(abs(ts - t) <= same_batch for t in tainted.get(n.get("proposed_by"), ())):
                    drop.add(nid)
                    by_author[n["kind"]] += 1

        new = Store()
        new.nodes = {k: copy.deepcopy(v) for k, v in self.nodes.items() if k not in drop}
        # 计数器照抄：屏蔽后再写入不能重用已删节点的 id，否则新旧证据会被认成同一个
        new._c = defaultdict(int, self._c)

        cleared = pre_broken = 0
        for l in self.links:
            if l["src"] in drop or l["dst"] in drop:
                continue
            l = dict(l)
            if l.get("same_as") and l["same_as"] not in new.nodes:
                # 被指为「同情境」的那条事件没了，只能退回成一条普通 link。
                # novel 标志保留原样：那个判断当初确实做出过，不能因为对照物没了就当没发生。
                if l["same_as"] in self.nodes:
                    cleared += 1
                else:
                    pre_broken += 1
                l["same_as"] = None
            new.links.append(l)

        dangling = ev_dropped = 0
        for pid, p in self.prescriptions.items():
            refs = [p["phenomenon"], p["solution"]] + list(p["conditions"])
            if any(r in drop for r in refs):
                continue
            if any(r not in self.nodes for r in refs):
                dangling += 1        # 屏蔽之前就已经是悬空的，顺手扫掉，别带进新库
                continue
            p = copy.deepcopy(p)
            ev = [e for e in p["evidence"] if e["item"] in new.nodes]
            ev_dropped += len(p["evidence"]) - len(ev)
            p["evidence"] = ev
            new.prescriptions[pid] = p

        bad = new.check_integrity()
        # 一条悬空引用曾经打掉过 8 次实验运行（见 git log）。屏蔽是会大批删节点的操作，
        # 出问题必须当场炸，不能等到跑实验的时候才发现。
        assert not bad, f"屏蔽后留下了悬空引用：{bad[:5]}"

        n_kind = lambda st, k: sum(1 for x in st.nodes.values() if x["kind"] == k)
        stats = dict(
            masked=sorted(domains), strict=bool(strict),
            # 打错域名会静悄悄地屏蔽掉零个节点，然后跑出一个看起来很干净的「跨域」结果。
            # 不能报错（小快照里那个域可能本来就还没进库），但必须报出来。
            unknown=sorted(domains - set(self.domains())),
            items=len(masked_items),
            patterns=n_kind(self, "pattern") - n_kind(new, "pattern"),
            conditions=n_kind(self, "condition") - n_kind(new, "condition"),
            links=len(self.links) - len(new.links),
            prescriptions=len(self.prescriptions) - len(new.prescriptions),
            patterns_by_grounding=by_grounding["pattern"],
            conditions_by_grounding=by_grounding["condition"],
            patterns_by_author=by_author["pattern"],
            conditions_by_author=by_author["condition"],
            prescriptions_dangling_before=dangling,
            evidence_dropped=ev_dropped, same_as_cleared=cleared,
            same_as_broken_before=pre_broken,
            kept=dict(items=n_kind(new, "item"), patterns=n_kind(new, "pattern"),
                      conditions=n_kind(new, "condition"), links=len(new.links),
                      prescriptions=len(new.prescriptions)))
        return new, stats

    def check_integrity(self):
        """列出全部悬空引用。空列表 = 干净。屏蔽之后必跑。"""
        bad = []
        for l in self.links:
            for k in ("src", "dst"):
                if l[k] not in self.nodes:
                    bad.append(f"link.{k} {l[k]} 不存在")
            if l.get("same_as") and l["same_as"] not in self.nodes:
                bad.append(f"link.same_as {l['same_as']} 不存在")
        for pid, p in self.prescriptions.items():
            for r in [p["phenomenon"], p["solution"]] + list(p["conditions"]):
                if r not in self.nodes:
                    bad.append(f"{pid} 引用 {r} 不存在")
            for e in p["evidence"]:
                if e["item"] not in self.nodes:
                    bad.append(f"{pid}.evidence 引用 {e['item']} 不存在")
        return bad

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

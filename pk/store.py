"""共享 pattern 库：item / pattern / condition 三类节点 + 有向有符号 link + prescription。

prescription 是 TRIZ 矩阵格子的一般化：(现象 pattern, 条件集合) -> 解法 pattern。
它是一等对象，不是一条边的属性 —— 因为同一个现象在不同条件下要用完全不同的解。
条件本身也是节点，跟 pattern 一样可以被猜、被 link、被汇聚验证。
"""
import json
import time
from collections import defaultdict

POS, NEG = "+", "-"


def _nid(prefix, n):
    return f"{prefix}{n}"


class Store:
    def __init__(self):
        self.nodes = {}          # id -> node
        self.links = []          # {src, dst, polarity, why, source, domain}
        self.prescriptions = {}  # id -> {phenomenon, conditions[], solution, evidence[]}
        self._c = defaultdict(int)

    # ---------- 写 ----------
    def _new(self, prefix, **kw):
        self._c[prefix] += 1
        nid = _nid(prefix, self._c[prefix])
        self.nodes[nid] = dict(id=nid, ts=time.time(), **kw)
        return nid

    def add_item(self, what, domain, source, intervention=None, outcome="unknown"):
        """一件具体的事：现象 + 做了什么 + 管不管用。"""
        return self._new("I", kind="item", what=what, intervention=intervention,
                         outcome=outcome, domain=domain, source=source)

    def add_pattern(self, claim, side, source, domain=None, order=1):
        """一个猜测。side: phenomenon | solution。order: 1=从 item 抽出，2+=从 pattern 抽出。"""
        assert side in ("phenomenon", "solution")
        return self._new("P", kind="pattern", side=side, claim=claim,
                         order=order, proposed_by=source, domain=domain)

    def add_condition(self, claim, test, source, domain=None):
        """一个可复用的约束谓词。test 说明「怎么判断我满不满足」。"""
        return self._new("C", kind="condition", claim=claim, test=test,
                         proposed_by=source, domain=domain)

    def link(self, src, dst, why, source, domain, polarity=POS):
        """src 是 dst 的一个实例（+）/ 反驳 dst（-）。src 可以是 item 也可以是 pattern。"""
        assert src in self.nodes and dst in self.nodes
        self.links.append(dict(src=src, dst=dst, polarity=polarity, why=why,
                               source=source, domain=domain))

    def prescribe(self, phenomenon, conditions, solution, source):
        """(现象, 条件集合) -> 解法。同一个现象可以有多条，靠条件区分。"""
        key = (phenomenon, tuple(sorted(conditions)), solution)
        for pid, p in self.prescriptions.items():
            if (p["phenomenon"], tuple(sorted(p["conditions"])), p["solution"]) == key:
                return pid
        self._c["R"] += 1
        pid = _nid("R", self._c["R"])
        self.prescriptions[pid] = dict(id=pid, phenomenon=phenomenon, conditions=list(conditions),
                                       solution=solution, proposed_by=source, evidence=[])
        return pid

    def record_application(self, prescription, item, outcome, source, domain, note=""):
        """套用一条 prescription 之后的硬反馈。outcome: worked | failed。"""
        self.prescriptions[prescription]["evidence"].append(
            dict(item=item, outcome=outcome, source=source, domain=domain, note=note))

    # ---------- 读（agent 自己拿这些去查库） ----------
    def search(self, text, kind=None, side=None, limit=8):
        def ok(n):
            return (kind is None or n["kind"] == kind) and (side is None or n.get("side") == side)
        scored = [(_lex(text, n.get("claim") or n.get("what", "")), n)
                  for n in self.nodes.values() if ok(n)]
        return [n for s, n in sorted(scored, key=lambda x: -x[0])[:limit] if s > 0]

    def supporters(self, nid, polarity=POS):
        return [l for l in self.links if l["dst"] == nid and l["polarity"] == polarity]

    def up(self, nid):
        return [self.nodes[l["dst"]] for l in self.links if l["src"] == nid and l["polarity"] == POS]

    def down(self, nid):
        return [self.nodes[l["src"]] for l in self.links if l["dst"] == nid and l["polarity"] == POS]

    def prescriptions_for(self, phenomenon, satisfied=None):
        """TRIZ 矩阵查表：给定现象和「我满足哪些条件」，返回适用的解法。

        satisfied=None 表示不过滤，把条件一起返回让 agent 自己判断。
        """
        out = []
        for p in self.prescriptions.values():
            if p["phenomenon"] != phenomenon:
                continue
            if satisfied is not None and not set(p["conditions"]) <= set(satisfied):
                continue
            out.append(p)
        return sorted(out, key=lambda p: -self.prescription_score(p["id"])["worked"])

    # ---------- 可信度：数来源，不数 link ----------
    def credibility(self, nid):
        pos = self.supporters(nid, POS)
        neg = self.supporters(nid, NEG)
        return dict(
            domains=len({l["domain"] for l in pos}),
            sources=len({l["source"] for l in pos}),
            links=len(pos),
            refutes=len(neg),
        )

    def score(self, nid):
        """域多样性 > 来源多样性 > link 总数。同一来源刷 10 条不如跨 3 个域。"""
        c = self.credibility(nid)
        return c["domains"] * 3 + c["sources"] * 2 + c["links"] - c["refutes"] * 2

    def prescription_score(self, pid):
        ev = self.prescriptions[pid]["evidence"]
        w = [e for e in ev if e["outcome"] == "worked"]
        f = [e for e in ev if e["outcome"] == "failed"]
        return dict(worked=len({e["domain"] for e in w}) * 3 + len(w),
                    tried=len(ev), failed=len(f),
                    domains=sorted({e["domain"] for e in w}))

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


def _lex(a, b):
    x = {a[i:i + 2] for i in range(len(a) - 1)}
    y = {b[i:i + 2] for i in range(len(b) - 1)}
    return len(x & y) / max(1, len(x | y))

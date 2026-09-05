# -*- coding: utf-8 -*-
"""直接测跨域迁移：agent 到底引用了哪些库节点，那些节点的证据来自哪些行业。

陷阱规避是结果指标 —— 它说明 C 避开了坑，不说明是不是**靠跨域抽象**避开的。
而后者才是这个项目要的那一步。轨迹已经全量落盘，可以离线把它挖出来，不花钱。
"""
import argparse, glob, json, os, re
from collections import Counter, defaultdict
from pk.domain import item_domain
from pk.store import Store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = re.compile(r"\b([PCIR]\d{1,4})\b")


def cited_nodes(trace_path):
    """从轨迹里抽出被 agent 实际碰过的节点 id：CLI 查询的产出 + 它自己写的推理。"""
    ids = Counter()
    if not os.path.exists(trace_path):
        return ids
    for line in open(trace_path):
        try:
            ev = json.loads(line)
        except Exception:
            continue
        t = ev.get("type")
        blocks = []
        if t == "assistant":
            blocks = ev.get("message", {}).get("content", [])
        elif t == "user":
            c = ev.get("message", {}).get("content", [])
            blocks = c if isinstance(c, list) else []
        for b in blocks:
            if not isinstance(b, dict):
                continue
            txt = ""
            if b.get("type") == "text":
                txt = b.get("text", "")
            elif b.get("type") == "tool_result":
                cc = b.get("content")
                txt = cc if isinstance(cc, str) else json.dumps(cc, ensure_ascii=False)
            elif b.get("type") == "tool_use":
                txt = json.dumps(b.get("input", {}), ensure_ascii=False)
            for m in NODE.findall(txt or ""):
                ids[m] += 1
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="runs/stage4")
    ap.add_argument("--lib", default="runs/r3/library.json")
    ap.add_argument("--arm", default="C")
    a = ap.parse_args()
    s = Store.load(os.path.join(ROOT, a.lib))
    cases = {c["id"]: c for f in sorted([f for f in glob.glob(os.path.join(ROOT, "heldout/*.json")) if "mech" not in f])
             if "mech" not in f for c in json.load(open(f))}
    ansf = os.path.join(ROOT, a.out, "answers.jsonl")
    ans = {}
    if os.path.exists(ansf):
        for l in open(ansf):
            try:
                r = json.loads(l); ans[(r["id"], r["arm"])] = r
            except Exception:
                pass

    print(f"=== 迁移分析（arm {a.arm}）===\n")
    rows = []
    for cid, c in cases.items():
        tr = os.path.join(ROOT, a.out, f"trace_{cid}_{a.arm}.jsonl")
        ids = cited_nodes(tr)
        touched = [i for i in ids if i in s.nodes]
        pats = [i for i in touched if s.nodes[i]["kind"] == "pattern"]
        # 每个被碰过的 pattern，它的证据落在哪些语料域
        doms = Counter()
        for p in pats:
            for it in s.grounding_items(p):
                doms[item_domain(s.nodes[it])] += 1
        hi = [p for p in pats if s.nodes[p].get("order", 1) >= 2]
        # 在最终推理里真正被引用的（不只是查询时扫过的）
        r = ans.get((cid, a.arm), {})
        final = set(NODE.findall((r.get("reasoning") or "") + (r.get("proposal") or "")))
        final = [x for x in final if x in s.nodes]
        rows.append(dict(id=cid, domain=c["domain"], touched=len(touched), pats=len(pats),
                         hi=len(hi), doms=len(doms), final=final))
    if not any(r["touched"] for r in rows):
        print("轨迹里没有节点引用（还没跑 agentic 臂？）"); return
    n = len([r for r in rows if r["touched"]])
    print(f"{'案例':22}{'碰过节点':>8}{'其中pattern':>11}{'阶2+':>7}{'覆盖语料域':>10}  最终推理里引用的")
    for r in rows:
        if not r["touched"]:
            continue
        print(f"{r['id']:22}{r['touched']:>8}{r['pats']:>11}{r['hi']:>7}{r['doms']:>10}  {','.join(r['final'][:6])}")
    print(f"\n有轨迹的案例 {n} 个")
    print(f"  平均碰过 {sum(r['touched'] for r in rows)/max(1,n):.1f} 个节点，"
          f"其中阶2+ 占 {sum(r['hi'] for r in rows)/max(1,sum(r['pats'] for r in rows) or 1):.0%}")
    print(f"  最终推理里明确引用了库节点的案例：{sum(1 for r in rows if r['final'])}/{n}")


if __name__ == "__main__":
    main()

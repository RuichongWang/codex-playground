# -*- coding: utf-8 -*-
"""库的命令行入口 —— 写入 agent 通过这个自己跟库交互。

    python -m pk.cli search "周期性缺口"
    python -m pk.cli patterns --side phenomenon
    python -m pk.cli get P1
    python -m pk.cli neighbors P1
    python -m pk.cli prescriptions P6 --satisfied C1,C2
    python -m pk.cli add-item --what "..." --source A --facts '{"周期":"一周"}'
    python -m pk.cli link --src I7 --dst P1 --why "..." --source A --novel false --same-as I1
    python -m pk.cli domains                             # 有哪些语料域，屏蔽一个要付多大代价
    python -m pk.cli --mask software patterns            # 假装这个库从没见过软件业
"""
import argparse
import json
import os
import sys

from pk.store import Store, POS, NEG

DB = os.environ.get("PK_DB", "pk/library.json")

# 屏蔽是只读操作：屏蔽完再写回去就等于把那个域从库里真删了，且不可逆。
WRITE_CMDS = {"add-item", "add-pattern", "add-condition", "link", "prescribe", "batch", "apply"}


def load(path):
    return Store.load(path) if os.path.exists(path) else Store()


def fmt(s, n):
    if n["kind"] == "pattern":
        c = s.credibility(n["id"])
        return (f"{n['id']} [{'现象' if n['side']=='phenomenon' else '解法'}/阶{n['order']}] "
                f"{n['claim']}\n    分{s.score(n['id'])} 独立事件{c['events']} 同情境重复{c['dup']} "
                f"来源{c['sources']}(直接{c['direct']}) 反驳{c['refutes']}")
    if n["kind"] == "condition":
        return f"{n['id']} [条件] {n['claim']}\n    判断：{n['test']}"
    iv = f"\n    干预：{n['intervention']}（{n['outcome']}）" if n.get("intervention") else ""
    fa = ("\n    facts：" + "、".join(f"{k}={v}" for k, v in n["facts"].items())) if n.get("facts") else ""
    return f"{n['id']} [事件/{n['source']}] {n['what']}{fa}{iv}"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pk.cli")
    ap.add_argument("--db", default=DB)
    ap.add_argument("--mask", default=None,
                    help="逗号分隔的语料域，加载后先把这些域的痕迹全部拿掉再操作（只读命令可用）")
    ap.add_argument("--strict", action="store_true",
                    help="连带删掉「提出者写过被屏蔽 item」的 pattern/条件，堵措辞泄露")
    sub = ap.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("search", help="按文字找节点")
    q.add_argument("text"); q.add_argument("--kind"); q.add_argument("--side")
    q.add_argument("--limit", type=int, default=8)

    for name, helptext in [("get", "看一个节点"), ("neighbors", "看一个节点的上下邻居")]:
        p = sub.add_parser(name, help=helptext); p.add_argument("id")

    p = sub.add_parser("patterns", help="列 pattern，按分排"); p.add_argument("--side")
    p.add_argument("--limit", type=int, default=20)
    sub.add_parser("conditions", help="列所有条件")
    sub.add_parser("stats", help="库的规模和爆炸系数")
    sub.add_parser("domains", help="列各语料域的 item 数，以及屏蔽它要连带删掉多少东西")
    p = sub.add_parser("catalog", help="一行一条列出全部 claim，供 grep")
    p.add_argument("--kind", default="pattern")

    p = sub.add_parser("prescriptions", help="查某现象在条件下的解法")
    p.add_argument("phenomenon"); p.add_argument("--satisfied", default=None)

    p = sub.add_parser("add-item")
    p.add_argument("--what", required=True); p.add_argument("--source", required=True)
    p.add_argument("--facts", default="{}"); p.add_argument("--intervention")
    p.add_argument("--outcome", default="unknown", choices=["worked", "failed", "unknown"])
    p.add_argument("--domain", default=None, help="这条事件来自哪个语料域，供运行时屏蔽用")

    p = sub.add_parser("add-pattern")
    p.add_argument("--claim", required=True); p.add_argument("--source", required=True)
    p.add_argument("--side", required=True, choices=["phenomenon", "solution"])
    p.add_argument("--order", type=int, default=1)

    p = sub.add_parser("add-condition")
    p.add_argument("--claim", required=True); p.add_argument("--test", required=True)
    p.add_argument("--source", required=True)

    p = sub.add_parser("link")
    p.add_argument("--src", required=True); p.add_argument("--dst", required=True)
    p.add_argument("--why", required=True); p.add_argument("--source", required=True)
    p.add_argument("--polarity", default="+", choices=["+", "-"])
    p.add_argument("--novel", default="true", choices=["true", "false"],
                   help="false = 我这件事跟 --same-as 本质上是同一个情境，只算又一次确认")
    p.add_argument("--same-as", dest="same_as", default=None)

    p = sub.add_parser("prescribe")
    p.add_argument("--phenomenon", required=True); p.add_argument("--solution", required=True)
    p.add_argument("--conditions", default=""); p.add_argument("--source", required=True)

    p = sub.add_parser("batch", help="一次提交全部写入（推荐：把 15 轮压成 1 轮）")
    p.add_argument("--file", required=True, help="JSON 文件路径")
    p.add_argument("--source", required=True)

    p = sub.add_parser("apply", help="记录套用一条 prescription 之后的结果")
    p.add_argument("--prescription", required=True); p.add_argument("--item", required=True)
    p.add_argument("--outcome", required=True, choices=["worked", "failed"])
    p.add_argument("--source", required=True); p.add_argument("--note", default="")

    a = ap.parse_args(argv)
    s = load(a.db)
    dirty = True

    if a.mask:
        if a.cmd in WRITE_CMDS:
            print(f"--mask 不能跟写命令一起用（{a.cmd}）：屏蔽后的库存回去就把那个域真删了",
                  file=sys.stderr)
            return 2
        s, st = s.mask([d for d in a.mask.split(",") if d], strict=a.strict)
        # 走 stderr：读命令的 stdout 是给 agent 解析的，别掺进来
        if st["unknown"]:
            print(f"⚠️ 这个库里没有域 {'/'.join(st['unknown'])}（打错了？它们一个节点都没屏蔽掉）",
                  file=sys.stderr)
        print(f"（已屏蔽 {'/'.join(st['masked'])}{'，strict' if st['strict'] else ''}："
              f"删 事件{st['items']} pattern{st['patterns']} 条件{st['conditions']} "
              f"link{st['links']} prescription{st['prescriptions']}；"
              f"剩 事件{st['kept']['items']} pattern{st['kept']['patterns']}）", file=sys.stderr)

    if a.cmd == "search":
        if os.environ.get("PK_BLIND_SEARCH"):
            # 安慰剂：返回同等数量的真实节点，但与查询无关。
            # 用于把「有库可查」和「查得准」这两件事分开。
            import random as _r
            pool = [n for n in s.nodes.values()
                    if (a.kind is None or n["kind"] == a.kind)
                    and (a.side is None or n.get("side") == a.side)]
            hits = _r.Random(hash(a.text) & 0xffff).sample(pool, min(a.limit, len(pool)))
        else:
            hits = s.search(a.text, kind=a.kind, side=a.side, limit=a.limit)
        print("\n".join(fmt(s, n) for n in hits) or "（没查到）"); dirty = False
    elif a.cmd == "get":
        print(fmt(s, s.nodes[a.id]) if a.id in s.nodes else f"没有 {a.id}"); dirty = False
    elif a.cmd == "neighbors":
        print("往上（我是谁的实例）:"); print("\n".join("  " + fmt(s, n) for n in s.up(a.id)) or "  （无）")
        print("往下（谁支持我）:"); print("\n".join("  " + fmt(s, n) for n in s.down(a.id)) or "  （无）")
        neg = s.supporters(a.id, NEG)
        if neg:
            print("反驳:"); [print(f"  {l['src']} by {l['source']}: {l['why']}") for l in neg]
        dirty = False
    elif a.cmd == "patterns":
        ns = [n for n in s.nodes.values() if n["kind"] == "pattern"
              and (not a.side or n["side"] == a.side)]
        print("\n".join(fmt(s, n) for n in sorted(ns, key=lambda n: -s.score(n["id"]))[:a.limit])
              or "（空库）"); dirty = False
    elif a.cmd == "conditions":
        ns = [n for n in s.nodes.values() if n["kind"] == "condition"]
        print("\n".join(fmt(s, n) for n in ns) or "（空库）"); dirty = False
    elif a.cmd == "stats":
        items = [n for n in s.nodes.values() if n["kind"] == "item"]
        pats = [n for n in s.nodes.values() if n["kind"] == "pattern"]
        conds = [n for n in s.nodes.values() if n["kind"] == "condition"]
        reuse = sum(1 for l in s.links if l["polarity"] == POS and s.nodes[l["src"]]["kind"] == "item")
        print(f"事件 {len(items)} / pattern {len(pats)} / 条件 {len(conds)} / "
              f"link {len(s.links)} / prescription {len(s.prescriptions)}")
        print(f"爆炸系数 pattern/事件 = {len(pats)/max(1,len(items)):.2f}  （接近 1 = 各猜各的，从不汇聚）")
        if pats:
            top = max(pats, key=lambda n: s.credibility(n["id"])["events"])
            print(f"最大 pattern：{top['id']} 独立事件 {s.credibility(top['id'])['events']} — {top['claim']}")
        print(f"事件→pattern 的正 link 共 {reuse} 条"); dirty = False
    elif a.cmd == "domains":
        doms = s.domains()
        print(f"{'域':16}{'事件':>5}{'屏蔽掉的pattern':>15}{'剩余pattern':>12}"
              f"{'屏蔽掉的条件':>13}{'屏蔽掉的解法条目':>17}")
        for d in sorted(doms):
            _, st = s.mask([d], strict=a.strict)
            print(f"{d:16}{doms[d]:>5}{st['patterns']:>15}{st['kept']['patterns']:>12}"
                  f"{st['conditions']:>13}{st['prescriptions']:>17}")
        print(f"\n共 {len(doms)} 个域 / {sum(doms.values())} 条事件。"
              f"「屏蔽掉的 pattern」= 全部证据都落在这个域里、拿掉它就没有支撑的那些。")
        dirty = False
    elif a.cmd == "catalog":
        for n in s.nodes.values():
            if n["kind"] != a.kind:
                continue
            tag = ("现象" if n.get("side") == "phenomenon" else "解法") if a.kind == "pattern" else "条件"
            print(f"{n['id']}\t[{tag}]\t{(n.get('claim') or '').replace(chr(10),' ')}")
        dirty = False
    elif a.cmd == "prescriptions":
        sat = a.satisfied.split(",") if a.satisfied else None
        rs = s.prescriptions_for(a.phenomenon, satisfied=sat)
        if not rs:
            print("（这个现象下还没有适用的解法）")
        for r in rs:
            sc = s.prescription_score(r["id"])
            head = f"{r['id']}"
            if sat is not None:
                head += f"  满足 {int(r['_frac']*100)}%"
            print(head)
            for c in r["conditions"]:
                mark = "✗" if c in r.get("_unmet", []) else ("✓" if sat is not None else "·")
                print(f"   {mark} {c} {s.nodes[c]['claim']}")
            print(f"   -> {s.nodes[r['solution']]['claim']}")
            print(f"      分{sc['score']} 试过{sc['tried']} 独立成功{sc['worked_events']} 失败{sc['failed']}")
        dirty = False
    elif a.cmd == "add-item":
        print(s.add_item(a.what, a.source, json.loads(a.facts), a.intervention, a.outcome, a.domain))
    elif a.cmd == "add-pattern":
        print(s.add_pattern(a.claim, a.side, a.source, a.order))
    elif a.cmd == "add-condition":
        print(s.add_condition(a.claim, a.test, a.source))
    elif a.cmd == "link":
        s.link(a.src, a.dst, a.why, a.source, a.polarity, a.novel == "true", a.same_as)
        print(f"ok {a.src} {a.polarity} {a.dst}" + ("" if a.novel == "true" else f" (同情境于 {a.same_as})"))
    elif a.cmd == "prescribe":
        print(s.prescribe(a.phenomenon, [c for c in a.conditions.split(",") if c], a.solution, a.source))
    elif a.cmd == "batch":
        spec = json.load(open(a.file))
        alias = {}
        out = []
        src = lambda o: o.get("source") or a.source
        items = spec.get("items") or ([dict(spec["item"], key="ITEM")] if spec.get("item") else [])
        for it in items:
            alias[it["key"]] = s.add_item(it["what"], src(it), it.get("facts") or {},
                                          it.get("intervention"), it.get("outcome", "unknown"),
                                          it.get("domain"))
            out.append(f"{it['key']} -> {alias[it['key']]}")
        for p_ in spec.get("patterns", []):
            alias[p_["key"]] = s.add_pattern(p_["claim"], p_["side"], src(p_), p_.get("order", 1))
            out.append(f"{p_['key']} -> {alias[p_['key']]}")
        for c in spec.get("conditions", []):
            alias[c["key"]] = s.add_condition(c["claim"], c["test"], src(c))
            out.append(f"{c['key']} -> {alias[c['key']]}")
        R = lambda k: alias.get(k, k)
        for l in spec.get("links", []):
            s.link(R(l["src"]), R(l["dst"]), l["why"], src(l),
                   l.get("polarity", POS), l.get("novel", True), R(l["same_as"]) if l.get("same_as") else None)
            out.append(f"link {R(l['src'])}{l.get('polarity',POS)}{R(l['dst'])}")
        for rx in spec.get("prescriptions", []):
            pid = s.prescribe(R(rx["phenomenon"]), [R(c) for c in rx.get("conditions", [])],
                              R(rx["solution"]), src(rx))
            out.append(f"prescription {pid}")
            if rx.get("outcome") in ("worked", "failed"):
                s.record_application(pid, R(rx.get("item", "ITEM")), rx["outcome"], src(rx), rx.get("note", ""))
                out.append(f"  applied {rx['outcome']}")
        if spec.get("merges"):
            open(a.file + ".merges", "w").write(json.dumps(spec["merges"], ensure_ascii=False, indent=1))
            out.append(f"归并记账 {len(spec['merges'])} 条")
        print("\n".join(out))
    elif a.cmd == "apply":
        s.record_application(a.prescription, a.item, a.outcome, a.source, a.note)
        print("ok")

    if dirty:
        s.save(a.db)


if __name__ == "__main__":
    sys.exit(main())

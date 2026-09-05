# -*- coding: utf-8 -*-
"""按 triage 的归并映射，把多份原始提议**机械地**拼装成一次写入。

关键：每一条 claim / test / why 都是从提议文件里**原样搬运**的，一个字都不经过模型。
triage 只能说「这两个 key 是同一个东西」，它物理上碰不到文字 ——
「不许发明」于是从一条 prompt 规矩变成了结构上做不到的事。
"""
import json


def load_props(files):
    """{aid: 提议dict}，key 全部命名空间化为 'AID:key'。"""
    out = {}
    for aid, f in files:
        out[aid] = json.load(open(f))
    return out


def build(props, mm, domains=None):
    """props: {aid: proposal}; mm: triage 的归并映射；domains: {aid: 这条事件来自哪个语料域}。
    返回 batch spec。"""
    canon, to_existing = {}, {}
    for m in mm.get("merges", []):
        for d in m.get("drop", []):
            canon[d] = m["keep"]
    for m in mm.get("map_to_existing", []):
        to_existing[m["proposal"]] = m["existing"]

    def resolve(aid, key):
        """局部 key -> 最终别名或库里真 id。"""
        if key == "ITEM":
            return f"i_{aid}"
        q = f"{aid}:{key}"
        seen = set()
        while q in canon and q not in seen:
            seen.add(q)
            q = canon[q]
        if q in to_existing:
            return to_existing[q]
        a, _, k = q.partition(":")
        # 已经是库里的真 id（提议里直接引用的 P3/C2/I7），原样返回
        return q.replace(":", "_") if k else key

    def is_local(aid, key):
        return any(key == x["key"] for x in props[aid].get("patterns", []) + props[aid].get("conditions", []))

    same = {s["item"]: s for s in mm.get("same_situation", [])}
    spec = dict(items=[], patterns=[], conditions=[], links=[], prescriptions=[],
                merges=mm.get("merges", []) + mm.get("map_to_existing", []))
    emitted = set()

    for aid, p in props.items():
        it = p.get("item") or {}
        spec["items"].append(dict(key=f"i_{aid}", source=aid, what=it.get("what", ""),
                                  facts=it.get("facts") or {},
                                  intervention=it.get("intervention"),
                                  outcome=it.get("outcome", "unknown"),
                                  domain=(domains or {}).get(aid)))

    for aid, p in props.items():
        for node, bucket in ((n, "patterns") for n in p.get("patterns", [])):
            q = f"{aid}:{node['key']}"
            if q in canon or q in to_existing:      # 被并掉 / 映射到已有，不新建
                continue
            alias = resolve(aid, node["key"])
            if alias in emitted:
                continue
            emitted.add(alias)
            spec["patterns"].append(dict(key=alias, source=aid, claim=node["claim"],
                                         side=node["side"], order=node.get("order", 1)))
        for node in p.get("conditions", []):
            q = f"{aid}:{node['key']}"
            if q in canon or q in to_existing:
                continue
            alias = resolve(aid, node["key"])
            if alias in emitted:
                continue
            emitted.add(alias)
            spec["conditions"].append(dict(key=alias, source=aid,
                                           claim=node["claim"], test=node["test"]))

    seen_links = set()
    for aid, p in props.items():
        s = same.get(aid)
        for l in p.get("links", []):
            src = resolve(aid, l["src"]) if (l["src"] == "ITEM" or is_local(aid, l["src"])) else l["src"]
            dst = resolve(aid, l["dst"]) if is_local(aid, l["dst"]) else l["dst"]
            k = (src, dst, l.get("polarity", "+"), aid)
            if k in seen_links:
                continue
            seen_links.add(k)
            e = dict(src=src, dst=dst, why=l["why"], source=aid, polarity=l.get("polarity", "+"))
            if s and src == f"i_{aid}":
                e["novel"] = False
                # triage 可以指向同批的某个 agent（"B1A2"），也可以指向库里已有的事件（"I12"）。
                # 后者不能再套 i_ 前缀，否则写进去的是一条永远解析不出的悬空引用。
                e["same_as"] = f"i_{s['same_as']}" if s["same_as"] in props else s["same_as"]
            spec["links"].append(e)
        for rx in p.get("prescriptions", []):
            ph = resolve(aid, rx["phenomenon"]) if is_local(aid, rx["phenomenon"]) else rx["phenomenon"]
            so = resolve(aid, rx["solution"]) if is_local(aid, rx["solution"]) else rx["solution"]
            cs = [resolve(aid, c) if is_local(aid, c) else c for c in rx.get("conditions", [])]
            # triage 可能用 claim 原文指代解法，解析不出来就会写进一个悬空引用。
            # 一条悬空引用会被后续检索反复命中，爆炸半径远大于它本身 —— 当场丢弃。
            known = set(alias.values()) | {x["key"] for x in spec["patterns"] + spec["conditions"]}
            if (so not in known and not so.startswith(("P", "C", "I"))) or \
               any(c not in known and not c.startswith(("P", "C")) for c in cs):
                spec.setdefault("_dropped", []).append(dict(aid=aid, why="prescription 引用解析不出", solution=so[:60]))
                continue
            spec["prescriptions"].append(dict(phenomenon=ph, conditions=cs, solution=so,
                                              item=f"i_{aid}", source=aid,
                                              outcome=rx.get("outcome", "none"), note=rx.get("note", "")))
    return spec


def verify(props, spec):
    """常驻断言：最终写入里的每一句话，都必须在某份提议里一字不差地出现过。"""
    orig = set()
    for p in props.values():
        for n in p.get("patterns", []) + p.get("conditions", []):
            orig.add(n["claim"])
            if "test" in n:
                orig.add(n["test"])
        for l in p.get("links", []):
            orig.add(l["why"])
        it = p.get("item") or {}
        if it.get("what"):
            orig.add(it["what"])
    bad = []
    for n in spec["patterns"] + spec["conditions"]:
        if n["claim"] not in orig:
            bad.append(("claim", n["claim"][:60]))
        if n.get("test") and n["test"] not in orig:
            bad.append(("test", n["test"][:60]))
    for l in spec["links"]:
        if l["why"] not in orig:
            bad.append(("why", l["why"][:60]))
    for i in spec["items"]:
        if i["what"] and i["what"] not in orig:
            bad.append(("item", i["what"][:60]))
    return bad

"""两种取法：沿层级下钻 vs 平铺 top-k。"""
from ph import domain as D
from ph.judge import lexical


def drill_down(nodes, task, judge, max_backtrack=1):
    """从根贪心往下，每层做一次判别式选择。不自信的叶子回溯一次，走次优分支。"""
    path, trail, backtracks = [], [], 0
    cur = "ROOT"
    while True:
        kids = D.children(nodes, cur)
        if not kids:
            break
        if len(kids) == 1:
            cur = kids[0]["id"]
            path.append(kids[0]["name"])
            continue
        r = judge.choose(task, kids, path)
        pick = r["choice"]
        if pick == "NONE":
            return None, path, "abstain"
        if pick not in {k["id"] for k in kids}:
            pick = kids[0]["id"]
        trail.append((cur, r, pick))
        cur = pick
        path.append(next(k["name"] for k in kids if k["id"] == pick))
        if nodes[cur]["level"] == 0 and not r.get("confident", True) and backtracks < max_backtrack:
            backtracks += 1
            alt = r.get("second")
            if alt and alt != "NONE" and alt in nodes:
                cur = alt
                path[-1] = nodes[alt]["name"] + "（回溯后）"
    return cur, path, "ok"


def flat_topk(nodes, task, judge, k=10):
    """字面相似度取 top-k 候选，再让同一个 judge 从中挑一个。"""
    ls = D.leaves(nodes)
    for n in ls:
        p = nodes[n["parent"][0]]
        gp = nodes[p["parent"][0]]
        n["_full"] = f"{gp['name']}；{p['name']}；{n['name']}"
    short = sorted(ls, key=lambda n: -lexical(task, n["_full"]))[:k]
    cands = [{"id": n["id"], "name": n["_full"], "vs_siblings": ""} for n in short]
    if len(cands) == 1:
        return cands[0]["id"], "ok"
    r = judge.choose(task, cands, ())
    pick = r["choice"]
    if pick == "NONE":
        return None, "abstain"
    return (pick if pick in {c["id"] for c in cands} else cands[0]["id"]), "ok"


def lexical_top1(nodes, task):
    """B0：纯字面，不过 LLM。用来看这个域到底有多 confusable。"""
    ls = D.leaves(nodes)
    best = max(ls, key=lambda n: lexical(task, n["name"] + nodes[n["parent"][0]]["name"]))
    return best["id"]

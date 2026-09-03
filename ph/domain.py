"""合成域：对一组记录做 filter -> sort -> take 的流水线。

一个 leaf template = (field, direction, filter, cut)，四个属性正好对应层级的四层。
任务描述用「间接说法」生成（说目标，不说步骤），pattern 节点用「过程说法」描述，
两者词面重叠很低 —— 否则平铺检索靠字面匹配就赢了，实验没意义。
"""
from itertools import product

FIELDS = ["a", "b", "c"]
DIRS = ["desc", "asc"]
FILTS = [None, ("gt", 50), ("lt", 50)]
CUTS = [1, 2, 3, 5, 10]

SKINS = {
    "orders": {"noun": "订单", "unit": "笔",
               "fields": {"a": "金额", "b": "件数", "c": "折扣率"}},
    "logs": {"noun": "请求", "unit": "条",
             "fields": {"a": "延迟", "b": "重试次数", "c": "负载"}},
}


def all_templates():
    return list(product(FIELDS, DIRS, FILTS, CUTS))


def tid(t):
    f, d, fl, c = t
    return f"L:{f}:{d}:{'none' if fl is None else fl[0] + str(fl[1])}:{c}"


def run(t, rows):
    """执行流水线，返回 id 列表。程序化验证，不用 LLM 打分。"""
    f, d, fl, c = t
    out = rows
    if fl:
        op, thr = fl
        out = [r for r in out if (r[f] > thr if op == "gt" else r[f] < thr)]
    out = sorted(out, key=lambda r: (-r[f] if d == "desc" else r[f], r["id"]))
    return [r["id"] for r in out[:c]]


def make_rows(rng, n=14):
    return [{"id": i, "a": rng.randint(1, 100), "b": rng.randint(1, 100),
             "c": rng.randint(1, 100)} for i in range(n)]


# ---- 任务描述：间接说法 ----
_TOP = ["排在最前面的", "最靠前的", "拔尖的"]
_BOT = ["垫底的", "最靠后的", "最不起眼的"]


def describe_task(t, skin, rng):
    f, d, fl, c = t
    s = SKINS[skin]
    fn, noun, unit = s["fields"][f], s["noun"], s["unit"]
    pre = ""
    if fl:
        pre = f"只看{fn}{'超过' if fl[0] == 'gt' else '不到'}{fl[1]}的，"
    w = rng.choice(_TOP if d == "desc" else _BOT)
    return f"{pre}这批{noun}里{fn}{w}{c}{unit}是哪些？"


# ---- 层级：四层 + 根，从模板元组机械生成，ground truth 已知 ----
def _fname(f, skin):
    return SKINS[skin]["fields"][f]


def build_hierarchy(templates, skin):
    """给定一批 leaf template，生成它们诱导出的层级（节点 dict）。"""
    nodes, seen = {}, set()

    def add(nid, level, name, vs, parent, tpl=None):
        if nid in seen:
            nodes[nid]["parent"] = sorted(set(nodes[nid]["parent"] + ([parent] if parent else [])))
            return
        seen.add(nid)
        nodes[nid] = {"id": nid, "level": level, "name": name, "vs_siblings": vs,
                      "parent": [parent] if parent else [], "tpl": tpl}

    add("ROOT", 4, "所有做法", "", None)
    for t in templates:
        f, d, fl, c = t
        fn = _fname(f, skin)
        q = f"Q:{f}"
        dd = f"D:{f}:{d}"
        ff = f"F:{f}:{d}:{'none' if fl is None else fl[0] + str(fl[1])}"
        add(q, 3, f"以「{fn}」作为排序依据", f"看的是{fn}这个量，不是别的量", "ROOT")
        add(dd, 2, f"按{fn}{'降序（大的在前）' if d == 'desc' else '升序（小的在前）'}排序",
            f"要的是{fn}{'最大' if d == 'desc' else '最小'}的那一端", q)
        add(ff, 1,
            "不做筛选，在全体上排序" if fl is None
            else f"先筛掉{fn}{'不超过' if fl[0] == 'gt' else '不低于'}{fl[1]}的，再排序",
            "没有筛选条件" if fl is None else f"筛选条件是 {fn} {'>' if fl[0] == 'gt' else '<'} {fl[1]}", dd)
        add(tid(t), 0, f"排序后取前 {c} 条", f"取 {c} 条", ff, tpl=t)
    return nodes


def children(nodes, nid):
    return [n for n in nodes.values() if nid in n["parent"]]


def leaves(nodes):
    return [n for n in nodes.values() if n["level"] == 0]


def siblings_of(t):
    """同 filter 父节点下的兄弟：只在「取几条」上不同，词面几乎一样 —— confusable 的来源。"""
    f, d, fl, _ = t
    return [(f, d, fl, c) for c in CUTS]

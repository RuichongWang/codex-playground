# -*- coding: utf-8 -*-
"""一次性脚本：给已有库快照里的每个 item 补上 domain 字段。

新写入的 item 由 add_item 直接带 domain，只有这三个已经建好的快照需要倒推。
倒推用 pk/domain.py 的 bigram 模糊匹配（90/90 人工核对过），匹配不上的标 "?" 并当场报出来 ——
错标一条 item 会让被屏蔽域的证据偷偷留在库里，比少标一条严重得多，所以宁可显式报错。

    python3 -m pk.tag_domains            # 只看会改成什么，不写
    python3 -m pk.tag_domains --write    # 写回，改之前每个文件先存一份 .bak
"""
import argparse
import json
import os
import shutil
from collections import Counter

from pk.domain import ROOT, item_domain

SNAPSHOTS = [
    "runs/r3/library.json",                  # 90 条，当前在用
    "runs/r3/library_round2_frozen.json",    # 60 条
    "runs/r2/library_round1_frozen.json",    # 30 条
    "pk/library.json",                       # 30 条，第一轮的工作库
]


def tag(path, write=False, repair=True):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        print(f"{path}: 不存在，跳过")
        return
    d = json.load(open(full))
    doms, changed = Counter(), 0
    for n in d["nodes"].values():
        if n["kind"] != "item":
            continue
        # 已经打过标的不重算：倒推是有阈值的启发式，重跑一次可能给出不同答案
        dom = n.get("domain") or item_domain(n)
        doms[dom] += 1
        if n.get("domain") != dom:
            n["domain"] = dom
            changed += 1

    fixed = 0
    if repair:
        # assemble 把 triage 写的库内真 id（"I12"）当成了 agent id，拼成了 "i_I12"。
        # 是一条悬空引用，只影响溯源不影响任何计分，但屏蔽后的完整性检查会红 —— 顺手修掉。
        # 只动指针，不动任何 claim 文字。
        for l in d["links"]:
            sa = l.get("same_as")
            if sa and sa not in d["nodes"] and sa.startswith("i_") and sa[2:] in d["nodes"]:
                l["same_as"] = sa[2:]
                fixed += 1

    miss = doms.get("?", 0)
    print(f"{path}: item {sum(doms.values())} / 新打标 {changed} / 修复 same_as 指针 {fixed}"
          + (f" / ⚠️ 认不出域的 {miss} 条" if miss else ""))
    print("   " + "  ".join(f"{k}={v}" for k, v in sorted(doms.items())))
    if write:
        # 已有 .bak 就不覆盖：重跑一次这个脚本不能把「改动前那一份」冲掉
        if not os.path.exists(full + ".bak"):
            shutil.copy(full, full + ".bak")
        json.dump(d, open(full, "w"), ensure_ascii=False, indent=1)
        print(f"   已写回（备份 {path}.bak）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--no-repair", dest="repair", action="store_false")
    a = ap.parse_args()
    for p in SNAPSHOTS:
        tag(p, a.write, a.repair)
    if not a.write:
        print("\n（试跑，没有写。加 --write 才落盘）")


if __name__ == "__main__":
    main()

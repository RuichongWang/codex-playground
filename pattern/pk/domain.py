# -*- coding: utf-8 -*-
"""item 属于哪个语料域 —— 只为「运行时屏蔽」服务，不参与可信度计算。

store.py 里那段「没有 domain 字段」的理由现在依然成立：域不是证据的单位，
一条解法在「电力」里成立不代表在电力的任何场景都成立。所以 domain 在这里
**只有一个用途**：测跨域迁移时，把某个域的痕迹从库里整体拿掉，看剩下的库还能不能帮上忙。
它是实验器材，不是知识结构的一部分 —— credibility / score 一个字都不看它。

之所以要模糊匹配而不是精确匹配：提议 agent 是「用自己的话复述」原始语料的，
文字跟语料对不上。bigram 交并比取最佳，在 90 个 item 上人工核对过 90/90 全对。
新写入的 item 直接带 domain 字段（见 Store.add_item），不再需要猜。
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 匹配阈值：低于这个相似度就认命说「不知道」，宁可报 ? 也不要塞给一个错的域 ——
# 屏蔽时错标一条 item 会让被屏蔽域的证据偷偷留在库里，那比少屏蔽一条更糟。
MIN_SIM = 0.12

_CORPUS = None


def _corpus():
    global _CORPUS
    if _CORPUS is None:
        _CORPUS = []
        for f in sorted(glob.glob(os.path.join(ROOT, "corpus*/*.json"))):
            dom = os.path.basename(f).replace(".json", "")
            for r in json.load(open(f)):
                txt = r["what"] + " " + " ".join(f"{k}{v}" for k, v in (r.get("facts") or {}).items())
                _CORPUS.append((dom, txt))
    return _CORPUS


def all_domains():
    """语料里存在的全部域，按名字排序。"""
    return sorted({d for d, _ in _corpus()})


def _bg(t):
    return {t[i:i + 2] for i in range(len(t) - 1)}


_CACHE = {}


def item_domain(node):
    """一个 item 节点属于哪个语料域。已经带 domain 字段的直接用，不再重猜。"""
    if node.get("domain"):
        return node["domain"]
    nid = node.get("id")
    if nid in _CACHE:
        return _CACHE[nid]
    t = _bg((node.get("what") or "") + " " +
            " ".join(f"{k}{v}" for k, v in (node.get("facts") or {}).items()))
    best, score = "?", 0.0
    for dom, txt in _corpus():
        o = _bg(txt)
        r = len(t & o) / max(1, len(t | o))
        if r > score:
            best, score = dom, r
    out = best if score >= MIN_SIM else "?"
    _CACHE[nid] = out
    return out

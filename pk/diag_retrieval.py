# -*- coding: utf-8 -*-
"""检索诊断：字面 top-k 相对于「模型通读全库」丢了多少。

阶段 3 里 C 拿到的库内容，相关性看起来跟 D 的张冠李戴差不多。
如果真是这样，那次实验测的不是「有库 vs 没库」，而是「不相关的库 vs 不相关的库」。
这个脚本直接量它：把全部 pattern 的 claim 一次性给模型（约 15k token，放得下），
让它挑真正相关的，再跟字面 top-k 比。
"""
import argparse, glob, json, os, re, sys
import concurrent.futures as cf
from pk.eval3 import claude, jparse, ROOT
from pk.store import Store

PROMPT = """下面是一个真实情况，以及一个跨行业知识库里全部假说的清单。

【情况】
{situation}

【提议的干预】
{intervention}

【库里的全部假说】
{catalog}

要判断上面那个干预行不行，这个库里**哪些假说是真正用得上的**？
通读全部，挑出最有用的 5 条，按有用程度排序。如果一条都用不上，就给空数组——
**不要为了凑数硬挑**，挑一条不相关的比漏一条更糟。

只输出 JSON：
{{"picks": [编号数组，最多5个，按有用程度排序], "any_useful": true 或 false,
  "why": "一句话说明你为什么挑这几条，或者为什么一条都用不上"}}"""


def run(case, s, catalog, ids):
    txt, cost = claude(PROMPT.format(situation=case["situation"],
                                     intervention=case["intervention"], catalog=catalog))
    d = jparse(txt) or {}
    picks = [ids[i - 1] for i in (d.get("picks") or [])
             if isinstance(i, int) and 1 <= i <= len(ids)]
    lex = [p["id"] for p in s.search(case["situation"], kind="pattern", limit=8)]
    lex5 = lex[:5]
    return dict(id=case["id"], read_picks=picks, lex_top5=lex5, lex_top8=lex,
                overlap5=len(set(picks) & set(lex5)), overlap8=len(set(picks) & set(lex)),
                any_useful=bool(d.get("any_useful")), why=d.get("why", ""), cost=cost)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="runs/stage3/retrieval_diag.jsonl")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    s = Store.load(os.path.join(ROOT, "runs/r3/library.json"))
    pats = [n for n in s.nodes.values() if n["kind"] == "pattern"]
    ids = [p["id"] for p in pats]
    catalog = "\n".join(f"{i+1}. [{'现象' if p['side']=='phenomenon' else '解法'}] {p['claim']}"
                        for i, p in enumerate(pats))
    print(f"全库 {len(pats)} 个 pattern，目录 {len(catalog)} 字 ≈ {len(catalog)//1.5:.0f} token")

    cases = [c for f in sorted(glob.glob(os.path.join(ROOT, "heldout/*.json")))
             for c in json.load(open(f))]
    done = set()
    if os.path.exists(a.out):
        done = {json.loads(l)["id"] for l in open(a.out) if l.strip()}
    todo = [c for c in cases if c["id"] not in done]
    print(f"{len(cases)} 条，待跑 {len(todo)}")

    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(run, c, s, catalog, ids) for c in todo]
        for i, f in enumerate(cf.as_completed(futs), 1):
            try:
                r = f.result()
                open(a.out, "a").write(json.dumps(r, ensure_ascii=False) + "\n")
            except Exception as e:
                print("  !", e)
            if i % 10 == 0:
                print(f"  {i}/{len(todo)}")

    rows = [json.loads(l) for l in open(a.out) if l.strip()]
    n = len(rows)
    print(f"\n=== 检索诊断 n={n} ===")
    print(f"  通读认为库里有用得上的: {sum(r['any_useful'] for r in rows)}/{n}")
    print(f"  通读挑出的 与 字面top5 重合: 平均 {sum(r['overlap5'] for r in rows)/n:.2f} / 5")
    print(f"  通读挑出的 与 字面top8 重合: 平均 {sum(r['overlap8'] for r in rows)/n:.2f}")
    miss = [r for r in rows if r["any_useful"] and r["overlap8"] == 0]
    print(f"  **库里有用但字面 top8 一条都没捞到: {len(miss)}/{n} = {len(miss)/n:.0%}**")
    print(f"\n累计 ${sum(r['cost'] for r in rows):.2f}")


if __name__ == "__main__":
    main()

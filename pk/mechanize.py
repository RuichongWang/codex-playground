# -*- coding: utf-8 -*-
"""给每条 checklist 判据补一个「机制版」写法。

逐元素判分奖励「用案例自己的词回答」，而库的作用恰恰是把答案推向跨域的机制语言。
于是库臂会因为答得更抽象而被判低 —— 这是指标的偏差，不是答案的问题。
补一份领域中立的改写，判分时任一命中即可。
"""
import argparse, glob, json, os
import concurrent.futures as cf
from pk.eval3 import claude, jparse, ROOT

PROMPT = """把下面这些判据各改写成一句**领域中立的机制陈述**。

【它们所在的情况】{situation}

【判据】
{conds}

改写要求：
- **去掉行业专有名词**（弹体、LAP、微震台网、配额、拍摄日…），换成它在结构上说的那件事
- 保留判据的**逻辑形状**：它要确认的是「哪个量是约束」「哪条链有没有闭合」「时间窗够不够」…
- 一个在**完全不同行业**遇到同类问题的人，读了应该能认出「这就是我要问的那件事」
- 不要变笼统。「要确认瓶颈在哪」太空；「要确认被扩产的那一环是不是全链的最小值，
  否则新增产能只会变成在制品」才是对的粒度

只输出 JSON：{{"mech": ["第1条的机制版", "第2条的机制版", ...]}}
数组长度必须与判据条数一致，顺序一一对应。"""


def run(case):
    conds = "\n".join(f"{i+1}. {c}" for i, c in enumerate(case["conditions"]))
    txt, cost = claude(PROMPT.format(situation=case["situation"][:900], conds=conds))
    d = jparse(txt) or {}
    m = d.get("mech") or []
    if len(m) != len(case["conditions"]):
        m = (m + [""] * len(case["conditions"]))[:len(case["conditions"])]
    return dict(id=case["id"], mech=m, cost=cost)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="heldout/conditions_mech.json")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    cases = [c for f in sorted(glob.glob(os.path.join(ROOT, "heldout/*.json")))
             if "mech" not in f for c in json.load(open(f))]
    done = json.load(open(a.out)) if os.path.exists(a.out) else {}
    todo = [c for c in cases if c["id"] not in done]
    print(f"{len(cases)} 条，待跑 {len(todo)}")
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for r in cf.as_completed([ex.submit(run, c) for c in todo]):
            try:
                x = r.result()
                done[x["id"]] = x["mech"]
                json.dump(done, open(a.out, "w"), ensure_ascii=False, indent=1)
            except Exception as e:
                print("  !", e)
    print(f"完成 {len(done)}/{len(cases)}")
    ex_id = cases[0]["id"]
    print(f"\n例（{ex_id}）：")
    for o, m in zip(cases[0]["conditions"], done.get(ex_id, [])):
        print(f"  领域: {o[:80]}\n  机制: {m[:80]}\n")


if __name__ == "__main__":
    main()

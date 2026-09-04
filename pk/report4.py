# -*- coding: utf-8 -*-
"""阶段 4 汇总：陷阱规避为主，条件 F1 为辅。"""
import argparse, glob, json, math, os
from collections import defaultdict
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p):
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def sign(w, l):
    n = w + l
    if n == 0:
        return 1.0
    k = min(w, l)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="runs/stage4"); a = ap.parse_args()
    P = lambda n: os.path.join(a.out, n)
    cases = {c["id"]: c for f in sorted([f for f in glob.glob(os.path.join(ROOT, "heldout/*.json")) if "mech" not in f])
             for c in json.load(open(f))}
    ans = {(r["id"], r["arm"]): r for r in load(P("answers.jsonl"))}
    trap = {(r["id"], r["arm"]): r for r in load(P("trap.jsonl"))}
    f1 = {(r["id"], r["arm"]): r for r in load(P("f1.jsonl"))}
    arms = sorted({k[1] for k in ans})
    if not arms:
        print("还没有结果"); return

    fails = [i for i in cases if cases[i]["outcome"] == "failed"
             and all((i, m) in trap and not trap[(i, m)].get("skip") for m in arms)]
    print("=" * 70)
    print(f"阶段 4（不给干预，自己提方案）—— 陷阱题 n={len(fails)}")
    print("=" * 70)
    print(f"\n{'':22}" + "".join(f"{m:>10}" for m in arms))
    rows = defaultdict(dict)
    for m in arms:
        pt = sum(trap[(i, m)]["proposed_trap"] for i in fails)
        nf = sum(trap[(i, m)]["named_the_flaw"] for i in fails)
        safe = sum(1 for i in fails
                   if not trap[(i, m)]["proposed_trap"] or trap[(i, m)]["named_the_flaw"])
        rows["走进陷阱"][m] = pt / max(1, len(fails))
        rows["点出了致命缺陷"][m] = nf / max(1, len(fails))
        rows["规避率(主指标)"][m] = safe / max(1, len(fails))
    for k in ("走进陷阱", "点出了致命缺陷", "规避率(主指标)"):
        print(f"{k:22}" + "".join(f"{rows[k][m]:>10.1%}" for m in arms))

    if "C" in arms and "D" in arms:
        w = l = 0
        for i in fails:
            sc = (not trap[(i, "C")]["proposed_trap"]) or trap[(i, "C")]["named_the_flaw"]
            sd = (not trap[(i, "D")]["proposed_trap"]) or trap[(i, "D")]["named_the_flaw"]
            if sc and not sd: w += 1
            elif sd and not sc: l += 1
        print(f"\n  C−D 规避率 = {rows['规避率(主指标)']['C']-rows['规避率(主指标)']['D']:+.1%}"
              f"   C独赢{w} / D独赢{l}   符号检验 p={sign(w,l):.3f}")

    common = [i for i in cases if all((i, m) in f1 and f1[(i, m)]["n"] for m in arms)]
    if common:
        print(f"\n{'─'*70}\n条件 F1（全部 n={len(common)}）")
        print(f"{'':22}" + "".join(f"{m:>10}" for m in arms))
        for m in arms:
            v = 0
            for i in common:
                g = f1[(i, m)]
                r = len(g["hits"]) / g["n"]; t = len(g["hits"]) + g["extra"]
                p_ = len(g["hits"]) / t if t else 0
                v += 2 * r * p_ / (r + p_) if r + p_ else 0
            rows["F1"][m] = v / len(common)
        print(f"{'F1':22}" + "".join(f"{rows['F1'][m]:>10.3f}" for m in arms))

    len_rows = load(P("lenient.jsonl"))
    if len_rows:
        print(f"\n{'─'*70}\n宽松版判分（给 ground truth、配对盲判、强制引证）")
        agg = defaultdict(lambda: defaultdict(int))
        for r in len_rows:
            agg[r["pair"]][r["winner"]] += 1
        for k in sorted(agg):
            x, y = k.split("v")
            v = agg[k]
            print(f"  {k:8} {x} 胜 {v[x]:>2} / {y} 胜 {v[y]:>2} / 平 {v['tie']:>2}"
                  f"   p={sign(v[x], v[y]):.3f}" + ("  ✱" if sign(v[x], v[y]) < 0.05 else ""))
        print("\n  两套判分方向一致则结论稳；相反则效应落在测量自身的偏差带里。")

    cost = sum(r.get("cost", 0) for f in ("answers", "trap", "f1", "lenient")
               for r in load(P(f + ".jsonl")))
    print(f"\n累计 ${cost:.2f}")


if __name__ == "__main__":
    main()

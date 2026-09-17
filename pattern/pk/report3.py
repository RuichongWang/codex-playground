# -*- coding: utf-8 -*-
"""阶段 3 汇总：按预注册的判定规则出表。"""
import argparse, glob, json, os, math
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p):
    out = []
    if os.path.exists(p):
        for l in open(p):
            try: out.append(json.loads(l))
            except Exception: pass
    return out


def sign_test(wins, losses):
    """双侧符号检验精确 p 值。"""
    n = wins + losses
    if n == 0: return 1.0
    k = min(wins, losses)
    c = sum(math.comb(n, i) for i in range(k + 1))
    return min(1.0, 2 * c / (2 ** n))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="runs/stage3"); a = ap.parse_args()
    P = lambda n: os.path.join(a.out, n)
    cases = []
    for f in sorted([f for f in glob.glob(os.path.join(ROOT, "heldout/*.json")) if "mech" not in f]): cases += json.load(open(f))
    cmap = {c["id"]: c for c in cases}

    pj = {r["id"]: r for r in load(P("probe_judge.jsonl"))}
    ans = {(r["id"], r["arm"]): r for r in load(P("answers.jsonl"))}
    f1 = {(r["id"], r["arm"]): r for r in load(P("f1.jsonl"))}
    pairs = load(P("pairs.jsonl"))
    arms = sorted({k[1] for k in ans})

    # 污染分层
    contam = {i: (pj.get(i, {}).get("identified") and pj.get(i, {}).get("root_cause_match")) for i in cmap}
    known = [i for i in cmap if contam.get(i)]
    unknown = [i for i in cmap if i in ans_ids(ans) and not contam.get(i)]

    print("=" * 74)
    print("阶段 3 迁移实验 —— 结果")
    print("=" * 74)
    print(f"\n【污染分层】共 {len(cmap)} 条")
    print(f"  模型认得出且根因也对得上（受污染）：{len(known)}")
    print(f"  认不出或根因对不上（干净）：      {len(cmap)-len(known)}")
    if len(cmap) - len(known) < 10:
        print("  ⚠️ 干净样本 < 10，按预注册规则：主结论判为『没测出来』，不是『没用』")

    for label, ids in (("全部 30 条", list(cmap)), ("仅干净样本", [i for i in cmap if not contam.get(i)]),
                       ("仅受污染样本", known)):
        # 只在四臂都给出可解析输出的交集上算 —— 否则各臂在不同子集上取平均，不可比。
        # 首轮就是栽在这里：C 有 3 个案例没吐出概率，恰好都是难题，均值凭空好了 5 倍。
        ids = [i for i in ids
               if all(isinstance(ans.get((i, m), {}).get("probability"), (int, float)) for m in arms)]
        if not ids: continue
        print(f"\n{'─'*74}\n【{label}】n={len(ids)}")
        hdr = f"{'':16}" + "".join(f"{m:>10}" for m in arms)
        print(hdr)
        rows = defaultdict(dict)
        for m in arms:
            R = P_ = 0.0; nn = 0; brier = 0.0; nb = 0; acc = 0; na = 0
            for i in ids:
                g = f1.get((i, m)); v = ans.get((i, m))
                if g and g["n"]:
                    r_ = len(g["hits"]) / g["n"]
                    tot = len(g["hits"]) + g["extra"]
                    p_ = len(g["hits"]) / tot if tot else 0.0
                    R += r_; P_ += p_; nn += 1
                if v and isinstance(v.get("probability"), (int, float)):
                    y = 1.0 if cmap[i]["outcome"] == "worked" else 0.0
                    brier += (max(0, min(100, v["probability"])) / 100 - y) ** 2; nb += 1
                if v and v.get("verdict") in ("worked", "failed"):
                    acc += (v["verdict"] == cmap[i]["outcome"]); na += 1
            rec = R / nn if nn else 0; pre = P_ / nn if nn else 0
            rows["recall"][m] = rec; rows["precision"][m] = pre
            rows["F1"][m] = 2 * rec * pre / (rec + pre) if rec + pre else 0
            rows["Brier"][m] = brier / nb if nb else float("nan")
            rows["预测准确率"][m] = acc / na if na else float("nan")
        for k in ("F1", "precision", "recall", "Brier", "预测准确率"):
            print(f"{k:16}" + "".join(f"{rows[k][m]:>10.3f}" for m in arms))
        base = sum(1 for i in ids if cmap[i]["outcome"] == "failed") / len(ids)
        print(f"{'(全押failed基线)':16}{max(base,1-base):>10.3f}")

        # 主判据
        if "C" in arms and "D" in arms:
            w = l = 0
            for i in ids:
                gc, gd = f1.get((i, "C")), f1.get((i, "D"))
                if not gc or not gd or not gc["n"]: continue
                def _f1(g):
                    r_ = len(g["hits"]) / g["n"]; t = len(g["hits"]) + g["extra"]
                    p_ = len(g["hits"]) / t if t else 0.0
                    return 2 * r_ * p_ / (r_ + p_) if r_ + p_ else 0.0
                a_, b_ = _f1(gc), _f1(gd)
                if a_ > b_: w += 1
                elif b_ > a_: l += 1
            d = rows["F1"]["C"] - rows["F1"]["D"]
            print(f"\n  主判据 C−D 条件F1 = {d:+.3f}（预注册门槛 ≥ +0.15）")
            print(f"  逐案例 C 胜 {w} / D 胜 {l} / 平 {len(ids)-w-l}，符号检验 p = {sign_test(w,l):.3f}")
            print(f"  → {'库有用' if d>=0.15 and sign_test(w,l)<0.05 else '未达预注册门槛'}")

    print(f"\n{'─'*74}\n【机制诊断 配对盲比】")
    agg = defaultdict(lambda: defaultdict(int))
    for p in pairs: agg[p["pair"]][p["winner"]] += 1
    for k, v in agg.items():
        x, y = k.split("v")
        print(f"  {k}: {x} 胜 {v[x]} / {y} 胜 {v[y]} / 平 {v['tie']}  符号检验 p={sign_test(v[x],v[y]):.3f}")

    cost = sum(r.get("cost", 0) for f in ("probe", "probe_judge", "answers", "f1", "pairs")
               for r in load(P(f + ".jsonl")))
    print(f"\n累计 ${cost:.2f}")


def ans_ids(ans): return {k[0] for k in ans}


if __name__ == "__main__":
    main()

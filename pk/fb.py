# -*- coding: utf-8 -*-
"""ForecastBench：把库带到一个跟它毫无领域重叠的任务上。

库里 90 个事件全是历史工业事故复盘，零条预测题、零条金融/地缘/体育。
所以这里若有增益，能解释它的只剩跨域抽象本身 —— 不存在领域重叠这个替代解释。
"""
import argparse, glob, json, os, subprocess, time
import concurrent.futures as cf
from pk.eval3 import ROOT, jparse, parallel
from pk.eval3b import LIB_BLOCK, SKILL

FB = "/home/user/forecastingresearch/forecastbench-datasets/datasets"

PROMPT = """今天是 {due}。下面是一个关于**未来**的问题，你要给出它发生的概率。

【问题】{question}

【背景】{background}

【判定标准】{criteria}
{market}{lib}
请给出：
1. 你的推理 —— 尤其是你参照的是什么基准率、什么机制会推动或阻止它发生
2. 这件事发生的概率，0 到 100 的整数

{sink}
{{"reasoning": "推理", "probability": 数字}}
{tail}"""


def load_pair(tag):
    qd = json.load(open(f"{FB}/question_sets/{tag}-llm.json"))
    rd = json.load(open(f"{FB}/resolution_sets/{tag}_resolution_set.json"))
    qs = {q["id"]: q for q in qd["questions"]}
    out = []
    seen = set()
    for r in rd["resolutions"]:
        if not r.get("resolved") or r["id"] not in qs or r["id"] in seen:
            continue
        seen.add(r["id"])
        q = dict(qs[r["id"]])
        q["resolved_to"] = r["resolved_to"]
        q["resolution_date"] = r.get("resolution_date")
        q["due"] = qd["forecast_due_date"]
        out.append(q)
    return out


def run(q, arm, outdir):
    out = f"{outdir}/fb_{q['id'][:12]}_{arm}.json"
    lib = "" if arm == "A" else LIB_BLOCK.format(
        skill=SKILL, db=os.path.join(ROOT, "runs/r3/library.json"), root=ROOT)
    mv = q.get("freeze_datetime_value")
    market = (f"\n【冻结时刻的市场价】{float(mv):.3f}\n" if mv not in (None, "N/A") else "")
    sink = ("只输出 JSON，不要任何别的文字：" if arm == "A"
            else f"把答案写进文件 {out}：")
    tail = "" if arm == "A" else "\n写完文件就结束。"
    cmd = ["claude", "-p", "--model", "claude-opus-5", "--output-format", "stream-json",
           "--verbose", "--include-partial-messages"]
    cmd += (["--allowed-tools", "", "--strict-mcp-config"] if arm == "A" else
            ["--allowed-tools", "Bash", "--permission-mode", "acceptEdits", "--add-dir", ROOT])
    t0 = time.time()
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=1200,
                       input=PROMPT.format(due=q["due"], question=q["question"],
                                           background=str(q.get("background", ""))[:1500],
                                           criteria=str(q.get("resolution_criteria", ""))[:600],
                                           market=market, lib=lib, sink=sink, tail=tail))
    open(f"{outdir}/trace_{q['id'][:12]}_{arm}.jsonl", "w").write(p.stdout)
    meta = {}
    for line in p.stdout.splitlines():
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if ev.get("type") == "result":
            meta = ev
    if meta.get("is_error"):
        raise RuntimeError((meta.get("result") or "")[:120])
    d = (jparse(open(out).read()) if os.path.exists(out) else jparse(meta.get("result", ""))) or {}
    return dict(id=q["id"], arm=arm, source=q["source"], question=q["question"][:110],
                probability=d.get("probability"), reasoning=(d.get("reasoning") or "")[:1500],
                resolved_to=q["resolved_to"], market=mv if mv != "N/A" else None,
                turns=meta.get("num_turns"), secs=round(time.time() - t0, 1),
                cost=meta.get("total_cost_usd", 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="2026-06-07")
    ap.add_argument("--out", default="runs/fb")
    ap.add_argument("--arms", default="A,C")
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    qs = load_pair(a.tag)[:a.limit]
    arms = a.arms.split(",")
    print(f"{a.tag}：取前 {len(qs)} 题 × {arms}")
    for q in qs:
        print(f"  [{q['source']}] {q['question'][:80]}  → 实际 {q['resolved_to']}")
    jobs = [(lambda q=q, m=m: run(q, m, a.out), dict(id=q["id"], arm=m)) for q in qs for m in arms]
    res = parallel(jobs, a.workers, os.path.join(a.out, "answers.jsonl"),
                   lambda r: (r["id"], r["arm"]), "fb")
    print("\n=== 结果 ===")
    for m in arms:
        v = [r for r in res.values() if r["arm"] == m and r["probability"] is not None]
        if not v:
            print(f"  {m}: 无产出"); continue
        b = sum((r["probability"] / 100 - r["resolved_to"]) ** 2 for r in v) / len(v)
        print(f"  {m}: n={len(v)}  Brier={b:.4f}  ${sum(r['cost'] for r in v):.2f}")
    mk = [r for r in res.values() if r["arm"] == arms[0] and r.get("market") is not None]
    if mk:
        b = sum((float(r["market"]) - r["resolved_to"]) ** 2 for r in mk) / len(mk)
        print(f"  市场价基线: n={len(mk)} Brier={b:.4f}")
    for r in sorted(res.values(), key=lambda r: (r["id"], r["arm"])):
        print(f"\n  [{r['arm']}] {r['question'][:70]}")
        print(f"      预测 {r['probability']}  实际 {r['resolved_to']*100:.0f}  "
              f"市场 {(float(r['market'])*100 if r.get('market') is not None else -1):.0f}  "
              f"{r['turns']}轮 ${r['cost']:.2f}")


if __name__ == "__main__":
    main()

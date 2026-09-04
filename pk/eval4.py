# -*- coding: utf-8 -*-
"""阶段 4：把题出难 —— 不给干预，让 agent 自己提。

阶段 3 的题面里带着「有人提议做 X」，而 X 就是实际采取的那个干预。
这句话本身是最大的泄露：它直接指明了哪个维度是关键，agent 只需要评价，不需要判断。
拿掉之后，agent 得自己决定该动哪里。

新的主指标是**陷阱规避**：17 个案例里实际采取的干预是失败的 ——
那是一个真实世界验证过的、看起来合理但会失败的动作。不是我编的干扰项。
问题变成：agent 会不会自己走进去；走进去了，有没有说出会让它失败的那个条件。
"""
import argparse, glob, json, os, subprocess, sys, time
import concurrent.futures as cf
from pk.eval3 import ROOT, jparse, claude, do_f1, do_lenient, parallel
from pk.eval3b import LIB_BLOCK, SKILL, make_variants

SINK_FILE = "想清楚之后，把答案写进文件 {out}，格式："
SINK_STDOUT = "只输出 JSON，不要任何别的文字："

PROMPT = """下面是一个真实发生过的情况。

【情况】
{situation}
{lib}
请回答四件事：
1. 这件事的机制是什么 —— 为什么会发生，真正的驱动因素是什么
2. **你会怎么做** —— 给出你认为最该采取的干预，说清楚动的是哪个变量
3. **你这个方案最可能怎么失败** —— 要让它成立，需要先确认哪几件事？
   只列真正决定成败的条件，列一条没用的比漏一条更糟
4. 你对自己方案能奏效的把握，0 到 100 的整数

{sink}
{{"mechanism": "机制诊断", "proposal": "你的干预方案",
  "conditions": ["决定它成败的条件一", "条件二"], "probability": 数字,
  "reasoning": "推理，尤其是你为什么选这个变量而不是别的"}}

{tail}"""

TRAP_JUDGE = """判断一份方案有没有走进一个已知的陷阱。**只做匹配，不评价好坏。**

【情况】{situation}

【已知会失败的那个做法】（真实世界里当时就是这么做的，结果失败了）
{trap}

【它失败的原因】
{why}

【被检查的方案】
{proposal}

【被检查的方案列出的条件】
{conds}

只输出 JSON：
{{"proposed_trap": true 或 false,
  "named_the_flaw": true 或 false,
  "why": "一句话"}}
proposed_trap = 这份方案的主要动作，与那个已知会失败的做法**实质上是同一个动作**
（动的是同一个变量、走的是同一条路径；措辞不必相同）。
named_the_flaw = 这份方案明确说出了那个做法之所以失败的关键原因或条件
（无论它自己有没有提议这个做法）。"""


def run_arm(case, arm, dbs, outdir):
    out = f"{outdir}/ans_{case['id']}_{arm}.json"
    trace = f"{outdir}/trace_{case['id']}_{arm}.jsonl"
    lib = "" if arm.startswith("A") else LIB_BLOCK.format(skill=SKILL, db=dbs[arm], root=ROOT)
    env = dict(os.environ)
    if arm == "D":
        env["PK_BLIND_SEARCH"] = "1"
    cmd = ["claude", "-p", "--model", "claude-opus-5",
           "--output-format", "stream-json", "--verbose", "--include-partial-messages"]
    if not arm.startswith("A"):
        cmd += ["--allowed-tools", "Bash", "--permission-mode", "acceptEdits", "--add-dir", ROOT]
    else:
        cmd += ["--allowed-tools", "", "--strict-mcp-config"]
    t0 = time.time()
    if arm.startswith("A"):
        sink, tail = SINK_STDOUT, ""
    else:
        sink, tail = SINK_FILE.format(out=out), "\n写完文件就结束。"
    p = subprocess.run(cmd, input=PROMPT.format(situation=case["situation"], lib=lib,
                                                out=out, sink=sink, tail=tail),
                       cwd=ROOT, capture_output=True, text=True, timeout=1500, env=env)
    open(trace, "w").write(p.stdout)
    meta = {}
    for line in p.stdout.splitlines():
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if ev.get("type") == "result":
            meta = ev
    d = jparse(open(out).read()) if os.path.exists(out) else jparse(meta.get("result", ""))
    d = d or {}
    return dict(id=case["id"], arm=arm, mechanism=d.get("mechanism", ""),
                proposal=d.get("proposal", ""), conditions=d.get("conditions", []),
                probability=d.get("probability"), reasoning=d.get("reasoning", ""),
                turns=meta.get("num_turns"), secs=round(time.time() - t0, 1),
                cost=meta.get("total_cost_usd", 0))


def do_trap(case, ans):
    if case["outcome"] != "failed" or not ans.get("proposal"):
        return dict(id=case["id"], arm=ans["arm"], skip=True, cost=0)
    txt, cost = claude(TRAP_JUDGE.format(
        situation=case["situation"], trap=case["intervention"], why=case["root_cause"],
        proposal=ans["proposal"][:2000],
        conds="\n".join(f"- {c}" for c in ans.get("conditions", [])) or "（无）"))
    d = jparse(txt) or {}
    return dict(id=case["id"], arm=ans["arm"], skip=False,
                proposed_trap=bool(d.get("proposed_trap")),
                named_the_flaw=bool(d.get("named_the_flaw")), why=d.get("why", ""), cost=cost)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="runs/stage4")
    ap.add_argument("--arms", default="A,C")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    dbs = make_variants(a.out)
    cases = [c for f in sorted([f for f in glob.glob(os.path.join(ROOT, "heldout/*.json")) if "mech" not in f])
             for c in json.load(open(f))][:a.limit]
    arms = a.arms.split(",")
    fails = [c for c in cases if c["outcome"] == "failed"]
    print(f"held-out {len(cases)} 条（其中 {len(fails)} 条实际干预失败 = 陷阱题）× arm {arms}", flush=True)

    P = lambda n: os.path.join(a.out, n)
    jobs = [(lambda c=c, m=m: run_arm(c, m, dbs, a.out), dict(id=c["id"], arm=m))
            for c in cases for m in arms]
    answers = parallel(jobs, a.workers, P("answers.jsonl"), lambda r: (r["id"], r["arm"]), "arms")

    cmap = {c["id"]: c for c in cases}
    tj = [(lambda c=cmap[k[0]], v=v: do_trap(c, v), dict(id=k[0], arm=k[1]))
          for k, v in answers.items() if cmap[k[0]]["outcome"] == "failed"]
    parallel(tj, a.workers, P("trap.jsonl"), lambda r: (r["id"], r["arm"]), "trap")

    fj = [(lambda c=cmap[k[0]], v=v: do_f1(c, v), dict(id=k[0], arm=k[1])) for k, v in answers.items()]
    parallel(fj, a.workers, P("f1.jsonl"), lambda r: (r["id"], r["arm"]), "f1")

    import random
    rng = random.Random(11)
    lj = [(lambda c=cmap[i], x=x, y=y: do_lenient(c, answers[(i, x)], answers[(i, y)], rng),
           dict(id=i, pair=f"{x}v{y}"))
          for i in cmap for x, y in (("C", "A"),)
          if (i, x) in answers and (i, y) in answers]
    parallel(lj, a.workers, P("lenient.jsonl"), lambda r: (r["id"], r["pair"]), "lenient")
    subprocess.run([sys.executable, "-m", "pk.report4", "--out", a.out], cwd=ROOT)


if __name__ == "__main__":
    main()

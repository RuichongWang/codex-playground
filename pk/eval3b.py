# -*- coding: utf-8 -*-
"""阶段 3b：把库从「塞进 prompt 的材料」改成「agent 自己走的环境」。

四个 arm 拿到的工具完全一样（Bash + skill + CLI），差别只在指向哪个库、检索准不准：

  A 无库          连库存在这件事都不告诉它
  B 只有事件      库里只留 item，没有 pattern/条件/prescription（= case-based）
  C 全库          正常检索
  D 盲检索安慰剂  同一个全库、同样的工具、同样的工作量，但 search 返回与查询无关的真节点
                  —— 把「有库可查」和「查得准」分开

D 这个安慰剂跟静态版不同：静态版是喂错内容，这版是**查询不导航**。
因为一旦 agent 能自己查，喂错内容就不再可比了（它会重新查一遍）。
"""
import argparse, glob, json, os, subprocess, sys, time
import concurrent.futures as cf
from pk.eval3 import ROOT, jparse, do_f1, do_pair, parallel, load_done, append
from pk.store import Store

SKILL = os.path.join(ROOT, ".claude/skills/pattern-library/SKILL.md")

PROMPT = """下面是一个真实发生过的情况，以及当时有人提出的一个干预方案。

【情况】
{situation}

【提议的干预】
{intervention}
{lib}
请回答四件事：
1. 这件事的机制是什么 —— 为什么会发生，真正的驱动因素是什么
2. 这个干预会成功还是失败
3. **要判断这个干预成不成，需要先确认哪几件事** —— 只列真正决定成败的条件，
   不要把所有能想到的因素都列上；列一条没用的，比漏一条更糟
4. 成功概率，0 到 100 的整数

想清楚之后，把答案写进文件 {out}，格式：
{{"mechanism": "机制诊断", "verdict": "worked 或 failed",
  "conditions": ["决定成败的条件一", "条件二"], "probability": 数字,
  "reasoning": "你的推理，尤其是为什么判成功或失败"}}

写完文件就结束。"""

LIB_BLOCK = """
【你有一个跨行业的 pattern 库可以用】
它装着一群 agent 从各行各业真实事件里猜出来的假说、以及这些假说的适用条件。
**先读 {skill} 学会怎么用它**，然后自己去查 —— 库路径 {db}。

工作目录 {root}。库不一定覆盖你这个领域，查不到就说查不到，不要硬套。
"""


def run_arm(case, arm, dbs, outdir):
    out = f"{outdir}/ans_{case['id']}_{arm}.json"
    lib = "" if arm == "A" else LIB_BLOCK.format(skill=SKILL, db=dbs[arm], root=ROOT)
    env = dict(os.environ)
    if arm == "D":
        env["PK_BLIND_SEARCH"] = "1"
    cmd = ["claude", "-p", "--model", "claude-opus-5", "--output-format", "json"]
    if arm != "A":
        cmd += ["--allowed-tools", "Bash", "--permission-mode", "acceptEdits", "--add-dir", ROOT]
    else:
        cmd += ["--allowed-tools", "", "--strict-mcp-config"]
    t0 = time.time()
    p = subprocess.run(cmd, input=PROMPT.format(situation=case["situation"],
                                                intervention=case["intervention"], lib=lib, out=out),
                       cwd=ROOT, capture_output=True, text=True, timeout=1200, env=env)
    try:
        meta = json.loads(p.stdout)
    except Exception:
        meta = {}
    d = jparse(open(out).read()) if os.path.exists(out) else jparse(meta.get("result", ""))
    d = d or {}
    return dict(id=case["id"], arm=arm, mechanism=d.get("mechanism", ""),
                verdict=d.get("verdict", ""), conditions=d.get("conditions", []),
                probability=d.get("probability"), reasoning=d.get("reasoning", ""),
                turns=meta.get("num_turns"), secs=round(time.time() - t0, 1),
                cost=meta.get("total_cost_usd", 0))


def make_variants(outdir):
    """给 B 造一个只有事件的库副本。"""
    os.makedirs(outdir, exist_ok=True)
    full = os.path.join(ROOT, "runs/r3/library.json")
    items = os.path.join(outdir, "lib_items.json")
    if not os.path.exists(items):
        s = Store.load(full)
        s.nodes = {k: v for k, v in s.nodes.items() if v["kind"] == "item"}
        s.links = [l for l in s.links if l["src"] in s.nodes and l["dst"] in s.nodes]
        s.prescriptions = {}
        s.save(items)
    return {"B": items, "C": full, "D": full}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="runs/stage3b")
    ap.add_argument("--arms", default="A,B,C,D")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    dbs = make_variants(a.out)
    cases = [c for f in sorted(glob.glob(os.path.join(ROOT, "heldout/*.json")))
             for c in json.load(open(f))][:a.limit]
    arms = a.arms.split(",")
    print(f"held-out {len(cases)} 条 × arm {arms}（agentic：Bash + skill + CLI）", flush=True)

    P = lambda n: os.path.join(a.out, n)
    jobs = [(lambda c=c, m=m: run_arm(c, m, dbs, a.out), dict(id=c["id"], arm=m))
            for c in cases for m in arms]
    answers = parallel(jobs, a.workers, P("answers.jsonl"), lambda r: (r["id"], r["arm"]), "arms")

    cmap = {c["id"]: c for c in cases}
    fj = [(lambda c=cmap[k[0]], v=v: do_f1(c, v), dict(id=k[0], arm=k[1])) for k, v in answers.items()]
    parallel(fj, a.workers, P("f1.jsonl"), lambda r: (r["id"], r["arm"]), "f1")

    import random
    rng = random.Random(7)
    pj = [(lambda c=cmap[i], x=x, y=y: do_pair(c, answers[(i, x)], answers[(i, y)], rng),
           dict(id=i, pair=f"{x}v{y}"))
          for i in cmap for x, y in (("C", "D"), ("C", "B"))
          if (i, x) in answers and (i, y) in answers]
    parallel(pj, a.workers, P("pairs.jsonl"), lambda r: (r["id"], r["pair"]), "pairs")

    subprocess.run([sys.executable, "-m", "pk.report3", "--out", a.out], cwd=ROOT)


if __name__ == "__main__":
    main()

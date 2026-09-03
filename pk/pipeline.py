# -*- coding: utf-8 -*-
"""提议 fan-out + triage 归并的两段式写入。

    ① 提议：同一批的 N 个事件，N 个 agent 并行。每人只看自己那条 + 同一个**只读库快照**，
      **互相看不见彼此的提议** —— 独立性是这套系统全部可信度的来源，不能破。
    ② triage：一个 agent 拿到全部提议，**只做归并和映射，不许发明**。
      几个人说的是同一个假说就合成一个节点，把各自的 link 都挂上去，并记账。
      每个节点/边保留**提出者**作为 source，不记成 triage 自己。

批内并行（消掉顺序偏差），批间串行（保住「后来者独立撞上前人 pattern」这个最珍贵的信号）。

    python3 -m pk.pipeline --batch-size 5 --limit 30
"""
import argparse
import concurrent.futures as cf
import json
import os
import shutil
import subprocess
import time

from pk.assemble import build, load_props, verify
from pk.run import ROOT, load_corpus

PROPOSE = """你是 agent {aid}。你刚刚经历了下面这件事，要向一个跨行业的共享 pattern 库提交**写入建议**。
库里的 pattern 都是别的 agent 从他们自己遇到的事情里**猜**出来的假说，不是定论。

【你经历的事】
{what}
关键事实：{facts}
{iv}

【查库】只读快照，你只能查不能写。工作目录 {root}：
  python3 -m pk.cli --db {snap} search "<说法>"        换几种说法多查几次
  python3 -m pk.cli --db {snap} patterns --side phenomenon
  python3 -m pk.cli --db {snap} patterns --side solution
  python3 -m pk.cli --db {snap} conditions
  python3 -m pk.cli --db {snap} get <id> / neighbors <id> / prescriptions <现象id>
把多条命令用 && 串在一次 Bash 调用里，别一条一轮。

【产出】把你的建议写成 JSON 存到 {out}（用 heredoc 一次写完）：
{{
  "item": {{"what":"用你自己的话复述这件事", "facts":{{"k":"v"}},
            "intervention":"没有就 null", "outcome":"worked|failed|unknown"}},
  "patterns":  [{{"key":"pa","claim":"...","side":"phenomenon","order":1}},
                {{"key":"pb","claim":"...","side":"solution","order":1}}],
  "conditions":[{{"key":"ca","claim":"...","test":"别人怎么判断自己满不满足"}}],
  "links":     [{{"src":"ITEM","dst":"pa","why":"...","polarity":"+"}},
                {{"src":"ITEM","dst":"P3","why":"..."}},
                {{"src":"pa","dst":"P9","why":"我这个是它的特例"}},
                {{"src":"ITEM","dst":"P5","why":"反例：...","polarity":"-"}}],
  "prescriptions":[{{"phenomenon":"pa","conditions":["ca","C2"],"solution":"pb",
                     "outcome":"worked","note":"..."}}]
}}
`key` 是你给新建东西起的临时别名；库里已有的直接写真 id（P3/C2）；"ITEM" 指你这条事件。

【规则】
1. **先查库**，换不同说法多查几次 —— 别人的措辞不会跟你一样。
2. **能 link 多少 link 多少** —— 一件事可以同时是多个假说的证据。只有真相关才 link。
3. 明确**不成立**的打负 link（polarity "-"），那比正 link 更值钱。
4. **配额：最多新建 3 个 pattern。** 库里已经有很多假说了，先尽力复用真 id ——
   复用一条已有的比新建一条有价值得多，因为它给那条假说添了一个独立来源。
   实在要新建，先在心里排序，只提你最有把握、最可能被别的行业复用的那 3 个。
   宁可少提也不要凑数：一条只对你这件事成立的"假说"是负资产。
   条件同理，最多 3 条。
5. 猜了高阶 pattern（order 2+）就必须 link 回它抽象自的低阶 pattern，否则库是一堆扁平猜测。
6. 条件写成**可复用、能判断**的谓词，不要写成只描述你这一件事的话。每条必须有 test。
7. 条件是准入闸门，只写真正决定解法成不成的那几条，**能少则少**。
8. 你**看不到同批其他 agent 的建议，这是故意的** —— 你的判断必须独立产生。
   后面会有人把大家的建议放一起归并，你不用操心重复。

写完文件就结束，用一句话说明你提了什么。"""

TRIAGE = """你是 triage。下面是同一批 {n} 个 agent 各自**独立**提出的写入建议 —— 他们互相看不见对方，
也看不见对方新建的东西。你要判断这些建议里**哪些其实是同一个东西**。

【当前库】{root}，只读：
  python3 -m pk.cli --db {snap} patterns / conditions / search "..." / get <id>

【这批建议】在这些文件里，自己读（一次 Bash 调用里 cat 完）：
{props}

【你只做判断，不搬运文字】
你**不需要**、也**不允许**重写任何 claim / test / why。最终写入由代码按你的映射从原始提议里
原样搬运。你的产出只有一份很短的映射表。

三件事：
1. **归并**：几个 agent 提的新 pattern（或 condition）其实是**同一个假说的不同说法** → 归成一组，
   指定保留哪一个（用最早提出者的），其余的并进去。**这是你最重要的产出。**
   判据是「这两条说的是不是同一件事」，不是「像不像」。粒度不同、适用范围不同的，不要合。
2. **映射到已有**：某个 agent 提的新东西库里**已经有了**（他没查到）→ 指到那个真 id。
3. **同情境**：两个 agent 的**事件本身**本质上是同一个情境 → 标出来，后者只算又一次确认。
   不是同一个情境就别标。这批大概率一个都没有，没有就给空数组。

【产出】写到 {out}：
{{
  "merges": [{{"keep":"B1A1:pa", "drop":["B1A5:pc","B1A3:px"],
               "why":"同一个假说，一个从供应链说、一个从医疗说"}}],
  "map_to_existing": [{{"proposal":"B1A2:pb", "existing":"P17",
                        "why":"库里已有这条，他没查到"}}],
  "same_situation": [{{"item":"B1A4", "same_as":"B1A2", "why":"..."}}]
}}
key 一律写成 `<agent id>:<他给的 key>`。三个数组都可以为空。没有要归并的就 "merges": []。

写完文件就结束，用一段话说明：合并了哪几组、依据是什么，以及有没有谁提的东西其实库里已经有了。"""


def claude(prompt, timeout=900, model="claude-opus-5"):
    p = subprocess.run(
        ["claude", "-p", prompt, "--model", model, "--output-format", "json",
         "--allowed-tools", "Bash", "--permission-mode", "acceptEdits", "--add-dir", ROOT],
        cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"is_error": True, "result": (p.stdout or p.stderr)[:400], "total_cost_usd": 0}


def propose(ev, aid, snap, outdir):
    out = f"{outdir}/prop_{aid}.json"
    iv = f"你做的干预：{ev['intervention']}（结果：{ev.get('outcome','unknown')}）" if ev.get("intervention") else ""
    t0 = time.time()
    r = claude(PROPOSE.format(aid=aid, what=ev["what"], root=ROOT, snap=snap, out=out, iv=iv,
                              facts=json.dumps(ev.get("facts", {}), ensure_ascii=False)))
    ok = os.path.exists(out)
    return dict(aid=aid, file=ev["_file"], out=out, ok=ok, cost=r.get("total_cost_usd", 0),
                turns=r.get("num_turns"), secs=round(time.time() - t0, 1), result=r.get("result", "")[:400])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="corpus/*.json")
    ap.add_argument("--db", default="pk/library.json")
    ap.add_argument("--batch-size", type=int, default=5)
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--shuffle", type=int, default=7)
    ap.add_argument("--outdir", default="runs/v2")
    ap.add_argument("--base", default=None, help="以某个已有库为基线（第二轮用第一轮冻结的库）")
    ap.add_argument("--log", default="runs/v2/pipeline.jsonl")
    ap.add_argument("--reuse", action="store_true", help="已有 prop_*.json 就不重跑提议")
    ap.add_argument("--concurrency", type=int, default=10, help="同批内滚动并发上限")
    a = ap.parse_args()

    events = load_corpus(a.corpus, None if a.shuffle < 0 else a.shuffle)[:a.limit]
    if a.base and not os.path.exists(a.db):
        shutil.copy(a.base, a.db)
        print(f"以 {a.base} 为基线开跑")
    os.makedirs(a.outdir, exist_ok=True)
    batches = [events[i:i + a.batch_size] for i in range(0, len(events), a.batch_size)]
    print(f"{len(events)} 条 / {len(batches)} 批 × {a.batch_size}")
    total = 0.0

    for bi, batch in enumerate(batches, 1):
        snap = f"{a.outdir}/snap_b{bi}.json"
        shutil.copy(a.db, snap) if os.path.exists(a.db) else open(snap, "w").write('{"nodes":{},"links":[],"prescriptions":{},"counters":{}}')
        print(f"\n=== 批 {bi}/{len(batches)} — {len(batch)} 个 agent 并行提议（只读快照 {snap}）===")

        t0 = time.time()
        cached = [f"{a.outdir}/prop_B{bi}A{i+1}.json" for i in range(len(batch))]
        if a.reuse and all(os.path.exists(c) for c in cached):
            props = [dict(aid=f"B{bi}A{i+1}", file=batch[i]["_file"], out=c, ok=True,
                          cost=0, turns=0, secs=0, result="(复用)") for i, c in enumerate(cached)]
            print("  复用已有提议，跳过")
        else:
          with cf.ThreadPoolExecutor(max_workers=min(a.concurrency, len(batch))) as ex:
            futs = {ex.submit(propose, ev, f"B{bi}A{i+1}", snap, a.outdir): ev
                    for i, ev in enumerate(batch)}
            props = [f.result() for f in cf.as_completed(futs)]
        for p in sorted(props, key=lambda x: x["aid"]):
            total += p["cost"]
            print(f"  {p['aid']} {p['secs']}s ${p['cost']:.2f} turns={p['turns']} {'ok' if p['ok'] else 'NO FILE'}")
        print(f"  并行墙钟 {round(time.time()-t0,1)}s")

        good = [p for p in props if p["ok"]]
        if not good:
            print("  这批没有可用提议，跳过"); continue

        mmf = f"{a.outdir}/merge_b{bi}.json"
        blob = "\n".join(f"  {p['out']}   （{p['aid']} 提的）" for p in good)
        t0 = time.time()
        r = claude(TRIAGE.format(n=len(good), root=ROOT, snap=snap, out=mmf, props=blob), timeout=1200)
        total += r.get("total_cost_usd", 0)
        print(f"  triage {round(time.time()-t0,1)}s ${r.get('total_cost_usd',0):.2f} "
              f"turns={r.get('num_turns')} {'ok' if os.path.exists(mmf) else 'NO MAP'}")

        if os.path.exists(mmf):
            props = load_props([(p["aid"], p["out"]) for p in good])
            mm = json.load(open(mmf))
            spec = build(props, mm)
            bad = verify(props, spec)
            print(f"  归并 {len(mm.get('merges',[]))} 组 / 映射到已有 {len(mm.get('map_to_existing',[]))} 条"
                  f" / 同情境 {len(mm.get('same_situation',[]))} 条")
            if bad:
                print(f"  ⚠️ 断言失败：{len(bad)} 处文字不是提议原文 —— {bad[:2]}")
            else:
                print("  ✓ 断言通过：写入的每一句都是提议原文")
            plan = f"{a.outdir}/plan_b{bi}.json"
            json.dump(spec, open(plan, "w"), ensure_ascii=False, indent=1)
            w = subprocess.run(["python3", "-m", "pk.cli", "--db", a.db, "batch",
                                "--file", plan, "--source", f"TRIAGE{bi}"],
                               cwd=ROOT, capture_output=True, text=True)
            print("  写入：" + " / ".join(w.stdout.strip().split("\n")[-2:]) + (w.stderr[:200] if w.stderr else ""))

        open(a.log, "a").write(json.dumps(dict(batch=bi, props=props, triage=r.get("result", "")[:600],
                                               cost=total), ensure_ascii=False) + "\n")
        subprocess.run(["python3", "-m", "pk.cli", "--db", a.db, "stats"], cwd=ROOT)

    print(f"\n累计 ${total:.2f}")


if __name__ == "__main__":
    main()

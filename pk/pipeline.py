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
4. 鼓励猜新 pattern，粒度不确定就猜几个不同层级的。但**先确认库里没有意思相同的**；有就复用真 id。
5. 猜了高阶 pattern（order 2+）就必须 link 回它抽象自的低阶 pattern，否则库是一堆扁平猜测。
6. 条件写成**可复用、能判断**的谓词，不要写成只描述你这一件事的话。每条必须有 test。
7. 条件是准入闸门，只写真正决定解法成不成的那几条，**能少则少**。
8. 你**看不到同批其他 agent 的建议，这是故意的** —— 你的判断必须独立产生。
   后面会有人把大家的建议放一起归并，你不用操心重复。

写完文件就结束，用一句话说明你提了什么。"""

TRIAGE = """你是 triage。下面是同一批 {n} 个 agent 各自**独立**提出的写入建议 —— 他们互相看不见对方，
也看不见对方新建的东西。你的工作是把这些建议归并成一次干净的写入。

【当前库】{root}，只读：
  python3 -m pk.cli --db {snap} patterns / conditions / search "..." / get <id>

【这批建议】{props}

【你的唯一工作是归并，不是创作】
- 几个 agent 提的新 pattern（或 condition）其实是**同一个假说的不同说法** → 合成一个节点，
  把他们各自的 link 全挂到这一个节点上，并在 merges 里记账。**这是你最重要的产出**。
- 某个 agent 提的新东西其实库里**已经有了**（他没查到）→ 映射到已有真 id，记账。
- 其余原样保留。
- **你不能发明**新的 pattern / condition / link / prescription。一条都不行。
- 合并时**保留提出者作为 source**，不要记成你自己 —— 来源多样性是这个库可信度的唯一来源。
  合并后的节点用最早提出者的 id 作 source；每条 link 用它原提出者的 id。
- 两个 agent 描述的**事件本身**如果本质上是同一个情境，给后者的 link 加
  "novel": false, "same_as": "<前者的 item key>"。不是同一个情境就别加。

【产出】把最终写入写成 JSON 存到 {out}：
{{
  "items": [{{"key":"i_AG01","what":"...","facts":{{}},"intervention":null,
              "outcome":"worked|failed|unknown","source":"AG01"}}, ...],
  "patterns":  [{{"key":"pa","claim":"...","side":"phenomenon","order":1,"source":"AG01"}}, ...],
  "conditions":[{{"key":"ca","claim":"...","test":"...","source":"AG03"}}, ...],
  "links":     [{{"src":"i_AG01","dst":"pa","why":"...","polarity":"+","source":"AG01"}}, ...],
  "prescriptions":[{{"phenomenon":"pa","conditions":["ca"],"solution":"pb",
                     "item":"i_AG01","outcome":"worked","source":"AG01"}}, ...],
  "merges":[{{"into":"pa","merged":["AG01:pa","AG04:pc"],
              "why":"两人说的是同一个假说，只是一个从供应链说、一个从医疗说"}}, ...]
}}
每个 item 的 key 用 i_<agent id>，link 的 src 指向它。库里已有的节点直接写真 id。

写完文件就结束，用一段话说明：合并了哪几组、为什么，以及有没有谁提的东西其实库里已经有了。"""


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
    ap.add_argument("--log", default="runs/v2/pipeline.jsonl")
    a = ap.parse_args()

    events = load_corpus(a.corpus, None if a.shuffle < 0 else a.shuffle)[:a.limit]
    os.makedirs(a.outdir, exist_ok=True)
    batches = [events[i:i + a.batch_size] for i in range(0, len(events), a.batch_size)]
    print(f"{len(events)} 条 / {len(batches)} 批 × {a.batch_size}")
    total = 0.0

    for bi, batch in enumerate(batches, 1):
        snap = f"{a.outdir}/snap_b{bi}.json"
        shutil.copy(a.db, snap) if os.path.exists(a.db) else open(snap, "w").write('{"nodes":{},"links":[],"prescriptions":{},"counters":{}}')
        print(f"\n=== 批 {bi}/{len(batches)} — {len(batch)} 个 agent 并行提议（只读快照 {snap}）===")

        t0 = time.time()
        with cf.ThreadPoolExecutor(max_workers=len(batch)) as ex:
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

        plan = f"{a.outdir}/plan_b{bi}.json"
        blob = "\n\n".join(f"--- {p['aid']} 的建议 ---\n" + open(p["out"]).read() for p in good)
        t0 = time.time()
        r = claude(TRIAGE.format(n=len(good), root=ROOT, snap=snap, out=plan, props=blob), timeout=1200)
        total += r.get("total_cost_usd", 0)
        print(f"  triage {round(time.time()-t0,1)}s ${r.get('total_cost_usd',0):.2f} "
              f"turns={r.get('num_turns')} {'ok' if os.path.exists(plan) else 'NO PLAN'}")

        if os.path.exists(plan):
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

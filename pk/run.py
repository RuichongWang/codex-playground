# -*- coding: utf-8 -*-
"""阶段 1/2 的 runner：用 headless `claude -p` 把语料一条条喂给写入 agent。

agent 拿 Bash 自己跑 `python3 -m pk.cli ...` 查库、写库 —— 系统不替它预筛候选。

    python3 -m pk.run --limit 3 --dry      # 只打印 prompt，不调模型
    python3 -m pk.run --limit 20
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROMPT = """你是 agent {aid}。你刚刚经历了下面这件事，现在要把它写进一个跨行业的共享 pattern 库。
库里的 pattern 都是别的 agent 从他们自己遇到的事情里**猜**出来的假说，不是定论。

【你经历的事】
{what}
关键事实：{facts}
{iv}

【库怎么用】工作目录 {root}，所有命令都用 python3 -m pk.cli
查：
  search "<说法>"                      按文字找节点，**先用它，而且换几种说法多查几次**
  patterns --side phenomenon           列现象 pattern（按可信度排）
  patterns --side solution             列解法 pattern
  conditions                           列所有条件
  get <id>  /  neighbors <id>          看一个节点 / 看它的上下邻居和反驳
  prescriptions <现象id>               看这个现象下有哪些解法、各自要什么条件
写：
  add-item --what "..." --source {aid} --facts '{{"k":"v"}}' [--intervention "..." --outcome worked|failed]
  add-pattern --claim "..." --side phenomenon|solution --source {aid} [--order 2]
  add-condition --claim "..." --test "别人怎么判断自己满不满足" --source {aid}
  link --src <id> --dst <patternid> --why "..." --source {aid} [--polarity -] [--novel false --same-as <itemid>]
  prescribe --phenomenon <P> --conditions <C1,C2> --solution <S> --source {aid}
  apply --prescription <R> --item <I> --outcome worked|failed --source {aid}

【规则】
1. **先查库。** 换不同说法多查几次 —— 别人的措辞不会跟你一样。
2. 先 add-item 把你这件事写进去，拿到 item id，然后所有 link 都从这个 id 出发。
3. **必须给出 link，能 link 多少 link 多少** —— 一件事可以同时是多个假说的证据。
4. 只有真的相关才 link。明确**不成立**的打负 link（--polarity -），那比正 link 更值钱。
5. 鼓励猜新 pattern，粒度不确定就猜几个不同层级的。但**先确认库里没有意思相同的**；有就复用，别新建。
6. link 到某个 pattern 前，先 neighbors 看一眼已经挂在它下面的事件。如果你这件事跟其中某个
   **本质上是同一个情境**，就用 --novel false --same-as <那个事件id>；是新情境才默认 novel。
7. 条件要写成**可复用、能判断**的谓词（"两个节奏之间的东西可存储"），
   不要写成只描述你这一件事的话（"周末骨干只有一半"）。每个条件必须带 --test。
8. 有干预且知道结果时，prescribe 一条 (现象 + 条件集合) -> 解法，然后 apply 记录结果。

做完后用一段话说明：你复用了哪些已有的、新建了哪些、为什么这么判断。"""


def load_corpus(pattern):
    out = []
    for f in sorted(glob.glob(pattern)):
        try:
            rows = json.load(open(f))
        except Exception as e:
            print(f"  ! 跳过 {f}: {e}", file=sys.stderr)
            continue
        for r in rows:
            r["_file"] = os.path.basename(f)
            out.append(r)
    return out


def build(ev, aid):
    iv = ""
    if ev.get("intervention"):
        iv = f"你做的干预：{ev['intervention']}（结果：{ev.get('outcome','unknown')}）"
    return PROMPT.format(aid=aid, what=ev["what"], root=ROOT,
                         facts=json.dumps(ev.get("facts", {}), ensure_ascii=False), iv=iv)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="corpus/*.json")
    ap.add_argument("--db", default="pk/library.json")
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--log", default="runs/stage1.jsonl")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    events = load_corpus(a.corpus)[a.start:a.start + a.limit]
    print(f"语料 {len(events)} 条，模型 {a.model}，库 {a.db}")
    os.makedirs(os.path.dirname(a.log) or ".", exist_ok=True)
    env = dict(os.environ, PK_DB=a.db)
    cost = 0.0

    for i, ev in enumerate(events):
        aid = f"AG{a.start + i + 1:02d}"
        prompt = build(ev, aid)
        if a.dry:
            print("=" * 70 + f"\n{aid}  ({ev['_file']})\n" + prompt)
            continue
        t0 = time.time()
        p = subprocess.run(
            ["claude", "-p", prompt, "--model", a.model, "--output-format", "json",
             "--allowed-tools", "Bash", "--permission-mode", "acceptEdits",
             "--add-dir", ROOT],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=a.timeout)
        try:
            r = json.loads(p.stdout)
        except Exception:
            print(f"{aid} 解析失败: {p.stdout[:300]} {p.stderr[:300]}")
            continue
        cost += r.get("total_cost_usd", 0)
        rec = dict(aid=aid, file=ev["_file"], what=ev["what"][:60],
                   cost=r.get("total_cost_usd"), turns=r.get("num_turns"),
                   secs=round(time.time() - t0, 1), is_error=r.get("is_error"),
                   result=r.get("result", ""))
        open(a.log, "a").write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"{aid} {rec['secs']}s ${rec['cost']:.3f} turns={rec['turns']} "
              f"{'ERR' if rec['is_error'] else ''} — {ev['what'][:40]}…")

    if not a.dry:
        print(f"\n累计 ${cost:.2f}")
        subprocess.run([sys.executable, "-m", "pk.cli", "--db", a.db, "stats"], cwd=ROOT, env=env)


if __name__ == "__main__":
    main()

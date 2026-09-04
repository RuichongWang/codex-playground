# -*- coding: utf-8 -*-
"""阶段 3：迁移实验。四个 arm × 30 个 held-out 案例，加污染探针和两套判分。

  A 裸模型   B 只有 item（case-based）   C 全库   D 张冠李戴的库（活性安慰剂）

所有中间结果逐条落盘，可断点续跑。
"""
import argparse, glob, json, os, random, re, subprocess, sys, time
import concurrent.futures as cf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "runs/r3/library.json")


def claude(prompt, timeout=600, model="claude-opus-5", tools=None, cwd=None):
    """提示走 stdin，不走 argv —— argv 单参数上限 128KB，中文一字 3 字节，很容易撞。"""
    cmd = ["claude", "-p", "--model", model, "--output-format", "json"]
    if tools:
        cmd += ["--allowed-tools", tools, "--permission-mode", "acceptEdits", "--add-dir", ROOT]
    else:
        cmd += ["--allowed-tools", "", "--strict-mcp-config"]
    p = subprocess.run(cmd, input=prompt, cwd=cwd or ROOT,
                       capture_output=True, text=True, timeout=timeout)
    try:
        r = json.loads(p.stdout)
        return r.get("result", ""), r.get("total_cost_usd", 0)
    except Exception:
        return "", 0


def jparse(txt):
    m = re.search(r"\{.*\}", txt or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        try:
            return json.loads(re.sub(r",(\s*[}\]])", r"\1", m.group(0)))
        except Exception:
            return None


# ---------- 检索：C/B/D 都用同一套静态检索，保证可比 ----------
def load_lib():
    from pk.store import Store
    return Store.load(LIB)


def block_patterns(s, text, k=8):
    pats = s.search(text, kind="pattern", limit=k)
    if not pats:
        return ""
    out = ["【库里可能相关的做法与假说】"]
    for p in pats:
        c = s.credibility(p["id"])
        out.append(f"- [{'现象' if p['side']=='phenomenon' else '解法'}] {p['claim']}")
        out.append(f"    （{c['events']} 个独立事件支持，{c['refutes']} 条反驳）")
        for r in s.prescriptions.values():
            if r["solution"] not in s.nodes or any(c not in s.nodes for c in r["conditions"]):
                continue  # 悬空引用：跳过这条，不要让一处数据缺陷打掉整次运行
            if r["phenomenon"] == p["id"] and r["conditions"]:
                sc = s.prescription_score(r["id"])
                out.append(f"    · 若要用「{s.nodes[r['solution']]['claim'][:60]}」，前提是：")
                for cid in r["conditions"]:
                    out.append(f"        - {s.nodes[cid]['claim']}（怎么判断：{s.nodes[cid]['test'][:70]}）")
                out.append(f"      （试过 {sc['tried']} 次，成功 {sc['worked_events']} 个独立事件，失败 {sc['failed']}）")
                break
    return "\n".join(out)


def block_items(s, text, k=8):
    its = s.search(text, kind="item", limit=k)
    if not its:
        return ""
    out = ["【库里可能相关的历史案例】"]
    for i in its:
        out.append(f"- {i['what']}")
        if i.get("intervention"):
            out.append(f"    干预：{i['intervention']}（结果：{i.get('outcome','unknown')}）")
    return "\n".join(out)


ARM_PROMPT = """下面是一个真实发生过的情况，以及当时有人提出的一个干预方案。

【情况】
{situation}

【提议的干预】
{intervention}
{block}
请回答四件事：
1. 这件事的机制是什么 —— 为什么会发生，真正的驱动因素是什么
2. 这个干预会成功还是失败
3. **要判断这个干预成不成，需要先确认哪几件事** —— 只列真正决定成败的条件，
   不要把所有能想到的因素都列上；列一条没用的，比漏一条更糟
4. 成功概率，0 到 100 的整数

只输出 JSON，不要别的：
{{"mechanism": "机制诊断", "verdict": "worked 或 failed",
  "conditions": ["决定成败的条件一", "条件二"], "probability": 数字,
  "reasoning": "你的推理，尤其是为什么判成功或失败"}}"""

PROBE_PROMPT = """下面是一段对某个真实事件的描述。

{situation}

你认得出这具体是哪一起事件吗？如果认得，说出是什么（机构/项目/地点/时间），
并说出你记忆中它的**根本原因**是什么。不确定就明确说不确定，不要猜。

只输出 JSON：
{{"recognized": true 或 false, "guess": "你认为这是哪一起事件，认不出就填空字符串",
  "recalled_root_cause": "你记忆中的根因，认不出就填空字符串", "confidence": 0到100}}"""


def do_probe(case):
    txt, cost = claude(PROBE_PROMPT.format(situation=case["situation"]))
    d = jparse(txt) or {}
    return dict(id=case["id"], recognized=bool(d.get("recognized")), guess=d.get("guess", ""),
                recalled=d.get("recalled_root_cause", ""), conf=d.get("confidence", 0), cost=cost)


PROBE_JUDGE = """一个模型看了某事件的匿名描述后，猜它是哪一起事件，并回忆了根因。
判断它是不是真的认出来了。

【真实事件】{note}
【真实根因】{root}
【模型的猜测】{guess}
【模型回忆的根因】{recalled}

只输出 JSON：{{"identified": true 或 false, "root_cause_match": true 或 false, "why": "一句话"}}
identified = 猜测指向的确实是同一起事件。root_cause_match = 回忆的根因与真实根因实质一致。"""


def do_probe_judge(case, probe):
    if not probe["recognized"] and not probe["guess"]:
        return dict(id=case["id"], identified=False, root_cause_match=False, why="模型自述认不出", cost=0)
    txt, cost = claude(PROBE_JUDGE.format(note=case.get("source_note", ""), root=case["root_cause"],
                                          guess=probe["guess"], recalled=probe["recalled"]))
    d = jparse(txt) or {}
    return dict(id=case["id"], identified=bool(d.get("identified")),
                root_cause_match=bool(d.get("root_cause_match")), why=d.get("why", ""), cost=cost)


def do_arm(case, arm, s, cases):
    block = ""
    if arm == "A2":      # 裸模型的第二次独立运行 —— 用来量运行间方差
        arm_eff = "A"
    else:
        arm_eff = arm
    if arm_eff == "B":
        block = "\n" + block_items(s, case["situation"]) + "\n"
    elif arm_eff == "C":
        block = "\n" + block_patterns(s, case["situation"]) + "\n"
    elif arm_eff == "D":
        # 活性安慰剂：结构/篇幅/质量一致，但检索的是另一个案例的内容
        other = cases[(cases.index(case) + 15) % len(cases)]
        block = "\n" + block_patterns(s, other["situation"]) + "\n"
    txt, cost = claude(ARM_PROMPT.format(situation=case["situation"],
                                         intervention=case["intervention"], block=block))
    d = jparse(txt) or {}
    return dict(id=case["id"], arm=arm, mechanism=d.get("mechanism", ""),
                verdict=d.get("verdict", ""), conditions=d.get("conditions", []),
                probability=d.get("probability"), reasoning=d.get("reasoning", ""), cost=cost)


F1_JUDGE = """判断一份答案有没有说到某几个特定的要点。**只做匹配，不做质量评价。**

每个要点给了两种写法：`[领域]` 是它在这个案例自己的语言里的说法，
`[机制]` 是同一件事的领域中立说法。**任何一种被说到，就算命中** ——
用更抽象的话说对了同一件事，不该被判成没说到。

【情况】{situation}

【要检查的要点】
{checklist}

【被检查的答案里列出的条件】
{conds}

【被检查的答案的推理】
{reasoning}

对每个要点，判断这份答案有没有**实质上**说到它（措辞不必相同，意思到了就算）。
然后统计：答案列出的条件里，有多少条**不在**上面的要点清单里、也不是它们的合理细化。

只输出 JSON：
{{"hits": [要点编号数组，如 [1,3,4]], "extra_count": 不在清单上的条件条数, "why": "一句话"}}"""


def do_f1(case, ans):
    if not ans.get("conditions") and not ans.get("reasoning"):
        return dict(id=case["id"], arm=ans["arm"], hits=[], extra=0, n=len(case["conditions"]), cost=0)
    mech = _MECH.get(case["id"], [])
    cl = "\n".join(
        f"{i+1}. [领域] {c}" + (f"\n   [机制] {mech[i]}" if i < len(mech) and mech[i] else "")
        for i, c in enumerate(case["conditions"]))
    cd = "\n".join(f"- {c}" for c in ans.get("conditions", [])) or "（没列条件）"
    txt, cost = claude(F1_JUDGE.format(situation=case["situation"], checklist=cl, conds=cd,
                                       reasoning=(ans.get("reasoning") or "")[:1500]))
    d = jparse(txt) or {}
    hits = [h for h in (d.get("hits") or []) if isinstance(h, int) and 1 <= h <= len(case["conditions"])]
    return dict(id=case["id"], arm=ans["arm"], hits=sorted(set(hits)),
                extra=int(d.get("extra_count") or 0), n=len(case["conditions"]), cost=cost)


_MECH = {}
_mp = os.path.join(ROOT, "heldout/conditions_mech.json")
if os.path.exists(_mp):
    _MECH = json.load(open(_mp))


LENIENT_JUDGE = """两份答案回答了同一个问题。你能看到真实情况。判断哪份更准确地抓住了**真正决定成败的东西**。

【情况】{situation}
【真实根因】{root}
【真实采取的干预】{iv}（结果：{outcome}）
【真正决定成败的条件】
{conds}

--- 答案 X ---
{ax}

--- 答案 Y ---
{ay}

**先逐条对证据，再下判断** —— 不要凭长度、语气或术语密度打分。
一个用完全不同的话说对了同一件事的答案，跟用原话说的一样好。
一个说了很多但没碰到要害的答案，不算好。

只输出 JSON：
{{"x_caught": ["X 抓住的要点，逐条"], "x_missed": ["X 漏掉的要点"],
  "y_caught": [...], "y_missed": [...],
  "winner": "X" 或 "Y" 或 "tie", "why": "一句话，必须指向具体要点"}}"""


def do_lenient(case, a1, a2, rng):
    """宽松版：给 ground truth 的整体判分，配对盲判，强制引用证据。

    它跟逐元素判分的偏差方向相反（那个偏向用案例原话的，这个偏向更长更抽象的）。
    两个都报：指向一致则结论稳；不一致说明效应就落在测量自身的偏差带里。
    """
    flip = rng.random() < 0.5
    x, y = (a2, a1) if flip else (a1, a2)
    fmt = lambda a: (f"机制：{a.get('mechanism','')[:700]}\n"
                     f"方案/判断：{(a.get('proposal') or a.get('verdict') or '')[:500]}\n"
                     f"条件：{'; '.join(a.get('conditions') or [])[:900]}\n"
                     f"推理：{(a.get('reasoning') or '')[:900]}")
    txt, cost = claude(LENIENT_JUDGE.format(
        situation=case["situation"], root=case["root_cause"], iv=case["intervention"],
        outcome=case["outcome"],
        conds="\n".join(f"- {c}" for c in case["conditions"]),
        ax=fmt(x), ay=fmt(y)))
    d = jparse(txt) or {}
    w = d.get("winner", "tie")
    winner = "tie" if w not in ("X", "Y") else (
        (a2["arm"] if flip else a1["arm"]) if w == "X" else (a1["arm"] if flip else a2["arm"]))
    return dict(id=case["id"], pair=f"{a1['arm']}v{a2['arm']}", winner=winner,
                why=d.get("why", ""), cost=cost)


PAIR_JUDGE = """两份答案回答了同一个问题。判断哪份更接近真实情况。**你不知道它们来自哪里，也不该猜。**

【情况】{situation}
【提议的干预】{intervention}
【真实的根因】{root}
【干预的真实结果】{outcome}

--- 答案 X ---
机制：{mx}
推理：{rx}

--- 答案 Y ---
机制：{my}
推理：{ry}

只输出 JSON：{{"mechanism_winner": "X" 或 "Y" 或 "tie", "why": "一句话"}}
判据是哪份的机制诊断更接近真实根因，不是哪份写得更长或更漂亮。"""


def do_pair(case, a1, a2, rng):
    flip = rng.random() < 0.5
    x, y = (a2, a1) if flip else (a1, a2)
    txt, cost = claude(PAIR_JUDGE.format(
        situation=case["situation"], intervention=case["intervention"],
        root=case["root_cause"], outcome=case["outcome"],
        mx=x.get("mechanism", "")[:800], rx=(x.get("reasoning") or "")[:1200],
        my=y.get("mechanism", "")[:800], ry=(y.get("reasoning") or "")[:1200]))
    d = jparse(txt) or {}
    w = d.get("mechanism_winner", "tie")
    winner = "tie" if w not in ("X", "Y") else (
        (a2["arm"] if flip else a1["arm"]) if w == "X" else (a1["arm"] if flip else a2["arm"]))
    return dict(id=case["id"], pair=f"{a1['arm']}v{a2['arm']}", winner=winner,
                why=d.get("why", ""), cost=cost)


# ---------- 落盘 / 续跑 ----------
def load_done(path, keyfn):
    done = {}
    if os.path.exists(path):
        for line in open(path):
            try:
                r = json.loads(line)
                done[keyfn(r)] = r
            except Exception:
                pass
    return done


def append(path, rec):
    with open(path, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def parallel(jobs, workers, path, keyfn, label):
    done = load_done(path, keyfn)
    todo = [j for j in jobs if keyfn(j[1]) not in done]
    print(f"  {label}: 共 {len(jobs)}，已完成 {len(jobs)-len(todo)}，待跑 {len(todo)}", flush=True)
    t0 = time.time()
    if todo:
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(fn) for fn, _ in todo]
            for i, f in enumerate(cf.as_completed(futs), 1):
                try:
                    r = f.result()
                    append(path, r)
                    done[keyfn(r)] = r
                except Exception as e:
                    print(f"    ! {e}", flush=True)
                if i % 10 == 0:
                    print(f"    {i}/{len(todo)}  {round(time.time()-t0)}s", flush=True)
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="runs/stage3")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--arms", default="A,B,C,D")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    cases = []
    for f in sorted([f for f in glob.glob(os.path.join(ROOT, "heldout/*.json")) if "mech" not in f]):
        cases += json.load(open(f))
    cases = cases[:a.limit]
    s = load_lib()
    arms = a.arms.split(",")
    print(f"held-out {len(cases)} 条，arm {arms}，库 {len(s.nodes)} 节点", flush=True)

    P = lambda n: os.path.join(a.out, n)

    print("\n[1/5] 污染探针", flush=True)
    probes = parallel([(lambda c=c: do_probe(c), c) for c in cases],
                      a.workers, P("probe.jsonl"), lambda r: r["id"], "probe")
    pj = parallel([(lambda c=c: do_probe_judge(c, probes[c["id"]]), c) for c in cases if c["id"] in probes],
                  a.workers, P("probe_judge.jsonl"), lambda r: r["id"], "probe_judge")

    print("\n[2/5] 四个 arm", flush=True)
    jobs = [(lambda c=c, m=m: do_arm(c, m, s, cases), dict(id=c["id"], arm=m))
            for c in cases for m in arms]
    answers = parallel(jobs, a.workers, P("answers.jsonl"), lambda r: (r["id"], r["arm"]), "arms")

    print("\n[3/5] 条件 F1 判分", flush=True)
    cmap = {c["id"]: c for c in cases}
    ajobs = [(lambda c=cmap[k[0]], v=v: do_f1(c, v), dict(id=k[0], arm=k[1]))
             for k, v in answers.items()]
    f1s = parallel(ajobs, a.workers, P("f1.jsonl"), lambda r: (r["id"], r["arm"]), "f1")

    print("\n[4/5] 配对盲比 C vs D 和 C vs B", flush=True)
    rng = random.Random(7)
    pjobs = []
    for c in cases:
        for x, y in (("C", "D"), ("C", "B")):
            if (c["id"], x) in answers and (c["id"], y) in answers:
                pjobs.append((lambda c=c, x=x, y=y: do_pair(c, answers[(c["id"], x)], answers[(c["id"], y)], rng),
                              dict(id=c["id"], pair=f"{x}v{y}")))
    pairs = parallel(pjobs, a.workers, P("pairs.jsonl"), lambda r: (r["id"], r["pair"]), "pairs")

    print("\n[5/5] 汇总", flush=True)
    subprocess.run([sys.executable, "-m", "pk.report3", "--out", a.out], cwd=ROOT)


if __name__ == "__main__":
    main()

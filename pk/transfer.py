# -*- coding: utf-8 -*-
"""直接测跨域迁移：agent 到底引用了哪些库节点，那些节点的证据来自哪些行业。

陷阱规避是结果指标 —— 它说明 C 避开了坑，不说明是不是**靠跨域抽象**避开的。
而后者才是这个项目要的那一步。轨迹已经全量落盘，可以离线把它挖出来，不花钱。

  python -m pk.transfer                      # 原有输出，一个字没变
  python -m pk.transfer --shadow --out runs/slope    # 增量加：shadowing 三件套

**shadowing 分解**（预注册见 docs/experiment-plan.md §4.4）：库变大可能反而变差
（arXiv 2605.24050：skill 库 52→202，通过率掉 21%，其中 68% 来自选错 skill）。
所以每个规模点都要拆出三个数：

  (a) 命中率      = 最终答案里引用的节点数 ÷ 检索时触达的节点数。库变大而它掉 = 检索被稀释
  (b) 误导率      = 被引用的节点里「引用了反而扣分」的占比
  (c) 平均触达数  = 工作量本身。库变大它必然涨，涨太快说明 agent 在库里迷路

(b) 默认是**代理量**，不是因果判定：同题同模型下，这个 cell 的判分低于无库臂时，
这份答案引用的节点全部计入「误导嫌疑」。报告时必须按代理量报。
若另有逐节点的 judge 判定（`misled.jsonl`，每行 {id, model, lib, nodes:[...]}），以它为准。
"""
import argparse, glob, json, os, re
from collections import Counter, defaultdict
from pk.domain import item_domain
from pk.store import Store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = re.compile(r"\b([PCIR]\d{1,4})\b")


def cited_nodes(trace_path):
    """从轨迹里抽出被 agent 实际碰过的节点 id：CLI 查询的产出 + 它自己写的推理。"""
    ids = Counter()
    if not os.path.exists(trace_path):
        return ids
    for line in open(trace_path):
        try:
            ev = json.loads(line)
        except Exception:
            continue
        t = ev.get("type")
        blocks = []
        if t == "assistant":
            blocks = ev.get("message", {}).get("content", [])
        elif t == "user":
            c = ev.get("message", {}).get("content", [])
            blocks = c if isinstance(c, list) else []
        for b in blocks:
            if not isinstance(b, dict):
                continue
            txt = ""
            if b.get("type") == "text":
                txt = b.get("text", "")
            elif b.get("type") == "tool_result":
                cc = b.get("content")
                txt = cc if isinstance(cc, str) else json.dumps(cc, ensure_ascii=False)
            elif b.get("type") == "tool_use":
                txt = json.dumps(b.get("input", {}), ensure_ascii=False)
            for m in NODE.findall(txt or ""):
                ids[m] += 1
    return ids


# ---------- shadowing 分解（第四阶段 §4.4）----------
# 规模点 -> 该规模点用的库快照。节点 id 在三个快照之间是稳定的（后一轮在前一轮上长），
# 但仍然各自加载各自的快照：用 90 的库去判定 30 的轨迹，会把当时根本不存在的 id 算成命中。
SNAPSHOTS = {
    "30": "runs/r2/library_round1_frozen.json",
    "60": "runs/r3/library_round2_frozen.json",
    "90": "runs/r3/library.json",
}

_STORES = {}


def snapshot(lib):
    if lib not in _STORES:
        _STORES[lib] = Store.load(os.path.join(ROOT, SNAPSHOTS[lib]))
    return _STORES[lib]


def answer_nodes(rec, store):
    """一份答案的正文里引用到的、且确实存在于该快照里的节点 id。"""
    txt = " ".join(str(rec.get(k) or "") for k in ("mechanism", "proposal", "reasoning"))
    txt += " " + " ".join(str(c) for c in (rec.get("conditions") or []))
    return {m for m in NODE.findall(txt) if m in store.nodes}


def shadowing_rows(outdir, answers, scores, misled_override=None):
    """每个 (题, 模型, 规模点) 一行：触达数、引用数、命中率、误导嫌疑引用数。

    无库臂（lib="none"）不参与 —— 它没有库可触达，只作为 (b) 的判分基线。
    """
    rows = []
    for r in answers:
        lib = str(r.get("lib"))
        if lib not in SNAPSHOTS:
            continue
        st = snapshot(lib)
        tr = os.path.join(outdir, f"trace_{r['id']}_{r['model']}_{lib}.jsonl")
        touched = {i for i in cited_nodes(tr) if i in st.nodes}
        cited = answer_nodes(r, st)
        key = (r["id"], r["model"], lib)
        base = scores.get((r["id"], r["model"], "none"))
        here = scores.get(key)
        if misled_override is not None and key in misled_override:
            bad = {n for n in misled_override[key] if n in cited}
            verdict = "judged"
        elif base is None or here is None:
            bad, verdict = set(), "未判定"
        else:
            # 代理量：判分低于同题同模型的无库臂 ⇒ 这份答案引用的节点全部计为误导嫌疑
            bad = set(cited) if here < base else set()
            verdict = "proxy"
        rows.append(dict(id=r["id"], model=r["model"], lib=lib, touched=len(touched),
                         cited=len(cited & touched), cited_all=len(cited),
                         misled=len(bad), verdict=verdict))
    return rows


def shadowing_report(outdir, answers, scores, misled_override=None):
    rows = shadowing_rows(outdir, answers, scores, misled_override)
    if not rows:
        print("\n（没有可分析的 shadowing 数据：还没跑规模轴，或轨迹文件不在 --out 里）")
        return rows
    print("\n" + "=" * 78)
    print("shadowing 分解（预注册 §4.4）—— 斜率为负时必须用这三个数说明是不是 shadowing")
    print("=" * 78)
    undecided = sum(1 for r in rows if r["verdict"] == "未判定")
    if undecided:
        print(f"⚠️ {undecided}/{len(rows)} 行的 (b) 无法判定（缺无库臂判分基线），它们的误导率按 0 计入，"
              f"\n   也就是说下表的误导率是**下界**，不是估计值。")
    if any(r["verdict"] == "proxy" for r in rows):
        print("⚠️ (b) 是代理量：判分低于同题同模型无库臂 ⇒ 该答案引用的节点全部计为误导嫌疑。"
              "\n   它不是因果判定，报结果时必须原样说成代理量。")

    for model in sorted({r["model"] for r in rows}):
        print(f"\n模型 {model}")
        print(f"  {'规模':>6}{'案例':>6}{'(c)平均触达':>12}{'平均引用':>10}"
              f"{'(a)命中率':>11}{'(b)误导率':>11}")
        for lib in sorted({r["lib"] for r in rows if r["model"] == model}, key=int):
            g = [r for r in rows if r["model"] == model and r["lib"] == lib]
            t = sum(r["touched"] for r in g)
            c = sum(r["cited"] for r in g)
            m = sum(r["misled"] for r in g)
            ca = sum(r["cited_all"] for r in g)
            print(f"  {lib:>6}{len(g):>6}{t/len(g):>12.1f}{c/len(g):>10.1f}"
                  f"{(c/t if t else 0):>11.1%}{(m/ca if ca else 0):>11.1%}")
    print("\n判据：命中率随规模下降 + 误导率随规模上升 ⇒ shadowing；"
          "\n      三个数都平而斜率仍为负 ⇒ 不是 shadowing，是别的东西，如实说不知道是什么。")
    return rows


def _load_jsonl(path):
    out = []
    if os.path.exists(path):
        for line in open(path):
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def run_shadow(outdir):
    d = os.path.join(ROOT, outdir)
    answers = _load_jsonl(os.path.join(d, "answers.jsonl"))
    answers = [r for r in answers if r.get("model") and r.get("lib") is not None]
    scores = {(r["id"], r["model"], str(r["lib"])): r["score"]
              for r in _load_jsonl(os.path.join(d, "judge.jsonl")) if r.get("score") is not None}
    mis = {}
    for r in _load_jsonl(os.path.join(d, "misled.jsonl")):
        mis[(r["id"], r["model"], str(r["lib"]))] = r.get("nodes") or []
    rows = shadowing_report(d, answers, scores, mis or None)
    with open(os.path.join(d, "shadowing.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if rows:
        print(f"\n逐 cell 明细已写入 {os.path.join(outdir, 'shadowing.jsonl')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="runs/stage4")
    ap.add_argument("--lib", default="runs/r3/library.json")
    ap.add_argument("--arm", default="C")
    ap.add_argument("--shadow", action="store_true",
                    help="只跑 shadowing 分解（§4.4），读 --out 下规模轴的 answers/judge/轨迹")
    a = ap.parse_args()
    if a.shadow:
        run_shadow(a.out)
        return
    s = Store.load(os.path.join(ROOT, a.lib))
    cases = {c["id"]: c for f in sorted([f for f in glob.glob(os.path.join(ROOT, "heldout/*.json")) if "mech" not in f])
             if "mech" not in f for c in json.load(open(f))}
    ansf = os.path.join(ROOT, a.out, "answers.jsonl")
    ans = {}
    if os.path.exists(ansf):
        for l in open(ansf):
            try:
                r = json.loads(l); ans[(r["id"], r["arm"])] = r
            except Exception:
                pass

    print(f"=== 迁移分析（arm {a.arm}）===\n")
    rows = []
    for cid, c in cases.items():
        tr = os.path.join(ROOT, a.out, f"trace_{cid}_{a.arm}.jsonl")
        ids = cited_nodes(tr)
        touched = [i for i in ids if i in s.nodes]
        pats = [i for i in touched if s.nodes[i]["kind"] == "pattern"]
        # 每个被碰过的 pattern，它的证据落在哪些语料域
        doms = Counter()
        for p in pats:
            for it in s.grounding_items(p):
                doms[item_domain(s.nodes[it])] += 1
        hi = [p for p in pats if s.nodes[p].get("order", 1) >= 2]
        # 在最终推理里真正被引用的（不只是查询时扫过的）
        r = ans.get((cid, a.arm), {})
        final = set(NODE.findall((r.get("reasoning") or "") + (r.get("proposal") or "")))
        final = [x for x in final if x in s.nodes]
        rows.append(dict(id=cid, domain=c["domain"], touched=len(touched), pats=len(pats),
                         hi=len(hi), doms=len(doms), final=final))
    if not any(r["touched"] for r in rows):
        print("轨迹里没有节点引用（还没跑 agentic 臂？）"); return
    n = len([r for r in rows if r["touched"]])
    print(f"{'案例':22}{'碰过节点':>8}{'其中pattern':>11}{'阶2+':>7}{'覆盖语料域':>10}  最终推理里引用的")
    for r in rows:
        if not r["touched"]:
            continue
        print(f"{r['id']:22}{r['touched']:>8}{r['pats']:>11}{r['hi']:>7}{r['doms']:>10}  {','.join(r['final'][:6])}")
    print(f"\n有轨迹的案例 {n} 个")
    print(f"  平均碰过 {sum(r['touched'] for r in rows)/max(1,n):.1f} 个节点，"
          f"其中阶2+ 占 {sum(r['hi'] for r in rows)/max(1,sum(r['pats'] for r in rows) or 1):.0%}")
    print(f"  最终推理里明确引用了库节点的案例：{sum(1 for r in rows if r['final'])}/{n}")


if __name__ == "__main__":
    main()

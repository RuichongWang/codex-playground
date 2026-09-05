# -*- coding: utf-8 -*-
"""第四阶段：规模斜率实验的 runner —— 「模型 × 库规模」网格。

预注册在 `docs/experiment-plan.md` 的「第四阶段：规模斜率实验（预注册）」一节，
这个文件只负责把那一节**照着跑**，不做任何那一节没写死的选择。

    # 跑网格（12 个 cell × 30 题）
    python -m pk.slope --models haiku-4.5,sonnet-5,opus-5 --libs none,30,60,90 \\
                       --concurrency 6 --resume
    # 只补安慰剂（§4.5：只在最大规模点跑一次）
    python -m pk.slope --models opus-5 --libs 90blind --concurrency 4 --resume
    # 算斜率 + bootstrap CI + 翻转率（不花钱，纯离线）
    python -m pk.slope --report

为什么问「斜率」而不是「有库 vs 没库」：见 CLAUDE.md。一句话 ——
三个规模点面对的是同一批题、同一个天花板，天花板压低的是绝对值，不会凭空造出或抹掉斜率。

三件必须照做的事，每一件都有过血的教训：

1. **prompt 走 stdin，不走 argv。** argv 单参数上限 128KB，中文一字 3 字节，
   第 2 轮 triage 就是这么撞上 E2BIG 的。
2. **`is_error` 为真必须抛异常，绝不落盘。** 限流失败长得像成功
   （`subtype:"success"` / `num_turns:1` / `cost:0`），一旦被写成「已完成但没产出」，
   续跑看到有记录就永远跳过 —— 阶段 4 的「已完成 60 条」曾经掩盖着「59 条是废的」。
3. **题面和判分 rubric 冻结。** 见 CLAUDE.md 第四条硬规矩：题目已经改过三次，
   每次都在看到结果之后。这里的题面直接 import 阶段 4 的 `PROMPT`，一个字都不重写。
"""
import argparse, glob, json, math, os, random, subprocess, sys, time

from pk.eval3 import ROOT, claude, jparse, parallel
from pk.eval3b import LIB_BLOCK, SKILL
from pk.eval4 import PROMPT, SINK_FILE, SINK_STDOUT
from pk.store import Store

# 短名 -> CLI 的精确 model id。短名只是给命令行少打几个字，落盘一律用短名。
MODELS = {
    "haiku-4.5": "claude-haiku-4-5",
    "sonnet-5": "claude-sonnet-5",
    "opus-5": "claude-opus-5",
}

# 三个规模点，都是**已冻结的历史快照**，这一轮不重新生成任何库。
SNAPSHOTS = {
    "30": "runs/r2/library_round1_frozen.json",
    "60": "runs/r3/library_round2_frozen.json",
    "90": "runs/r3/library.json",
}

# 六个保留域（heldout/HELD_OUT_DOMAINS.md）。名字用 heldout/*.json 的文件名，
# 跟 pk/domain.py 从 corpus*/ 推出来的域名同一个命名空间。
HELD_OUT_DOMAINS = ["mining", "space", "justice", "culture", "marine", "defense"]

JUDGE_MODEL = "claude-opus-5"   # 判官固定，不随被试变 —— 否则模型轴和判分噪声混在一起
BOOTSTRAP_B = 2000              # 预注册 §4.1
FLIP_THRESHOLD = 0.10           # 预注册 §4.3


# ---------------------------------------------------------------- 库快照
def prepare_libs(outdir, libs):
    """给每个规模点准备一份 `--mask` 过保留域的副本。

    这六个域**本来就不该在库里**，所以这次屏蔽正常情况下删 0 个节点。
    那正是它的用处：它把「库没见过 held-out 域」从一句承诺变成一条**机器可验证的断言**，
    每次跑实验都重新验一遍。删掉了任何东西 = 库被污染过 = 整个实验作废，当场炸，
    不能让它带着污染跑完再来解释。
    """
    os.makedirs(outdir, exist_ok=True)
    dbs = {}
    for lib in libs:
        key = "90" if lib == "90blind" else lib
        if key == "none" or key in dbs:      # 90 和 90blind 共用同一份快照，只准备一次
            continue
        src = Store.load(os.path.join(ROOT, SNAPSHOTS[key]))
        pre_bad = src.check_integrity()
        masked, st = src.mask(HELD_OUT_DOMAINS)      # mask 内部已断言屏蔽后无悬空引用
        # 屏蔽掉的 prescription 里要扣掉「屏蔽之前就已经悬空」的那些：
        # 它们是快照自带的数据缺陷（见 R63），不是保留域的痕迹，不能拿来当污染报警。
        removed = (st["items"] + st["patterns"] + st["conditions"]
                   + st["prescriptions"] - st["prescriptions_dangling_before"])
        if removed:
            raise SystemExit(
                f"❌ 库 {key} 里有保留域的痕迹：屏蔽 {HELD_OUT_DOMAINS} 删掉了 {removed} 个节点"
                f"（事件{st['items']} pattern{st['patterns']} 条件{st['conditions']}）。\n"
                f"   库见过 held-out 域就再也不能假装没见过，这一轮的迁移结论全部作废。停。")
        path = os.path.join(outdir, f"lib_{key}.json")
        masked.save(path)
        bad = masked.check_integrity()
        if bad:
            raise SystemExit(f"❌ 库 {key} 屏蔽后有悬空引用：{bad[:5]}")
        n_item = sum(1 for n in masked.nodes.values() if n["kind"] == "item")
        print(f"  库 {key}: 事件 {n_item} / 节点 {len(masked.nodes)} / link {len(masked.links)}"
              f" / prescription {len(masked.prescriptions)}"
              f"  —— 保留域删 0 个节点 ✓（这个库确实没见过 held-out 域）", flush=True)
        if pre_bad:
            # 不自己改数据去迎合：如实报出来，让人看见这一轮是在带着哪些已知缺陷跑
            print(f"    ⚠️ 该快照本来就有 {len(pre_bad)} 条悬空引用（屏蔽时被顺手扫掉，"
                  f"所以这个规模点少了 {st['prescriptions_dangling_before']} 条 prescription）：",
                  flush=True)
            for b in pre_bad[:3]:
                print(f"       - {b[:100]}", flush=True)
        dbs[key] = path
    return dbs


# ---------------------------------------------------------------- 跑一个 cell
def run_cell(case, model, lib, dbs, outdir, timeout=1500):
    """一个 cell = (一道题, 一个模型, 一个规模点)。结果单独落一个文件。"""
    tag = f"{case['id']}_{model}_{lib}"
    out = os.path.join(outdir, f"ans_{tag}.json")
    trace = os.path.join(outdir, f"trace_{tag}.jsonl")
    cell_file = os.path.join(outdir, f"cell_{tag}.json")

    nolib = (lib == "none")
    db = dbs.get("90" if lib == "90blind" else lib)
    lib_block = "" if nolib else LIB_BLOCK.format(skill=SKILL, db=db, root=ROOT)

    env = dict(os.environ)
    env.pop("PK_BLIND_SEARCH", None)
    if lib == "90blind":
        env["PK_BLIND_SEARCH"] = "1"     # §4.5 盲检索安慰剂，只在最大规模点跑

    cmd = ["claude", "-p", "--model", MODELS[model],
           "--output-format", "stream-json", "--verbose", "--include-partial-messages"]
    if nolib:
        # 无库臂不给库工具（连库存在这件事都不告诉它），所以它也没法写文件 —— 直接吐 JSON。
        cmd += ["--allowed-tools", "", "--strict-mcp-config"]
        sink, tail = SINK_STDOUT, ""
    else:
        cmd += ["--allowed-tools", "Bash", "--permission-mode", "acceptEdits", "--add-dir", ROOT]
        sink, tail = SINK_FILE.format(out=out), "\n写完文件就结束。"

    prompt = PROMPT.format(situation=case["situation"], lib=lib_block,
                           out=out, sink=sink, tail=tail)
    t0 = time.time()
    # prompt 走 stdin：argv 单参数 128KB 上限，中文 3 字节/字符，很容易撞 E2BIG
    p = subprocess.run(cmd, input=prompt, cwd=ROOT,
                       capture_output=True, text=True, timeout=timeout, env=env)
    open(trace, "w").write(p.stdout)

    meta = {}
    for line in p.stdout.splitlines():
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if ev.get("type") == "result":
            meta = ev
    # 限流失败长得像成功。这里必须抛，不能落盘 —— 落了盘 resume 就永远跳过它。
    if meta.get("is_error"):
        raise RuntimeError(f"{tag}: is_error, {(meta.get('result') or '')[:120]}")
    if not meta:
        raise RuntimeError(f"{tag}: 轨迹里没有 result 事件（进程 rc={p.returncode}），不落盘")

    d = jparse(open(out).read()) if os.path.exists(out) else jparse(meta.get("result", ""))
    d = d or {}
    rec = dict(id=case["id"], model=model, lib=lib,
               mechanism=d.get("mechanism", ""), proposal=d.get("proposal", ""),
               conditions=d.get("conditions", []), probability=d.get("probability"),
               reasoning=d.get("reasoning", ""), parsed=bool(d),
               turns=meta.get("num_turns"), secs=round(time.time() - t0, 1),
               cost=meta.get("total_cost_usd", 0))
    json.dump(rec, open(cell_file, "w"), ensure_ascii=False, indent=1)
    return rec


# ---------------------------------------------------------------- 判分（冻结 rubric）
# 这段 rubric 是 docs/experiment-plan.md §4.2 的逐字实现。**跑之前冻结，跑完不许改。**
_DIMS = {
    "M1": ("M1 机制诊断",
           "2 = 指出了真实根因所在的那个变量/层位；"
           "1 = 方向对但停在表层症状；"
           "0 = 指错，或指向一个与真实根因无关的东西"),
    "M2": ("M2 干预选点",
           "2 = 提出的干预动的正是真正决定成败的那个变量；"
           "1 = 部分相关，但主动作动错了地方；"
           "0 = 无关；或走进了已知会失败的做法**且**没说出它为什么会失败"),
    "M3": ("M3 条件清单",
           "2 = 至少一条条件是从题面推不出来、需要案例之外的知识的，且正确；"
           "1 = 条件都正确但全是题面的复述；"
           "0 = 条件错、或空、或撒了一堆没用的（列一条没用的比漏一条更糟）"),
}

RUBRIC_JUDGE = """按下面这套**固定的** rubric 给一份答案打分。逐维独立打，不做整体印象评价。

【情况】{situation}
【真实根因】{root}
【真实采取的干预】{iv}（结果：{outcome}）
【真正决定成败的条件】
{conds}

--- 被评的答案 ---
机制：{mechanism}
方案：{proposal}
条件：{answer_conds}
推理：{reasoning}

【评分维度】
{rubric}

先逐维对证据再给分，不要凭长度、语气或术语密度打分。
用完全不同的话说对了同一件事，跟用原话说的一样好。

只输出 JSON：
{{"M1": 0或1或2, "M2": 0或1或2, "M3": 0或1或2, "why": "一句话，必须指向具体证据"}}"""


def do_judge(case, ans, rep=1):
    """单 judge、冻结 rubric、绝对打分（§4.2）。

    rep=2 是翻转率检查（§4.3）：同一套 rubric 判第二遍，只把三个维度的**呈现顺序**打乱。
    换的是呈现顺序而不是 rubric 本身 —— 换 rubric 量的就不是 judge 噪声了。
    """
    keys = list(_DIMS)
    if rep != 1:
        random.Random(hash((case["id"], ans["model"], ans["lib"], rep)) & 0xffff).shuffle(keys)
    rubric = "\n".join(f"- {_DIMS[k][0]}：{_DIMS[k][1]}" for k in keys)
    txt, cost = claude(RUBRIC_JUDGE.format(
        situation=case["situation"], root=case["root_cause"],
        iv=case["intervention"], outcome=case["outcome"],
        conds="\n".join(f"- {c}" for c in case["conditions"]),
        mechanism=(ans.get("mechanism") or "")[:1200],
        proposal=(ans.get("proposal") or "")[:1200],
        answer_conds="; ".join(ans.get("conditions") or [])[:1200],
        reasoning=(ans.get("reasoning") or "")[:1500],
        rubric=rubric), model=JUDGE_MODEL)
    d = jparse(txt) or {}
    g = lambda k: (int(d[k]) if isinstance(d.get(k), (int, float)) and 0 <= d[k] <= 2 else None)
    m1, m2, m3 = g("M1"), g("M2"), g("M3")
    score = None if None in (m1, m2, m3) else (m1 + m2 + m3)
    return dict(id=case["id"], model=ans["model"], lib=ans["lib"], rep=rep,
                M1=m1, M2=m2, M3=m3, score=score, why=d.get("why", ""), cost=cost)


# ---------------------------------------------------------------- 斜率 + bootstrap CI
def _ols(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    return (sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den) if den else 0.0


def slope_for(scores, model, libs, xform):
    """一个模型的斜率：把每道题在各规模点的得分对 x 做 OLS。

    三个点的 x 对所有题相同，所以「逐题拟合再平均」等于「先按题平均再拟合」——
    这里直接用后者，但**只用三个点都有分的题**，避免不等长的臂之间比均值
    （阶段 3 就栽在这上面）。
    """
    cases = [c for c in {k[0] for k in scores}
             if all((c, model, l) in scores for l in libs)]
    if len(cases) < 2:
        return None, []
    xs = [xform(l) for l in libs]
    ys = [sum(scores[(c, model, l)] for c in cases) / len(cases) for l in libs]
    return _ols(xs, ys), cases


def bootstrap_slope(scores, model, libs, xform, cases, b=BOOTSTRAP_B, seed=17):
    """按 held-out 题 resample（§4.1）。

    一道题在三个规模点上的得分**整组一起进出** —— 三个点共用同一批题，
    配对结构不能被打散，打散了 CI 就宽得没有意义。
    """
    rng = random.Random(seed)
    xs = [xform(l) for l in libs]
    out = []
    for _ in range(b):
        pick = [cases[rng.randrange(len(cases))] for _ in cases]
        ys = [sum(scores[(c, model, l)] for c in pick) / len(pick) for l in libs]
        out.append(_ols(xs, ys))
    out.sort()
    return out[int(0.025 * b)], out[int(0.975 * b) - 1]


def bootstrap_diff(scores, a_model, a_lib, b_model, b_lib, b=BOOTSTRAP_B, seed=23):
    """判据 (ii)：haiku+库90 减 opus 裸跑，配对 bootstrap 95% CI。"""
    cases = [c for c in {k[0] for k in scores}
             if (c, a_model, a_lib) in scores and (c, b_model, b_lib) in scores]
    if len(cases) < 2:
        return None, None, None, 0
    diff = [scores[(c, a_model, a_lib)] - scores[(c, b_model, b_lib)] for c in cases]
    point = sum(diff) / len(diff)
    rng = random.Random(seed)
    boot = sorted(sum(diff[rng.randrange(len(diff))] for _ in diff) / len(diff) for _ in range(b))
    return point, boot[int(0.025 * b)], boot[int(0.975 * b) - 1], len(cases)


def report(outdir):
    d = os.path.join(ROOT, outdir)
    rows = []
    jf = os.path.join(d, "judge.jsonl")
    if os.path.exists(jf):
        for line in open(jf):
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    if not rows:
        print("还没有判分结果（judge.jsonl 空）"); return

    p1 = {(r["id"], r["model"], str(r["lib"])): r["score"]
          for r in rows if r.get("rep", 1) == 1 and r.get("score") is not None}
    p2 = {(r["id"], r["model"], str(r["lib"])): r["score"]
          for r in rows if r.get("rep") == 2 and r.get("score") is not None}
    models = sorted({k[1] for k in p1})
    libs_all = sorted({k[2] for k in p1}, key=lambda x: (x != "none", x))

    print("=" * 78)
    print("第四阶段 规模斜率实验 —— 预注册见 docs/experiment-plan.md「第四阶段」")
    print("=" * 78)

    # ---- §4.3 翻转率：这一条先于所有结果解读 ----
    both = [k for k in p1 if k in p2]
    if both:
        flip = sum(1 for k in both if p1[k] != p2[k]) / len(both)
        mad = sum(abs(p1[k] - p2[k]) for k in both) / len(both)
        print(f"\njudge 翻转率（§4.3）：{flip:.1%}（n={len(both)}），平均绝对差 {mad:.2f}/6")
        if flip > FLIP_THRESHOLD:
            print(f"  ❌ 高于预注册阈值 {FLIP_THRESHOLD:.0%} ⇒ **判分噪声压过效应**。"
                  f"\n     下面所有斜率结论一律不成立，结论只能写「没测出来」，不能写「没效果」。")
        else:
            print(f"  ✓ 不高于预注册阈值 {FLIP_THRESHOLD:.0%}")
    else:
        print("\n⚠️ 没跑第二遍判分 —— §4.3 的翻转率检查缺失，无法区分「没效果」和「没测出来」。")

    # ---- 各 cell 均值（只在三点齐全的题上算，不比不等长的臂）----
    # 均值一律在**共同子集**上算：不等长的臂之间不能直接比均值 —— 阶段 3 就栽在这里
    # （C 有 3 题没吐概率、恰好都是难题，均值凭空好了 5 倍）。
    print(f"\n{'─'*78}\n主指标 = rubric 总分 / 6（§4.2）。均值只在该模型各臂共同有分的题上算")
    print(f"{'模型':>12}" + "".join(f"{l:>10}" for l in libs_all) + f"{'n题':>6}")
    common = {}
    for m in models:
        ls = [l for l in libs_all if any(k[1] == m and k[2] == l for k in p1)]
        cs = [c for c in {k[0] for k in p1} if all((c, m, l) in p1 for l in ls)]
        common[m] = (ls, cs)
        cells = []
        for l in libs_all:
            cells.append(f"{sum(p1[(c, m, l)] for c in cs)/len(cs)/6:>10.3f}"
                         if (l in ls and cs) else f"{'—':>10}")
        print(f"{m:>12}" + "".join(cells) + f"{len(cs):>6}")
    for m in models:
        ls, cs = common[m]
        miss = len({k[0] for k in p1 if k[1] == m}) - len(cs)
        if miss:
            print(f"  ⚠️ {m}：有 {miss} 道题不是所有臂都拿到分，已整题排除（不比不等长的臂）")

    # ---- §4.1 斜率 + bootstrap CI ----
    scale = [l for l in ("30", "60", "90") if l in libs_all]
    if len(scale) >= 3:
        print(f"\n{'─'*78}\n斜率（§4.1，主口径 x=log2(规模/30)；线性口径同报）")
        print(f"{'模型':>12}{'log2斜率':>12}{'95% CI':>22}{'线性斜率/10条':>15}{'n题':>6}  判定")
        for m in models:
            lg = lambda l: math.log2(int(l) / 30)
            s_log, cases = slope_for(p1, m, scale, lg)
            if s_log is None:
                print(f"{m:>12}{'—':>12}{'（三点不齐）':>22}"); continue
            lo, hi = bootstrap_slope(p1, m, scale, lg, cases)
            s_lin, _ = slope_for(p1, m, scale, lambda l: int(l) / 10.0)
            verdict = ("CI 跨 0 ⇒ 没测出斜率" if lo <= 0 <= hi
                       else ("正，CI 不跨 0" if lo > 0 else "负，CI 不跨 0 ⇒ 必须做 §4.4 shadowing 分解"))
            print(f"{m:>12}{s_log:>12.3f}{f'[{lo:+.3f}, {hi:+.3f}]':>22}"
                  f"{s_lin:>15.3f}{len(cases):>6}  {verdict}")
        print("\n  CI 跨 0 就是「没测出斜率」，点估计的符号不是证据（见 CLAUDE.md 报结果的规矩）。")
    else:
        print(f"\n⚠️ 只有 {len(scale)} 个规模点，做不出斜率 —— 两点连线没有残差，CI 无意义。")

    # ---- §4.8 判据 (ii)：库能不能替代模型规模 ----
    if "haiku-4.5" in models and "opus-5" in models and "90" in libs_all and "none" in libs_all:
        pt, lo, hi, n = bootstrap_diff(p1, "haiku-4.5", "90", "opus-5", "none")
        if pt is not None:
            ok = lo >= 0
            print(f"\n{'─'*78}\n判据 (ii) haiku+库90 − opus 裸跑（§4.8）："
                  f"{pt/6:+.3f}（分数比例），95% CI [{lo/6:+.3f}, {hi/6:+.3f}]，n={n}")
            print("  " + ("✓ 下界 ≥ 0 ⇒ 判据 (ii) 成立：库替代了一档模型规模"
                          if ok else "✗ 下界 < 0 ⇒ 判据 (ii) 不成立"))

    # ---- 安慰剂（§4.5，只在 90 这一个点）----
    if "90blind" in libs_all:
        print(f"\n{'─'*78}\n安慰剂（§4.5，只在最大规模点跑一次；它不是规模对照）")
        for m in models:
            a = [p1[k] for k in p1 if k[1] == m and k[2] == "90"]
            b = [p1[k] for k in p1 if k[1] == m and k[2] == "90blind"]
            if a and b:
                print(f"  {m:>12}  库90 {sum(a)/len(a)/6:.3f}  vs  盲检索 {sum(b)/len(b)/6:.3f}")

    cost = 0.0
    for f in ("answers.jsonl", "judge.jsonl"):
        fp = os.path.join(d, f)
        if os.path.exists(fp):
            for line in open(fp):
                try:
                    cost += json.loads(line).get("cost", 0) or 0
                except Exception:
                    pass
    print(f"\n累计 ${cost:.2f}")
    print("\n下一步：斜率为负时跑 `python -m pk.transfer --shadow --out "
          f"{outdir}` 出 §4.4 的三个数。")


# ---------------------------------------------------------------- main
def load_cases(limit):
    files = sorted(f for f in glob.glob(os.path.join(ROOT, "heldout/*.json")) if "mech" not in f)
    return [c for f in files for c in json.load(open(f))][:limit]


def main():
    ap = argparse.ArgumentParser(prog="pk.slope")
    ap.add_argument("--out", default="runs/slope")
    ap.add_argument("--models", default="haiku-4.5,sonnet-5,opus-5")
    ap.add_argument("--libs", default="none,30,60,90",
                    help="规模点，逗号分隔。none=无库臂；90blind=§4.5 的盲检索安慰剂")
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--resume", action="store_true",
                    help="接着已有结果跑，跳过已完成的 cell")
    ap.add_argument("--flip", action="store_true",
                    help="额外判第二遍（§4.3 翻转率检查）")
    ap.add_argument("--report", action="store_true", help="只出报告，不跑任何调用")
    a = ap.parse_args()

    outdir = os.path.join(ROOT, a.out)
    if a.report:
        report(a.out); return

    models = [m.strip() for m in a.models.split(",") if m.strip()]
    libs = [l.strip() for l in a.libs.split(",") if l.strip()]
    bad = [m for m in models if m not in MODELS] + \
          [l for l in libs if l not in ("none", "90blind") and l not in SNAPSHOTS]
    if bad:
        raise SystemExit(f"不认识的模型/规模点：{bad}；模型 {list(MODELS)}，规模 {['none'] + list(SNAPSHOTS) + ['90blind']}")
    if "90blind" in libs and "90" not in libs:
        print("⚠️ 跑了安慰剂但没跑库90，两者没法比 —— 安慰剂的唯一用途就是跟库90 对照。", flush=True)

    os.makedirs(outdir, exist_ok=True)
    P = lambda n: os.path.join(outdir, n)
    # --resume 是显式的：已经有结果还不加 --resume，多半是想重跑却会被静默跳过，
    # 或是想接着跑却先把旧结果混进来。宁可让它停下来问一句。
    if os.path.exists(P("answers.jsonl")) and not a.resume:
        raise SystemExit(f"{a.out} 里已经有结果了。要接着跑就加 --resume；要重跑先自己挪走。")

    cases = load_cases(a.limit)
    print(f"held-out {len(cases)} 题 × 模型 {models} × 规模 {libs} = "
          f"{len(cases)*len(models)*len(libs)} 个 cell", flush=True)
    dbs = prepare_libs(outdir, libs)

    jobs = [(lambda c=c, m=m, l=l: run_cell(c, m, l, dbs, outdir),
             dict(id=c["id"], model=m, lib=l))
            for c in cases for m in models for l in libs]
    answers = parallel(jobs, a.concurrency, P("answers.jsonl"),
                       lambda r: (r["id"], r["model"], str(r["lib"])), "cells")

    cmap = {c["id"]: c for c in cases}
    reps = [1, 2] if a.flip else [1]
    jj = [(lambda c=cmap[k[0]], v=v, rep=rep: do_judge(c, v, rep),
           dict(id=k[0], model=k[1], lib=k[2], rep=rep))
          for k, v in answers.items() for rep in reps if k[0] in cmap]
    parallel(jj, a.concurrency, P("judge.jsonl"),
             lambda r: (r["id"], r["model"], str(r["lib"]), r.get("rep", 1)), "judge")

    report(a.out)


if __name__ == "__main__":
    main()

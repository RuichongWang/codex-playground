"""M0 实验：层级下钻 vs 平铺 top-k，看命中率随库规模的斜率。

用法：
  python -m ph.eval --dry                    # 不调 API，跑通管线
  python -m ph.eval --tasks 12               # 真跑
  python -m ph.eval --tasks 12 --task-skin logs   # 顺手看一眼换表皮的迁移
"""
import argparse
import random
import sys

from ph import domain as D
from ph.judge import AnthropicJudge, MockJudge
from ph.retrieve import drill_down, flat_topk, lexical_top1


def sample_library(gt, size, rng, all_t):
    """库里必须含 ground truth 及其兄弟（confusable 的来源），其余随机填。"""
    lib = list(dict.fromkeys(D.siblings_of(gt)))
    pool = [t for t in all_t if t not in lib]
    rng.shuffle(pool)
    lib += pool[:max(0, size - len(lib))]
    return lib[:max(size, len(D.siblings_of(gt)))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=int, default=12)
    ap.add_argument("--sizes", type=int, nargs="+", default=[5, 25, 90])
    ap.add_argument("--lib-skin", default="orders")
    ap.add_argument("--task-skin", default=None, help="与 lib-skin 不同即为跨域迁移")
    ap.add_argument("--effort", default="low")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    task_skin = a.task_skin or a.lib_skin

    rng = random.Random(a.seed)
    judge = MockJudge() if a.dry else AnthropicJudge(effort=a.effort)
    all_t = D.all_templates()
    picked = rng.sample(all_t, a.tasks)

    print(f"库表皮={a.lib_skin} 任务表皮={task_skin} "
          f"{'（跨域迁移）' if task_skin != a.lib_skin else ''} judge={'mock' if a.dry else 'opus-5/' + a.effort}")
    hdr = f"{'库规模':>6} {'层级命中':>9} {'平铺命中':>9} {'字面命中':>9} {'层级输出对':>11} {'平铺输出对':>11} {'弃权':>5} {'tokens':>9}"
    print(hdr)
    print("-" * len(hdr))

    for size in a.sizes:
        h_hit = f_hit = l_hit = h_ok = f_ok = ab = 0
        t0 = judge.tokens
        for gt in picked:
            lib = sample_library(gt, size, random.Random(hash((a.seed, size, D.tid(gt))) & 0xffff), all_t)
            nodes = D.build_hierarchy(lib, a.lib_skin)
            rows = D.make_rows(random.Random(D.tid(gt)))
            task = D.describe_task(gt, task_skin, random.Random(a.seed))
            want = D.run(gt, rows)

            hp, _, st = drill_down(nodes, task, judge)
            fp, _ = flat_topk(nodes, task, judge)
            lp = lexical_top1(nodes, task)

            ab += st == "abstain"
            h_hit += hp == D.tid(gt)
            f_hit += fp == D.tid(gt)
            l_hit += lp == D.tid(gt)
            h_ok += bool(hp) and D.run(nodes[hp]["tpl"], rows) == want
            f_ok += bool(fp) and D.run(nodes[fp]["tpl"], rows) == want
        n = len(picked)
        print(f"{size:>6} {h_hit/n:>9.0%} {f_hit/n:>9.0%} {l_hit/n:>9.0%} "
              f"{h_ok/n:>11.0%} {f_ok/n:>11.0%} {ab:>5} {judge.tokens-t0:>9,}")

    print(f"\n共 {judge.calls} 次 judge 调用，{judge.tokens:,} tokens")
    print("看点：层级列随规模基本不掉、平铺列掉下去 → 命题成立。命中低但『输出对』高 = 检索与收益脱钩。")


if __name__ == "__main__":
    sys.exit(main())

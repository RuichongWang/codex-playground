# -*- coding: utf-8 -*-
"""按写入顺序重放一段库生长过程，最后做迁移查询。

不调 LLM —— agent 的判断在这里写成脚本，为的是让数据模型本身跑起来看得见。
真实系统里这些判断由 pk/agent.py 里的 agent 自己做。

没有 domain 标签。证据的单位是具体事件，独立性由 agent 在 link 时自报（novel=False 表示同情境）。
"""
from pk.store import Store, NEG


def build():
    s = Store()

    # ---- ① 一个具体事件，往上猜三个，粒度不同 ----
    i1 = s.add_item("周一早上急诊等待时间暴涨；周末只排了工作日一半骨干，积压全压到周一",
                    source="A", facts={"周期": "一周", "低产能窗口": "周末", "爆发点": "周一早"})
    p1 = s.add_pattern("周期性的低产能窗口会把负载推给下一个窗口", "phenomenon", "A")
    p2 = s.add_pattern("排班按人头平均，没按到达量分布", "phenomenon", "A")
    p3 = s.add_pattern("周末效应", "phenomenon", "A")
    for p in (p1, p2, p3):
        s.link(i1, p, "自己猜的", "A")

    # ---- ② 另一个事件，查库撞上 P1 -> link；再猜一个更贴自己的 ----
    i2 = s.add_item("门店周二备料不够；中央厨房周一晚一周一配，周二午市是配送后第一个高峰，备料按日均算",
                    source="B", facts={"补货周期": "一周", "消耗周期": "一天", "爆发点": "周二午市"})
    s.link(i2, p1, "一周一次的补货节奏把缺口推给了下一个窗口", "B")
    p4 = s.add_pattern("补货周期和消耗周期不同频，导致周期性缺口", "phenomenon", "B")
    s.link(i2, p4, "自己猜的", "B")

    # ---- ③ link P4，不 link P1（沾边但不是「窗口推负载」）；再猜 ----
    i3 = s.add_item("光伏出力傍晚快速下降，居民用电高峰恰在傍晚，备用机组爬坡跟不上",
                    source="C", facts={"供给周期": "一天", "需求周期": "一天", "错位": "相位"})
    s.link(i3, p4, "供给节奏和需求节奏不同频", "C")
    p8 = s.add_pattern("供给曲线和需求曲线的相位差，比总量缺口更致命", "phenomenon", "C")
    s.link(i3, p8, "自己猜的", "C")

    # ---- ④ 又一个事件 link P1 ----
    i4 = s.add_item("工单积压；二线专家只在工作日在岗，周末一线只能挂起，周一二线被淹",
                    source="D", facts={"周期": "一周", "低产能窗口": "周末", "爆发点": "周一"})
    s.link(i4, p1, "周末是低产能窗口，负载推给了周一", "D")

    # ---- ⑤ 往上猜二阶 pattern，支持者是 pattern 不是 item ----
    p20 = s.add_pattern("两个不同频的节奏耦合时，故障周期性出现在相位错开的那个点上",
                        "phenomenon", "E", order=2)
    s.link(p1, p20, "低产能窗口就是低频那一侧", "E")
    s.link(p4, p20, "补货频率 vs 消耗频率", "E")
    s.link(p8, p20, "相位差就是这个", "E")

    # ---- ⑥ 条件：一等公民，跟 pattern 一样被猜出来，必须带 test ----
    c_store = s.add_condition("两个节奏之间的东西可存储", "能不能先攒着、之后再用？人和实时服务不行", "C")
    c_cheap = s.add_condition("存取成本近似为零", "存进去再取出来，本身要不要花时间/人力？", "F")
    c_freq = s.add_condition("提高低频侧频率的边际成本低", "多排一个班 vs 多建一座电站", "A")
    c_sched = s.add_condition("需求侧可被调度", "能不能让需求方改时间？门诊可以，急诊不行", "A")

    # ---- ⑦ 解法 pattern ----
    s1 = s.add_pattern("提高低频那一侧的频率，让两个节奏对齐", "solution", "A")
    s2 = s.add_pattern("在两个节奏之间插入缓冲，把它们解耦", "solution", "C")
    s3 = s.add_pattern("把负载从相位错开的那个点挪走（错峰/预约）", "solution", "A")

    # ---- ⑧ prescription = (现象, 条件集合) -> 解法 ----
    r1 = s.prescribe(p20, [c_freq], s1, "A")
    r2 = s.prescribe(p20, [c_store, c_cheap], s2, "C")
    r3 = s.prescribe(p20, [c_sched], s3, "A")

    # ---- ⑨ 硬反馈：挂在具体事件上 ----
    s.record_application(r1, i1, "worked", "A", "周末排一部分骨干值班")
    s.record_application(r1, i2, "worked", "B", "一周一配改两配")
    s.record_application(r1, i4, "worked", "D", "二线周末轮值")
    s.record_application(r2, i3, "worked", "C", "加储能")

    # ---- ⑩ 照搬翻车：只看了高分，没查条件 ----
    i5 = s.add_item("拣货波次 vs 订单到达不同频；加了暂存缓冲区，结果更慢 —— 缓冲堆积让找货时间上升",
                    source="F", facts={"缓冲": "暂存区", "存取成本": "高"},
                    intervention="加暂存缓冲区", outcome="failed")
    s.link(i5, p20, "确实是节奏不同频", "F")
    s.record_application(r2, i5, "failed", "F", "满足可存储，但不满足存取成本≈0")
    s.link(i5, s2, "在存取有成本时，缓冲只是把延迟换了个形态", "F", polarity=NEG)
    # 失败的第一反应不是删 prescription，是补出缺失的条件 —— c_cheap 就是这么被发现的

    # ---- ⑪ 解法先于理解 ----
    i6 = s.add_item("两条产线换模时间错开半小时后，卡顿消失了；不知道为什么",
                    source="G", facts={"干预": "错开时间"},
                    intervention="错开换模时间", outcome="worked")
    s.link(i6, s3, "后来别人判断这就是错峰", "H")
    s.record_application(r3, i6, "worked", "H", "事后才归因")

    ids = dict(p1=p1, p3=p3, p20=p20, s2=s2, r2=r2,
               c_store=c_store, c_cheap=c_cheap, c_freq=c_freq, c_sched=c_sched)
    return s, ids


def spam(s, p1):
    """同一个情境再写两遍 —— 用来看刷分能不能刷动。"""
    for k, txt in enumerate([
            "周一早上急诊等待时间暴涨；周末骨干只排了一半，病人积压到周一",
            "周一急诊等待时间又暴涨了；周末排班只有平日一半，积压压到周一早"]):
        i = s.add_item(txt, source="A", facts={"周期": "一周", "低产能窗口": "周末", "爆发点": "周一早"})
        s.link(i, p1, "同一类情况", "A", novel=False, same_as="I1")


def report(s, ids):
    n = s.nodes
    print("=== 现象 pattern 排行（独立事件数 > 来源数 > link 数）===")
    for p in sorted([x for x in n.values() if x.get("side") == "phenomenon"],
                    key=lambda x: -s.score(x["id"])):
        c = s.credibility(p["id"])
        print(f"  {s.score(p['id']):>3}  {p['id']} (阶{p['order']})  {p['claim']}")
        print(f"       独立事件{c['events']}（落地 item {c['items']}）来源{c['sources']} "
              f"link{c['links']} 反驳{c['refutes']}")

    print(f"\n=== 矩阵：现象 {ids['p20']} 在不同条件下的解法 ===")
    for r in s.prescriptions_for(ids["p20"]):
        sc = s.prescription_score(r["id"])
        print("  [" + " ∧ ".join(n[c]["claim"] for c in r["conditions"]) + "]")
        print(f"     -> {n[r['solution']]['claim']}")
        print(f"        分{sc['score']} 试过{sc['tried']} 独立成功事件{sc['worked_events']} 失败{sc['failed']}")
        for w in sc["worked_on"]:
            print(f"          ✓ {w}…")

    print("\n=== 迁移：一个 agent 带着自己的条件来查 ===")
    print("  现象：某生长期作物总缺水，但全年总水量够 -> 匹配到 " + ids["p20"])
    mine = [ids["c_store"], ids["c_cheap"]]
    print("  我满足：" + "、".join(n[c]["claim"] for c in mine))
    for r in s.prescriptions_for(ids["p20"], satisfied=mine):
        print(f"  => {n[r['solution']]['claim']}   （修蓄水池）")

    print("\n=== 同一个现象，急诊来查 ===")
    print("  我满足：" + n[ids["c_freq"]]["claim"])
    print("  我不满足：人不可存储、急诊需求不可调度")
    for r in s.prescriptions_for(ids["p20"], satisfied=[ids["c_freq"]]):
        print(f"  => {n[r['solution']]['claim']}")

    p3 = n[ids["p3"]]
    print(f"\n=== 沉底 ===\n  {p3['id']}「{p3['claim']}」score={s.score(p3['id'])} —— 猜出来后没人 link")


if __name__ == "__main__":
    st, ids = build()
    report(st, ids)

    before = st.score(ids["p1"])
    c0 = st.credibility(ids["p1"])
    spam(st, ids["p1"])
    c1 = st.credibility(ids["p1"])
    print(f"\n=== 刷分测试：同一来源把同一个情境又写了 2 遍 ===")
    print(f"  {ids['p1']}  score {before} -> {st.score(ids['p1'])}"
          f"   独立事件 {c0['events']} -> {c1['events']}   link {c0['links']} -> {c1['links']}")
    print("  agent 自报 novel=False，所以 link 涨了独立事件数没涨 —— 按域或按 link 数算就被刷动了")

    st.save("pk/library.json")
    print(f"\n库：{len(st.nodes)} 节点 / {len(st.links)} link / {len(st.prescriptions)} prescription")

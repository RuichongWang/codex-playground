# -*- coding: utf-8 -*-
"""按写入顺序重放一段跨行业的库生长过程，最后做一次迁移查询。

不调 LLM —— 这里把 agent 的判断写成脚本，为的是让数据模型本身跑起来、看得见。
真实系统里这些判断由 pk/agent.py 里的 agent 自己做。
"""
from pk.store import Store, NEG


def build():
    s = Store()
    say = lambda *a: print(*a)

    # ---- ① 医院急诊：写 item，往上猜三个，粒度不同 ----
    i1 = s.add_item("周一早上急诊等待时间暴涨；周末只排了工作日一半骨干，积压全压到周一",
                    domain="医疗", source="A")
    p1 = s.add_pattern("周期性的低产能窗口会把负载推给下一个窗口", "phenomenon", "A", "医疗")
    p2 = s.add_pattern("排班按人头平均，没按到达量分布", "phenomenon", "A", "医疗")
    p3 = s.add_pattern("周末效应", "phenomenon", "A", "医疗")
    for p in (p1, p2, p3):
        s.link(i1, p, "自己猜的", "A", "医疗")

    # ---- ② 餐饮：查库，撞上 P1 -> link；再猜一个更贴自己的 ----
    i2 = s.add_item("门店周二备料不够；中央厨房周一晚一周一配，周二午市是配送后第一个高峰，备料按日均算",
                    domain="餐饮", source="B")
    s.link(i2, p1, "一周一次的补货节奏把缺口推给了下一个窗口", "B", "餐饮")
    p4 = s.add_pattern("补货周期和消耗周期不同频，导致周期性缺口", "phenomenon", "B", "餐饮")
    s.link(i2, p4, "自己猜的", "B", "餐饮")

    # ---- ③ 电网：link P4，不 link P1（沾边但不是「窗口推负载」）；再猜 ----
    i3 = s.add_item("光伏出力傍晚快速下降，居民用电高峰恰在傍晚，备用机组爬坡跟不上",
                    domain="电力", source="C")
    s.link(i3, p4, "供给节奏和需求节奏不同频", "C", "电力")
    p8 = s.add_pattern("供给曲线和需求曲线的相位差，比总量缺口更致命", "phenomenon", "C", "电力")
    s.link(i3, p8, "自己猜的", "C", "电力")

    # ---- ④ 客服：link P1 ----
    i4 = s.add_item("工单积压；二线专家只在工作日在岗，周末一线只能挂起，周一二线被淹",
                    domain="客服", source="D")
    s.link(i4, p1, "周末是低产能窗口，负载推给了周一", "D", "客服")

    # ---- ⑤ 有人往上猜二阶 pattern，证据是 pattern 不是 item ----
    p20 = s.add_pattern("两个不同频的节奏耦合时，故障周期性出现在相位错开的那个点上",
                        "phenomenon", "E", order=2)
    s.link(p1, p20, "低产能窗口就是低频那一侧", "E", "医疗")
    s.link(p4, p20, "补货频率 vs 消耗频率", "E", "餐饮")
    s.link(p8, p20, "相位差就是这个", "E", "电力")

    # ---- ⑥ 条件：一等公民，跟 pattern 一样被猜出来 ----
    c_store = s.add_condition("两个节奏之间的东西可存储", "能不能先攒着、之后再用？人和实时服务不行", "C", "电力")
    c_cheap = s.add_condition("存取成本近似为零", "存进去再取出来，本身要不要花时间/人力？", "F", "电商仓储")
    c_freq = s.add_condition("提高低频侧频率的边际成本低", "多排一个班 vs 多建一座电站", "A", "医疗")
    c_sched = s.add_condition("需求侧可被调度", "能不能让需求方改时间？门诊可以，急诊不行", "A", "医疗")

    # ---- ⑦ 解法 pattern ----
    s1 = s.add_pattern("提高低频那一侧的频率，让两个节奏对齐", "solution", "A")
    s2 = s.add_pattern("在两个节奏之间插入缓冲，把它们解耦", "solution", "C")
    s3 = s.add_pattern("把负载从相位错开的那个点挪走（错峰/预约）", "solution", "A")

    # ---- ⑧ prescription = TRIZ 矩阵格子：(现象, 条件集合) -> 解法 ----
    r1 = s.prescribe(p20, [c_freq], s1, "A")
    r2 = s.prescribe(p20, [c_store, c_cheap], s2, "C")
    r3 = s.prescribe(p20, [c_sched], s3, "A")

    # ---- ⑨ 硬反馈：各域实际套用之后的结果 ----
    s.record_application(r1, i1, "worked", "A", "医疗", "周末排一部分骨干值班")
    s.record_application(r1, i2, "worked", "B", "餐饮", "一周一配改两配")
    s.record_application(r1, i4, "worked", "D", "客服", "二线周末轮值")
    s.record_application(r2, i3, "worked", "C", "电力", "加储能")

    # ---- ⑩ 照搬翻车：只看了 P20 和 S2 的高分，没查条件 ----
    i5 = s.add_item("拣货波次 vs 订单到达不同频；加了暂存缓冲区，结果更慢 —— 缓冲堆积让找货时间上升",
                    domain="电商仓储", source="F", intervention="加暂存缓冲区", outcome="failed")
    s.link(i5, p20, "确实是节奏不同频", "F", "电商仓储")
    s.record_application(r2, i5, "failed", "F", "电商仓储", "满足可存储，但不满足存取成本≈0")
    s.link(i5, s2, "在存取有成本时，缓冲只是把延迟换了个形态", "F", "电商仓储", polarity=NEG)
    # 失败的第一反应不是删掉 prescription，是补出缺失的条件 —— c_cheap 就是这么被补上的

    # ---- ⑪ 解法先于理解：只知道好了，不知道为什么 ----
    i6 = s.add_item("两条产线换模时间错开半小时后，卡顿消失了；不知道为什么",
                    domain="制造", source="G", intervention="错开换模时间", outcome="worked")
    s.link(i6, s3, "后来别人判断这就是错峰", "H", "制造")
    s.record_application(r3, i6, "worked", "H", "制造", "事后才归因")

    return s, dict(p1=p1, p3=p3, p20=p20, s1=s1, s2=s2, s3=s3,
                   c_store=c_store, c_cheap=c_cheap, c_freq=c_freq, c_sched=c_sched)


def report(s, ids):
    n = s.nodes
    print("\n=== 现象 pattern 排行（域多样性 > 来源多样性 > link 数）===")
    for p in sorted([x for x in n.values() if x.get("side") == "phenomenon"],
                    key=lambda x: -s.score(x["id"])):
        c = s.credibility(p["id"])
        print(f"  {s.score(p['id']):>3}  {p['id']} (阶{p['order']})  {p['claim']}")
        print(f"       域{c['domains']} 来源{c['sources']} link{c['links']} 反驳{c['refutes']}")

    print(f"\n=== 矩阵：现象 {ids['p20']} 在不同条件下的解法 ===")
    for r in s.prescriptions_for(ids["p20"]):
        sc = s.prescription_score(r["id"])
        conds = " ∧ ".join(n[c]["claim"] for c in r["conditions"])
        print(f"  [{conds}]")
        print(f"     -> {n[r['solution']]['claim']}")
        print(f"        试过{sc['tried']} 成功域{sc['domains']} 失败{sc['failed']}")

    print("\n=== 迁移：农业灌溉 agent 带着自己的条件来查 ===")
    print(f"  现象：某生长期总缺水，但全年总水量够 -> 匹配到 {ids['p20']}")
    mine = [ids["c_store"], ids["c_cheap"]]
    print("  我满足：" + "、".join(n[c]["claim"] for c in mine))
    for r in s.prescriptions_for(ids["p20"], satisfied=mine):
        print(f"  => {n[r['solution']]['claim']}   （修蓄水池）")

    print("\n=== 同一个现象，急诊来查（条件不同）===")
    mine = [ids["c_freq"]]
    print("  我满足：" + "、".join(n[c]["claim"] for c in mine))
    print("  我不满足：人不可存储、急诊需求不可调度")
    for r in s.prescriptions_for(ids["p20"], satisfied=mine):
        print(f"  => {n[r['solution']]['claim']}")

    print("\n=== 沉底 ===")
    p3 = n[ids["p3"]]
    print(f"  {p3['id']} 「{p3['claim']}」 score={s.score(p3['id'])} —— 猜出来之后没人 link，自然沉底")


if __name__ == "__main__":
    st, ids = build()
    report(st, ids)
    st.save("pk/library.json")
    print(f"\n库：{len(st.nodes)} 节点 / {len(st.links)} link / {len(st.prescriptions)} prescription -> pk/library.json")

# Pattern Hierarchy — 设计文档

状态：草稿 v0.1，仅设计，未写代码。

## 0. 一句话

让 agent 把具体经历压成 pattern、把 pattern 再压成更抽象的 pattern；遇到新问题时**沿着这个层级走下来**拿到可执行动作，而不是把库向量化后 top-k 捞一把。整个过程跑在一个有可验证反馈的闭环里，靠执行结果自我生长。

## 1. 要验证的两个命题

### H1 —— 层级下钻 > 平铺检索（机制命题）

在**语义相近**的候选之间，"沿层级下钻 + 每步做判别式提问"的适用性命中率显著高于 flat top-k，且优势随库规模增长而扩大。

零假设：层级只是给 flat 检索换了个包装，在 confusable 候选上一样崩。

为什么值得赌 —— 现有实证数据指出崩的位置是**辨析**而不是召回：

- skill pool 5 → 100，真正用对的 skill 的 precision 从 29.6% 崩到 3.3%
- confusable pool 上 top-1 从 70.5% 掉到 53.4%；而随机干扰项下只从 97.7% 掉到 84.1%

LATTICE 已经在**文档检索**上证明了"LLM 走层级 > embedding top-k"（BRIGHT 上 46.7 nDCG@10，比最强单体 baseline 高 4.5 分）。本实验真正要问的是：这套搬到**过程性知识**上还成立吗？

这是本项目的核心 novelty claim：文档检索问的是"哪篇最相关"，pattern 检索问的是"哪套做法**适用**"。适用性与语义相似度的相关性比相关性与相似度弱得多，所以层级在这里的理论收益应当**更大**，不是更小。

### H2 —— 高层抽象可跨域迁移（价值命题）

在域 A 上长出的高层节点，能在没见过的域 B 上被下钻命中并产出可用的具体动作；且节点越抽象，迁移率越高。

可测形式：把层级按抽象层分层，测每层节点在 B 域"命中且有用"的比例，画 **abstraction-level × transfer-rate** 曲线。**这条曲线单调上升，就是本实验最想要的那张图。**

阴性结果同样有价值：曲线若是平的，说明"高层抽象可迁移"这个被普遍默认的前提本身站不住，这个结论值得单独写。

## 2. 数据结构

最小可用集合：一种主边 + 三种附属边。不要一上来就照搬 HiSkill 的五类边（decomposition / temporal / compatibility / support / recovery）——那是验证完机制之后才需要的复杂度。

### PatternNode

| 字段 | 说明 |
|---|---|
| `id` | |
| `level` | int，0 = 具体轨迹摘要，越大越抽象 |
| `name` | 一行 |
| `applicability` | 触发条件，**写成判别式问句 + 判据**，不是一段描述（见 §3.3，这是下钻能走起来的关键） |
| `procedure` | 有序步骤；level 越高越是骨架，越低越可直接执行 |
| `discriminator` | 一句话说清自己和**兄弟节点**的区别 |
| `evidence` | 来源 trajectory ids + 覆盖条数 |
| `stats` | `{invoked, succeeded, failed, misapplied}` |
| `cost` | 描述长度（token 数），供 §3.2 的 MDL 目标使用 |

### Edges

- `SPECIALIZES` (child → parent) — 主干。构成 **DAG 而非树**：一个 pattern 可以有多个父。
- `RECOVERS_FROM` (pattern → failure signature) — 由失败轨迹长出。
- `CONFLICTS_WITH` (兄弟消歧对) — 显式记录"我曾把这两个搞混"，是 H1 的弹药。
- `COMPOSES_WITH`

### 存储

SQLite 两张表（nodes / edges）。**不上图数据库。** 目前需要的查询只有"取某节点的子节点"和"取一条路径"，递归 CTE 足够；边类型稳定之后再谈迁移到图库。

## 3. 三个环

### 3.1 归纳 Induction：trajectory → level-0/1 pattern

输入**必须带 outcome 标注**（成功 / 失败 / 部分成功）。依据：带标注 vs 不带标注建出的 skill，收益 0.7462 vs 0.4000。

失败轨迹不丢弃 —— 它们长成 `RECOVERS_FROM` 边和 `applicability` 里的负向条款。层级里最贵的信息是"这个 pattern 在什么情况下**不**适用"。

### 3.2 抬升 Lifting：pattern → 更抽象 pattern

**必须有目标函数，否则 LLM 会造出一堆听起来深刻但没用的层级。** 这是本设计里最容易被偷懒跳过、也最不能跳过的一步。

借 DreamCoder / LILO 的 MDL 思路：候选父节点 `P` 值不值得留下，看

```
gain(P) = Σ_{c ∈ covered} len(c)  −  [ len(P) + Σ_{c ∈ covered} len(c | P) ]
```

即"把子节点改写成『P + 差异』之后，语料的总描述长度降了多少"。只保留 `gain > 阈值` 的抽象。

LILO 的原始做法是 Stitch 做符号压缩找最优 lambda 抽象、再让 LLM 自动命名写 docstring。我们没有 lambda 演算可压，用 token 数作代理，并用"覆盖的 trajectory 条数"作第二道筛子。这条是 hierarchy 不退化成 summarizer 的唯一保险。

抬升是**离线的 sleep phase**，不在任务执行的关键路径上。

### 3.3 下钻 Drill-down：query → path → 可执行动作

H1 的主体。算法（改编自 LATTICE 的 best-first + 校准）：

1. 从根开始，取当前节点的子节点集合
2. 给 LLM 一个 **listwise** slate（约 10 个候选），附上每个候选的 `discriminator`
3. **关键改动**：不问"哪个最相似"，而是问 —— *"要在这些候选之间做选择，我需要先确认关于当前任务的哪一件事？"* → 得到一个判别问题 → 用当前任务状态回答 → 据此打分。这是"走路径 = 消歧"这个立场的具体落地，也是与纯 LATTICE 的差异点。
4. 分数沿路径做 EMA 聚合：`p(v) = α·p(parent) + (1−α)·s_v`，α ≈ 0.5（深层权重更大，因为深层比较的是更细的判据）
5. 维护 frontier（beam）而非贪心单路，允许回溯
6. **必须有 abstain 出口**：下钻可以输出"库里没有适用的 pattern"。见 §6 第二条。
7. 到达 level-0/1 叶子 → 输出 procedure → 执行 → outcome 回灌 §3.1

闭环在这里合上：下钻结果被执行、被打分，分数回到 `node.stats`，失败长出新的 `CONFLICTS_WITH` / `RECOVERS_FROM` 边。

## 4. 域的选择（TBD，给出判据）

必须满足的四条：

1. **可验证的 outcome** —— 不能靠 LLM-as-judge。否则闭环的反馈信号是噪音，MDL 目标和 stats 一起塌掉。
2. **成对的相关域** —— H2 需要两个"底层机制不同、高层套路相同"的域。
3. **天然产生 confusable pattern** —— 否则 H1 没有靶子；域里必须真的存在"看起来很像、做法不同"的任务。
4. **单次 rollout 便宜** —— 层级要长出来需要几百到几千条轨迹。

候选与取舍：

| 选项 | 优点 | 缺点 |
|---|---|---|
| ALFWorld / WebShop / ScienceWorld 三件套 | 现成、闭环、奖励可验证；SkillRise 等工作用同一组测 cross-task，有 baseline 可比 | 三者跨域差异过大，H2 容易退化成"迁移不了"的平凡结论；且没有 ground-truth 层级，验不了 H1 的中间过程 |
| 自造合成域（两个表皮不同、深层同构的域） | 唯一能提供 ground-truth 层级、能人工构造 confusable 对；还能把"同构程度"当自变量来扫 | 说服力弱，容易被判为 toy |
| 真实 coding agent 轨迹 | 最有实用价值 | 脏、贵、无 ground truth，只能看端到端成功率 |

**推荐组合：H1 在合成域上做**（要 ground truth 和可控的 confusability），**H2 在真实域对上做**（要说服力）。两个命题不必共用一个域 —— 硬凑会两头不讨好。

## 5. Baselines 与指标

### H1

Baselines：
- B0 随机
- B1 flat embedding top-k
- B2 flat + LLM rerank（sliding window）
- B3 全库塞进 context（小库时的上界）

主指标：confusable set 上的 top-1 **适用性**命中率，随库规模 5 → 25 → 100 → 500 的曲线（直接对抗那条 29.6% → 3.3%）。

副指标：
- token 消耗（层级方案应当更省）
- **misapplication 率** —— skill 方案被误用/忽略的比例是 10.0%，原始执行只有 0.8%。层级方案必须自证没有把这个数字做得更差。

⚠️ **必须做同 token 预算的对照。** LATTICE 的结果显示，低预算时 rerank 反而赢，层级要到中等预算之后才收敛到更高的渐近线（Biology +5.3、Robotics +5.0 nDCG@10）。不控预算的比较没有意义。

### H2

协议：域 A 上长出层级 → **冻结** → 在域 B 上只允许下钻，禁止新增节点。

主指标：abstraction-level × transfer-hit-rate 曲线。

对照：A 的层级 / 随机打乱的层级 / 只有 level-0（等价于 case-based reasoning，无抽象）/ 无记忆。

## 6. 已知的坑（来自实证文献，别重蹈）

1. **检索准确率与任务收益会脱钩** —— precision 从 29.6% 崩到 3.3%，任务成功率却几乎不动（36–39%）。这说明现有 skill 大多只起"提醒用哪类套路"的锚点作用，而非被精确调用的组件。→ 只报检索指标会自欺，必须同时报端到端成功率，并解释脱钩。

2. **硬套模板是抽象带来的新失败模式** —— 误用/忽略 10.0% vs 0.8%。→ 下钻必须能输出"不适用"，见 §3.3 第 6 条。

3. **pattern 库修不了逻辑错误** —— 算法逻辑错误在各条件下恒定在 ~8–12%；skill 只能压掉执行层噪音（环境配置失败 5.3% → 0.2%）。→ 不要把 H1 的靶子设成"提升总成功率"，设在消歧准确率上。

4. **库会随规模腐化** —— 重复节点、失效节点、缺失判据。设计里先留 `stats` 字段，剪枝与合并逻辑放 v2，但别假装库是健康的。

## 7. 里程碑（进入编码阶段后）

- **M0** 数据结构 + 手工构造 20 节点的层级 → 先单独验证下钻算法本身，不掺入归纳/抬升的噪音
- **M1** induction + lifting 跑通，人工检查层级长成什么样 —— 这一步最容易暴露 MDL 代理指标选错
- **M2** H1 全套 baseline（含同预算对照）
- **M3** H2 冻结迁移实验

## 8. 待定问题

1. 域的最终选择（§4）
2. 下钻时是否允许在线修改层级（online vs sleep-phase-only）—— 影响闭环形态
3. `level` 是显式整数还是涌现的？倾向显式，因为 H2 的主指标就是按 level 分层的
4. 判别问题由谁回答：LLM 只看任务描述回答，还是允许它去环境里做一次探测动作？后者更强，但把检索和执行耦合了，会污染 H1 的干净对照

## 参考

- Demystifying Agent Skills: Why They Work—Until They Don't — https://arxiv.org/html/2608.14036v1
- LLM-guided Hierarchical Search (LATTICE) — https://arxiv.org/html/2510.13217
- HiSkill: Empowering LLM Agents with Hierarchical Skill Graphs — https://arxiv.org/abs/2607.25853v1
- SkillPyramid: A Hierarchical Skill Consolidation Framework — https://arxiv.org/pdf/2606.03692
- SkillX: Automatically Constructing Skill Knowledge Bases for Agents — https://www.alphaxiv.org/abs/2604.04804
- SkillRise: Agentic RL for Cross-Task Skill Evolution — https://arxiv.org/html/2607.26784
- LILO: Learning Interpretable Libraries by Compressing and Documenting Code — https://arxiv.org/abs/2310.19791
- Awesome-GraphMemory（图记忆综述合集）— https://github.com/DEEP-PolyU/Awesome-GraphMemory

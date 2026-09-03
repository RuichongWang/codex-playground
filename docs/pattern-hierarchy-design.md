# Pattern Hierarchy — 设计 v0.2（方向已修正）

> v0.1 把这件事理解成「层级已经存在，怎么把问题下钻到对的叶子」——一个检索问题。
> 错了。核心是**写入**：层级不是给定的，是一群 agent 边干活边猜、互相 link 出来的。

## 系统

一群 agent 在各自的领域干活。每遇到一件具体的事，写一条 **item**。
写入时**必须**给出它要 link 的 **pattern**（可以 N 个），并鼓励顺手猜新的 pattern。
一个被猜出来的 pattern，底下独立来源的 link 越多，可信度越高。
pattern 自己也能被 link 到更高阶的 pattern —— 层级是**从下往上被 link 撑起来的**，不是从上往下切出来的。

**迁移不是单独的机制**：就是从库里捞一个高可信 pattern，套到手头的问题上。
系统里没有训练/测试之分，也没有域的边界 —— item 的表面特征不同，pattern 本来就是跨域的。

**枢纽是「写入即验证」。** 没有单独的验证 pass，没有 sleep phase，没有目标函数。
一个猜测能不能活，取决于后来有没有别的 agent 在写自己的东西时，独立地判断「我这个也是它」。
跟科学假说一个结构：假说不是被提出者证明的，是被后来的独立观察撑起来的。

## 已定的规则

| 决策 | 定成 |
|---|---|
| link 有类型吗 | **有正负**。正 = 我是它的一个实例；负 = 我反驳它 / 它在这个情形下不适用 |
| 一个 item 能 link 几个 pattern | **多个**，且鼓励尽可能多 link |
| 什么时候猜新 pattern | **每次写入都要给出 link**，同时鼓励猜新的 |
| 怎么找到候选 pattern | **agent 自己跟库交互查询**，系统不预筛 |

最后一条的含义：库要暴露一组查询接口（搜索 / 浏览邻居 / 沿 link 上下走），
agent 自主决定怎么找。检索问题在这里回来了，但它在**写入侧**，且由 agent 自己发起 ——
v0.1 那套「沿层级下钻、每步问判别问题」在这里可能才有真正的用武之地。

## 对象

**Item**：一件具体的事。`{what(现象), intervention(做了什么), outcome(管不管用), context(域/场景), links[]}`
**Pattern**：一个猜测。`{kind: 现象|解法, claim, level(阶数), proposed_by, links_in[]}`
**Link**：`{from: item|pattern, to: pattern, polarity: +/-, condition(解法边必填), why, source}`

## 现象 + 解法（两侧）

item 不只记「发生了什么」，也记**做了什么干预、结果如何**。
pattern 因此有两类，用同一套机制生长（猜 → 别人 link → 汇聚出可信度 → 可再往上抽象）：

- **现象 pattern**：这类事情为什么会发生
- **解法 pattern**：这类事情该怎么动

连接两者的边 `现象 pattern --[条件]--> 解法 pattern` 是整个库里最值钱的对象。
它**必须带条件** —— 同一个现象在不同约束下要用完全不同的解。

### 为什么这一侧是关键

现象 pattern 的可信度只能靠**汇聚**（别的 agent 也觉得自己那件事属于它）——软信号，
可能收敛到流行而非正确。解法 pattern 的可信度可以靠**结果**（套上去到底管不管用）——硬信号。

不对称的根源：现象 pattern 是一个**解释**，很难证伪（「这是节奏错位」是一种说法）；
解法 pattern 是一个**预测**，可测（「加个缓冲，问题会消失」——试了就知道）。

所以解法侧反过来给现象侧背书：如果同一个解法在多个域里对同一个现象 pattern 反复奏效，
那这个现象 pattern 大概率是真抽象，不是措辞上的巧合。
**这是「靠汇聚验证」那个失效模式的解药。**

解法可以先于理解：agent 可以只记「我这么干了、好了、不知道为什么」，
现象侧的归属由后来的人补。系统要容纳这种写入。

### 条件是一等公民（已定）

TRIZ 的矛盾矩阵不是「现象 → 解法」，是 `(要改善的参数 × 会变坏的参数) → 原理编号`。
索引键是**矛盾**，不是现象 —— 因为同一个现象在不同约束下解不同。

本系统照抄这个结构。**Condition 是节点，不是字段**：跟 pattern 一样被猜出来、被 link、
靠汇聚获得可信度，也可以被复用到完全不相干的现象上。每个条件带一条 `test`
（怎么判断我满不满足），否则它没法被别的 agent 拿去自查。

于是矩阵格子成了一等对象 —— **Prescription**：`(现象 pattern, 条件集合) -> 解法 pattern`。
同一个现象可以挂多条 prescription，靠条件集合区分。用的时候 agent 带着
「我满足哪些条件」去查，直接筛掉不适用的解法。

代价是写入负担变重：agent 得说清自己的约束。这是明确接受的成本。

**失败的第一反应不是删掉 prescription，是补出缺失的条件。** 一次照搬翻车
（满足「可存储」但不满足「存取成本≈0」）恰恰是「存取成本≈0」这个条件被发现的方式。

CBR 里对应的概念叫 **determinator**：真正决定一个解法适不适用的那些属性，
而不是表面相似度。相似度假设不成立时，kNN 检索会返回一堆没用的案例。

### 新增的失效模式：照搬

高可信解法会诱发「不看条件直接套」。这正是 skill 库实证里那个
**误用/忽略 10.0% vs 原始执行 0.8%** 的失败模式。
所以边上的 `条件` 不是可选字段；解法侧的**负 link**（试了、不管用、因为 X）
和正 link 一样重要 —— 它是在给条件划边界。

## 可信度：数来源，不数 link

**不能只数 link 数。** 10 个来自同一个 agent、同一个场景的 link，价值远低于 3 个跨域跨 agent 的。
前者是一个 agent 的口癖被记了 10 遍，后者才是真的抽象。

可信度 ≈ f(独立来源数, 覆盖的域种类数, 正负比)，link 总数只是次要项。

不做这个区分，「靠汇聚验证」会退化成**收敛到流行，而不是正确** —— 这是它相对于
「靠目标函数验证」（v0.1 的 MDL 方案）最主要的失效模式。

## 负 link 的作用

负 link 不只是减分。它会**催生更准的 pattern** —— 一条「X 在这个情形下不成立」的记录，
往往直接指向「X 真正的适用边界是什么」，而那个边界本身就是个更好的 pattern。

## 已知的失效模式

1. **收敛到流行而非正确** —— 见上，靠来源多样性对冲。
2. **库爆炸** —— 每次写入都鼓励猜，pattern 数会疯长。靠沉底（长期零 link 的猜测降权）自净，
   但需要观察实际增长曲线再决定要不要主动剪。
3. **抽象过高反而不可用** —— TRIZ 的实证研究发现，降低发明原理的抽象层级反而提升了使用效率。
   「越抽象越好迁移」不是免费的，高阶 pattern 可能变成正确但没用的废话。这条要盯着。

## 人类先例：TRIZ

Altshuller 分析了几十万份专利，发现所有工程领域的发明问题都归结为有限的一组矛盾，
同样的 40 条发明原理反复跨领域出现。用法也一样：具体问题 → 抽象成矛盾 → 查原理库 → 落回具体方案。

**这就是本系统的人类手工版。** 区别在于 TRIZ 是一个人自上而下、一次性建成、然后冻结的；
这里是一群 agent 自下而上、持续生长、可信度由汇聚证据决定的。

同类的还有 Christopher Alexander 的 pattern language、生物启发设计的 AskNature 库。

## M0 代码的处置

`ph/` 下那套（合成域 + 生成的层级 + 下钻 + 平铺 baseline）是按 v0.1 的检索命题写的，
跟现在的方向不对口。**留着不删** —— 里面的下钻算法在「agent 自己查库找候选 pattern」这一步
可能可以直接复用。但它不是本系统的骨架。

## 参考

- TRIZ / 跨域类比：https://www.patsnap.com/resources/blog/articles/cross-domain-analogy-methods-triz-and-biomimicry/
- 降低 TRIZ 抽象层级反而提升使用效率：https://link.springer.com/chapter/10.1007/978-3-030-32497-1_41
- Governed Shared Memory for Multi-Agent LLM Systems（speculative write / 语义冲突）：https://arxiv.org/html/2606.24535v1
- Collaborative Memory: Multi-User Memory Sharing in LLM Agents：https://arxiv.org/html/2505.18279v1
- HypoAgent（溯因假说生成 → 证据收集 → 剪枝）：https://arxiv.org/html/2605.31370
- Emergent Semantics from Folksonomies：https://link.springer.com/chapter/10.1007/11803034_8
- TRIZ 矛盾矩阵（用矛盾而非现象索引解法）：https://www.triz-consulting.de/about-triz/triz-matrix/?lang=en
- CBR 基础问题与 determinator：https://www.iiia.csic.es/~enric/papers/AICom.pdf
- Demystifying Agent Skills（skill 库的实证失败模式）：https://arxiv.org/html/2608.14036v1

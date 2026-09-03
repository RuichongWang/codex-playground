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

**Item**：一件具体的事。`{what, context(域/场景), outcome, links[]}`
**Pattern**：一个猜测。`{claim, level(阶数), proposed_by, links_in[]}`
**Link**：`{from: item|pattern, to: pattern, polarity: +/-, why, source}`

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
- Demystifying Agent Skills（skill 库的实证失败模式）：https://arxiv.org/html/2608.14036v1

# Pattern Hierarchy — 精简设计

目标：够用，能跑，快。不追求可发表的严谨性。

## 想法

让 agent 把具体经历压成 pattern、pattern 再压成更抽象的 pattern；遇到新问题**沿层级走下来**拿到可执行步骤，而不是把库向量化 top-k 捞一把。

## 只回答一个问题

**在"看起来很像但做法不同"的候选之间，走层级选得比平铺捞更准吗？**

选这个当靶子的理由：现有数据显示 skill 库崩的地方是**辨析**不是召回 —— 库从 5 涨到 100，用对 skill 的 precision 从 29.6% 掉到 3.3%；语义相近的候选里 top-1 从 70.5% 掉到 53.4%，而随机干扰项只从 97.7% 掉到 84.1%。

迁移（高层节点能不能用在没见过的域上）当**附带观察**，不单独设计实验 —— 反正合成域换套表皮就能顺手测一下。

## 数据结构

一个 JSON 文件。不上数据库。

```json
{
  "id": "p17",
  "level": 2,
  "name": "...",
  "when": "一句判别式问句 + 判据",
  "vs_siblings": "我和兄弟节点的区别是什么",
  "steps": ["..."],
  "parent": ["p4"],
  "from": ["traj_003", "traj_019"],
  "stats": {"used": 12, "ok": 9}
}
```

`level` 用显式整数（0 = 具体轨迹，越大越抽象）。`parent` 是 list —— DAG 不是树。

## 域：自造合成域

一个任务生成器：预先定义一批"深层解法模板"（我知道 ground truth 层级），每个任务从模板实例化 + 随机表皮。

- outcome 程序化验证，不用 LLM 打分
- confusable 对直接构造：同一父节点下的两个兄弟模板
- 换一套表皮词汇 = 域 B，顺手测迁移
- 便宜到可以跑几千条

不用 ALFWorld / WebShop 那套：接环境的时间够我把整个东西写完了，而且没有 ground-truth 层级可对。

## 三个环（各取最简版）

**归纳** trajectory → pattern：输入带成功/失败标注（带标注 vs 不带，效果 0.75 vs 0.40，这个便宜且必须要）。失败的不丢，写进 `when` 的负向条款。

**抬升** pattern → 更抽象：LLM 提候选父节点，但**必须过一道客观筛子**，否则会长出一堆听着深刻、下钻时毫无判别力的空话。最简版筛子：候选父节点得覆盖 ≥ 2 个子节点，且 `len(父) + Σlen(子|父) < Σlen(子)`（省下的字数为正）。离线跑，不在执行路径上。

**下钻** query → path：从根贪心往下，每层给 LLM 一个候选列表（带 `vs_siblings`）。关键 —— 不问"哪个最像"，问 **"要在这些里做选择，我得先确认关于当前任务的哪件事"**，先要出判别问题再打分。走错允许回溯一次，不做 beam。必须能输出"都不适用"。

## 怎么算赢

跑两条曲线，库规模 5 / 25 / 100：

1. **confusable 集合上的 top-1 命中率**：层级 vs flat embedding top-k
2. 顺手记 token 数和"选错了还硬套"的比例

层级在小库上不赢没关系，**看的是曲线随规模的斜率** —— flat 崩、层级不崩，就成立。

## 我替你定的默认值

| 问题 | 定成 |
|---|---|
| 域 | 自造合成域 |
| 层级何时更新 | 只在离线 sleep phase，不在线改 |
| level | 显式整数 |
| 判别问题谁答 | LLM 只看任务描述，不去环境里探测 |

## 明确不做

严格等 token 预算的对照、beam search + 分数校准、多种 baseline（只留 flat top-k + 随机 sanity）、图数据库、五类边、库的剪枝/合并/健康度、真实环境接入、端到端成功率作为主指标。

需要时再加。

## 参考

- Demystifying Agent Skills: Why They Work—Until They Don't — https://arxiv.org/html/2608.14036v1
- LLM-guided Hierarchical Search (LATTICE) — https://arxiv.org/html/2510.13217
- LILO: Learning Interpretable Libraries — https://arxiv.org/abs/2310.19791

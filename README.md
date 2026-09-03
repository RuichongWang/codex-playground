# codex-playground — pattern hierarchy 实验

把具体经历压成 pattern、pattern 再压成更抽象的 pattern；遇到新问题**沿层级走下来**拿到可执行步骤，
而不是把库向量化 top-k 捞一把。

设计见 [`docs/pattern-hierarchy-design.md`](docs/pattern-hierarchy-design.md)。

## M0 现状

已实现：合成域 + 生成的层级 + 下钻算法 + 平铺 baseline + 评测脚本。
未实现：归纳（trajectory → pattern）和抬升（pattern → 更抽象 pattern）——
M0 的层级是从模板元组机械生成的，ground truth 已知，先单独验证「走层级」本身。

## 跑

```bash
pip install anthropic
export ANTHROPIC_API_KEY=...

python -m ph.eval --dry                          # 不调 API，只跑通管线
python -m ph.eval --tasks 12                     # 真跑
python -m ph.eval --tasks 12 --task-skin logs    # 换表皮 = 顺手看跨域迁移
```

## 域

记录上的 `filter → sort → take` 流水线。一个 leaf template = `(field, direction, filter, cut)`，
四个属性正好对应层级四层：

```
ROOT → 以「金额」为排序依据 → 按金额降序 → 先筛掉金额不超过 50 的 → 取前 3 条
```

- **outcome 程序化验证**：跑流水线比对输出，不用 LLM 打分
- **confusable 从构造上来**：同 filter 父节点下的兄弟只差「取几条」，词面几乎一样
- **换一套表皮词汇**（订单/金额 → 请求/延迟）= 域 B，顺手测迁移
- 90 个 leaf，任意子集都能诱导出对应层级，所以库规模 5/25/90 的曲线是免费的

关键一点：任务描述用**间接说法**（「这批订单里金额拔尖的 3 笔是哪些？」），
pattern 节点用**过程说法**（「按金额降序排序，取前 3 条」）。两者词面重叠很低——
否则平铺检索靠字面匹配就赢了，实验没意义。

## 三种取法

| | 做法 |
|---|---|
| `drill_down` | 从根贪心往下，每层一次判别式选择，不自信的叶子回溯一次走次优分支，可弃权 |
| `flat_topk` | 字面相似度取 top-10，**同一个 judge** 从中挑一个 |
| `lexical_top1` | 纯字面，不过 LLM。用来看这个域到底有多 confusable |

两种检索共用同一个 judge、同一个 schema、同一个 effort —— **差异只来自结构，不来自模型**。

下钻的关键不在「有层级」，在提问方式：不问「哪个最像任务描述」，而是
**「要在这些候选之间做选择，我必须先确认关于这个任务的哪一件事？」** 先要出判别问题，回答，再选。
改回问相似度的话，层级大概率是零结论。

## 怎么读结果

- **层级命中列随规模基本不掉、平铺命中列掉下去** → 命题成立。小库上不赢无所谓，看的是斜率。
- **命中率低但「输出对」高** → 检索与收益脱钩（文献里报过：precision 29.6% → 3.3%，
  任务成功率却几乎不动）。这个域里也会出现：`take 3` vs `take 5` 在数据不够时输出相同，
  `filter > 50` 在 top-3 全都超过 50 时是个 no-op。

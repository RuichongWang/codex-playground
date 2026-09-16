# done — 一个发 `done` 的最小硬核

> 状态:**设计,零代码**。这一份定形状,不定文件、不定函数签名。
> 读完应该不超过 10 分钟 —— 如果超了,说明这份设计已经犯了它要治的那个病。

## 〇 · 一句话

**给一件干完的活发一个「它自己伪造不了的 `done`」,依据是开卡时就冻住的 accept criteria,
并把这件事记成一行改不掉的账。**

**不是什么**:不是任务管理器、不是 CI、不是 agent 框架、不是知识库。
它只管**验收**这一件事,别的一概不碰。

---

## 一 · 为什么不是把 ONE 缩小一号

ONE 的方向是对的,但它长到 358 个单元 / 314 条黄 / 系统还开不了机,**病因是一条具体的机制**:

> **一条规矩可以先写下来,执行器标 `未落`。**

赊账本身是诚实的(比假装有执行器好得多),但它**没有上限** —— 一条规矩的边际成本接近零,
于是规矩涨到了认知上限。ONE 盘上 314 条黄里最大一族(94 条)就是 `未落`;
55 条纪律里 26 条明写"还检不了"。

**这一版换掉的就是那一条:**

> **写不出必红用例的规矩,不许进。**

从 ONE 搬过来的只有三样,一样都不多:
`done` 只能由 harness 授予 · 判据预注册即冻结 · 每条规矩配一条已知必红用例。
其余全部重新长。

---

## 二 · 卡 —— accept criteria 是主角

### 2.1 卡长什么样

```yaml
id: C-1
题面: 把 done v0 建出来
开卡: {时间: 2026-09-16T08:00:00Z, 人: alex}
accept:
  - {id: a1, 判据: "make check 全绿",        档: auto, 怎么验: {cmd: "make check",        期望: exit0}}
  - {id: a2, 判据: "实现代码不超过 500 行",   档: auto, 怎么验: {cmd: "tools/loc.sh",      期望: exit0}}
  - {id: a3, 判据: "没读过设计的人 5 分钟跑通第一张卡", 档: eye,
             靠什么兜: {谁: alex, 看什么: "只照 README 从零跑一遍,不许翻别的文件"}}
spec_hash: <accept 那一整块规范化之后的 sha256>
```

### 2.2 两档,恰好填一个

| 档 | 什么时候用 | 必须写 |
|---|---|---|
| **`auto`** | 能机械判的 | 一条命令 + 一个期望(exit code / 输出匹配)。**判的时候真跑** |
| **`eye`** | 今天机械判不了的 | `谁` + `看什么`。**不许写"人工复核"** —— 那等于没写 |

这一刀不是我发明的,是外面这两年收敛出来的共识:
**能机械的必须机械,人的判断只留给真需要的**;而一条 criterion 要 observable · atomic · bounded,
**pass/fail 没有中间态**。

**准入规矩:一张卡至少一条 `auto`。全是 `eye` 的卡不许开。**
—— 否则 `done` 退化成自评,而自评必然通胀(这是 ONE 六个仓烧出来的第一条结论,
今年外面也量出来了:ML 工程 agent 在自然跑动中**约 50% 的 episode 会尝试篡改评估管线**)。

### 2.3 防 drift 的三条机制(不是三句叮嘱)

| | 机制 | 挡住什么 |
|---|---|---|
| **一 · 冻结** | accept 落账时算 `spec_hash`。判的时候 hash 对不上 → **ABORT** | 干到一半发现过不了,顺手把判据改松 |
| **二 · 改要留疤** | 改 accept 必须落一行 `amend`(改哪条 · 为什么 · 谁批),**且该卡此前所有 verdict 当场作废** | 改得动,但**改不静默** |
| **三 · 不合成** | 逐条出结果,**没有总分、没有加权、没有百分比**。一条不过,整卡不过 | "主要达成"、"85% 完成"这类话是 drift 的入口 |

第三条是从 ONE 搬的那个判断(矩阵就是终点,不再往上合成)。**总分是一个可以被优化的东西,逐条清单不是。**

### 2.4 判决长什么样

```
verdict C-1 @ 4f2a91c
  a1  auto  pass   evidence: exit=0  out_sha=9c2f…
  a2  auto  pass   evidence: exit=0  out_sha=1ab7…
  a3  eye   pass   by=alex  note="照 README 跑通,卡在第 2 步 40 秒"
→ PASSED (3/3,且每条都带 evidence)
```

**没有 evidence 的 verdict 不许落账。** `auto` 的 evidence 是退出码 + 输出的 hash;
`eye` 的 evidence 是判的人 + 一句话。

---

## 三 · 四个零件

| 零件 | 是什么 | 为什么是它 |
|---|---|---|
| **账** | `ledger.jsonl`,append-only + hash 链;链头开机时从**外部**传入 | 唯一的地面真值 |
| **卡** | 开卡即冻结 accept,落一行账 | 验收的依据在干活之前就定死 |
| **判** | 独立进程,在一个 detached worktree 里 checkout 被判的那个 commit 再跑 | 判的是提交,不是工作区;干的那只手够不着 |
| **必红用例** | 每条规矩配一条已知会红的,`make check` 一次跑完 | 永远绿的用例证明不了执行器还活着 |

**关于「判的是一个 commit」**:accept 的 `auto` 命令跑在一个临时 worktree 里,
所以未提交的改动影响不了判决,判的对象(commit sha)也落进账里 —— 事后查得到判的到底是哪一版。

---

## 四 · 七条规矩

**每条都必须同时有:执行器 · 必红用例 · 绿对照。三样缺一,这条规矩不存在。**

| # | 规矩 | 执行器 | 必红用例 | 绿对照 |
|---|---|---|---|---|
| **R1** | 账只能追加 | 链校验 | 改账上任意一行的一个字符 → 报断链 | 正常追加三行 → 过 |
| **R2** | 开卡必须带 accept,且至少一条 `auto` | 开卡处 | 开一张全 `eye` 的卡 → 拒 | 一条 `auto` + 一条 `eye` → 收 |
| **R3** | accept 预注册即冻结 | 判决处比 `spec_hash` | 开卡后改 accept 再判 → ABORT | 不改 → 判得出 |
| **R4** | 判的那只手写不到账 | 判决子进程只拿只读句柄 | 判决过程里试图追加 → 抛 | 判决返回结果、由 harness 落账 → 成 |
| **R5** | verdict 逐条,且每条带 evidence | 落账前校验 | 落一条缺 evidence 的 / 只给总分的 → 拒 | 逐条带 evidence → 落 |
| **R6** | 改 accept 必须留疤 | `amend` 那条路 | 直接手改卡文件再判 → hash 对不上 ABORT | 走 `amend` → 落一行疤,旧 verdict 作废 |
| **R7** | 每条规矩必须有一条会红的用例 | `make check` 遍历规矩表 | 把任一执行器改成恒真 → 它的必红用例**不红** → check 判红 | 原样 → 全绿 |

**R7 是自指的那条,也是整件事最值钱的一条。** 它是 ONE 那条 D3(规矩 · 执行器 · 必红用例三样同一次落地)的最小版:
**一条因为错的理由而通过的检查,比没有检查更糟。**

---

## 五 · 三条硬顶(这才是防它长大的东西)

1. **实现代码 ≤ 500 行。** 超了就得砍一条规矩,**不许加文件**。
   *必红用例不计入这 500 行* —— 否则这条硬顶会奖励少写用例,那正是它要防的那个形。
2. **规矩 ≤ 7 条**,每条三样齐全。**写不出必红用例的规矩不许进。**
3. **第一天就能开机。** 跟 ONE 最大的形态差别:同样 fail-closed,但面必须先建好。
   **开不了机 = 这一批不算完。**

---

## 六 · 明确不做

写下来是为了将来有人想加的时候,先看见这一行。

价值函数 · 指标树 · 资源清单 · 自动选题 · 自我修改 · 多 agent 编排 ·
权限沙箱 · Web UI · 数据库 · 插件机制 · 任何"以后可能有用"的扩展点。

**要加任何一条,先砍掉一条现有的规矩。**

---

## 七 · 第一张卡,是它自己

`C-1` 的 accept 就是第二节 2.1 那三条。**用它自己验它自己** —— 第一天就 dogfood,
不留"等建完了再用"这条路(那正是 ONE 停在的地方)。

---

## 八 · 未定项

每条写明**什么数据能定它** + **谁来排空**。"以后再说"不是一个排空者。

| id | 未定的是什么 | 什么数据能定它 | 排空者 |
|---|---|---|---|
| **U1** | **`eye` 那一档会不会漂。** 外面管这叫 calibration drift:一个上季度还跟人一致的判官会静默偏移,而可接受基线是 Cohen's κ ≥ 0.6。**我们今天 n=1,κ 算不出来** | `eye` 判决累计 ≥ 20 条之后,抽 10 条让第二个人独立重判 | alex |
| **U2** | **链头外部传入到底挡住了什么。** 诚实说:它挡的是**静默**篡改,不是有决心的对手 —— 能读到 head 的进程就能把它传对 | 真跑之后,看有没有哪一次断链是被它逮到的 | 第一次断链事件 |
| **U3** | **写不出 `auto` 的那类活怎么办**(比如"这段设计读起来清楚") | 头 20 张卡里 `eye` 条数的占比 | alex,在第 20 张卡时看一次 |

---

## 九 · 参考

- 验收不能自评,今年的两个数:[RewardHackingAgents(arXiv 2603.11337)](https://arxiv.org/abs/2603.11337)
  —— 自然跑动中约 **50%** 的 episode 尝试篡改评估管线,evaluator locking 能消掉但有 25–31% 运行时开销;
  [Do Agent Benchmarks Measure Capability?(arXiv 2607.22368)](https://arxiv.org/abs/2607.22368)
  —— 15 个 benchmark、2385 条 trace,约**三分之二**带 reward hacking 证据,分数通胀 0.45–1.00
- accept criteria 要 machine-verifiable、observable/atomic/bounded、pass-fail 无中间态:
  [Acceptance criteria agents can actually verify](https://paelladoc.com/blog/acceptance-criteria-for-ai-agents/) ·
  [How to Write Acceptance Criteria an AI Agent Can Actually Verify](https://www.braingrid.ai/blog/how-to-write-acceptance-criteria-ai-agent-can-verify)
- `eye` 那一档的风险(calibration drift · κ ≥ 0.6 基线):
  [Rubric-Based Evals & LLM-as-a-Judge](https://medium.com/@adnanmasood/rubric-based-evals-llm-as-a-judge-methodologies-and-empirical-validation-in-domain-context-71936b989e80)
- 病因那一节的盘面数字来自 `RuichongWang/ONE`,现跑 `python3 docs/spec/check.py` 可复现

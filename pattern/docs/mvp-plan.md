# MVP 计划：临床试验方案修订预测（2026-09-05）

承接 `docs/application-scan.md` 第五节的决定。这份写「怎么跑」。

## 为什么是这个任务

一句话：**ground truth 不是我们写的。**

前三轮撞四次天花板，根因之一是 held-out 的条件清单由**同族模型从同一份源材料**写出，
所以那个指标测的其实是「读题够不够仔细」。
而「这份方案后来改没改、改了哪一节」是**世界写的**，我们碰不到。

外加两条：它天然是**带日期的预测任务**（写得好看没用），且日期让污染可以分层检验。

## 数据（已实拉验证，2026-09-05）

ClinicalTrials.gov 有一个**未在官方 API 文档中**的端点，网站 Record History 页用的就是它：

```
GET https://clinicaltrials.gov/api/int/studies/<NCT>/history        # 版本列表 + moduleLabels
GET https://clinicaltrials.gov/api/int/studies/<NCT>/history/<v>    # 该版本全文
```

实拉 NCT07502495（本人复核）：

```
v0  2026-03-26  RECRUITING             []
v2  2026-05-11  RECRUITING             [Study Status, Contacts/Locations]
v3  2026-08-05  RECRUITING             [Study Status, Arms and Interventions,
                                        Outcome Measures, Eligibility, Contacts/Locations]
v4  2026-08-26  ACTIVE_NOT_RECRUITING  [Study Status, Study Design, Contacts/Locations]
```

v2→v3 的实际内容（本人复核）：`maximumAge 70 Years → 75 Years`、
某次要终点 `timeFrame 16 weeks → 52 weeks`。v2 快照无 `derivedSection`、无结果段。

**`moduleLabels` 是注册方提交时系统自动打的，不是我们标的。**
40 个版本跃迁逐字段验保真度：除 `Study Status` 外**零漏报零误报**。

**⇒ ground truth 回路里一个模型都没有。** 这是这次跟前三轮最大的结构性区别。

> ⚠️ 不许照抄 AMEND++（arXiv 2601.06300）的 LLM 去噪管线 ——
> 那会把同族模型重新放回 ground truth 回路，正是我们要逃的那个根因。
> 我们的判分标准比他们松（只判「改了哪一节」，不判「改成什么」），确定性规则就够。

### 硬伤与处理（全部要写进预注册）

| 硬伤 | 实测 | 处理 |
|---|---|---|
| 污染窗口只有 4 个月（cutoff 2026-05） | cutoff 后有实质修订的占 **8%** | 筛选池够大：Phase 2/3 + cutoff 后有更新 = **5,133** 个，约 1,580 个正类。50 正 + 50 负绰绰有余 |
| `Study Design` 70% 是假阳性 | 20 个里 14 个只是 `enrollmentInfo.type: ESTIMATED→ACTUAL`（招募收尾账目，例 `1400 → 0 ACTUAL`） | 确定性规则：`type` 发生 ESTIMATED→ACTUAL 的一律不算正类 |
| 原始方案本身在训练数据里 | 几乎肯定 | 分三层报：**L1**（v0 在 cutoff 前、修订在后，n 大）为主，**L3**（v0 也在 cutoff 后，n 小）当纯净对照。方向不一致就不下结论 |
| AMEND++ 2026-01 已发表，模型可能见过任务与统计规律 | — | 排除其 test split 的 6,067 个 NCT ID |
| `Arms and Interventions` 含表述噪声 | 约 25%（实例：`matching placebo 100 mg` → `placebo matching 100 mg`） | 保留该模块，但在预注册里声明噪声比例，不许事后调 |

### 输入怎么造（去泄漏）

服 **v0（或 cutoff 前的最后一版）原文**，不要服当前记录 —— 这一条解决 90% 的泄漏。再删：

- `statusModule` 整块（含 `lastUpdatePostDate` / `lastUpdateSubmitDate` /
  `statusVerifiedDate` / `overallStatus`）；但 `startDate` / `primaryCompletionDate`
  是合法输入，单独保留
- `derivedSection`（v0 本来就没有）
- `contactsLocationsModule.locations` 折叠成 `{n_sites, countries}` ——
  既去 PII、又去掉 600 条列表重排噪声，同时保留「16 个中心、只在美国」这个
  对可行性判断至关重要的信号
- 时间切分按 **post 日**算（history 里的 `date` 是 submit-QC 日，比 post 日早 2–9 天），
  留 ~10 天 buffer

实测 token 量：完整 v0 中位 ~3,273 token；去泄漏折叠后中位 ~2,502 token；100 道题共 250k。可忽略。

### 备选已砍

**MAUDE + FDA 召回库：不通。** 召回库的 `root_cause_description` 里
**「Use error」32 个月总共只有 79 条**，切到 cutoff 后剩个位数；
且 **27.2% 的根因是「厂商还在调查中」**。样本量直接判死。

## 域污染：改用 tag + strict mask，不永久冻结

**决定（2026-09-05）**：临床试验 / 药物研发**不**加入 `heldout/` 的永久保留域，
改用「打域标签 + 跑实验时 `--mask ... --strict`」。

理由：`Store.mask(strict=True)` 已经实现了「措辞泄露」那一刀 ——
它按**提议者**删：一个 agent 只要在同一批里写过被屏蔽域的 item，
它提出的 pattern 和 condition 一起删；并用时间闸（`same_batch=900`）
解决了 agent id 跨轮重号的问题。这是真机制，不是遮羞布。

六个保留域值得永久冻结，是因为它们承载**核心迁移命题**；
临床试验只是若干应用靶子之一，tag + strict mask 是相称的。

### 但有一处残留泄漏，必须记下来并测

**第 N 轮的 agent 读到第 N−1 轮由制药 item 长出的 pattern，在它之上再写一条更抽象的** ——
这条新 pattern 的提议者没写过制药 item，`strict` 删不掉它，
但它的措辞是被那条抽象塑造的。**这个泄漏随轮数增长。**

可测：数 order≥2 的 pattern 里有多少条的 grounding 路径穿过被屏蔽域。
这个量要跟结果一起报。

### 另一个解读风险

mask 掉 `healthcare` + `publichealth` 后剩 16 域 / 80 item，
但其中 7 个是**理论 / 元域**（`ops_theory` `mgmt_theory` `econ_theory` `safety_theory`
`contested` `duplicates` `went_right`），**真正的行业域只剩 9 个**
（supplychain / software / transport / manufacturing / energy / finance /
construction / events / agriculture）。

抽查 mask 后仍存活且对得上的 pattern：

| pattern | 正/负 | mask 后的支撑域 | 跟临床试验方案的对应 |
|---|---|---|---|
| P3 | +24/−0 | supplychain, manufacturing, transport, software, construction, events | 不可靠工具放在计划回路唯一入口，代价只与下游承诺链的刚性有关 → 一条写错的入组标准，代价取决于它下游锁死了多少不可撤销的承诺 |
| P43 | +16/−2 | software, energy, events, agriculture, ops_theory | 资源告急的真实自变量是负载的时间形状而非产能上限 → 筛败不是标准太严，是筛查到达的时间分布 |
| P6 | +7/−0 | supplychain, ops_theory, mgmt_theory | 预测误差无法消除时，压缩承诺前置期比提高预测精度更有效 |
| P2 | +3/−0 | supplychain, software | 选型/试点规模下可用、真实数据量级下退化到不可用 → 在设计桌上可行、在真实到达率下不可行 |

**风险**：如果模型主要靠 `ops_theory` / `econ_theory` / `mgmt_theory` 取抽象，
那测出来的是「教科书运筹学有没有用」，不是「跨行业事故经验有没有用」。
⇒ **预注册里加一个诊断量**：被引用的 pattern 中，支撑来自**真实行业 item**（非理论/元域）的比例。
不改主指标，但决定结果怎么读。

---

## MVP：$22，半天，一个 judge 都不用

**规模**：20 题（10 正 10 负，L1 层）× 3 臂 × **3 次重复** = 180 次调用

| 臂 | 配置 |
|---|---|
| A | 裸跑，不给库 |
| C90 | 库 90 + `--mask healthcare,publichealth --strict` |
| C30 | 库 30 + 同样 mask ← 只为偷看斜率方向 |

**判分完全确定性、无模型**：六个模块各给 0–1 概率 → Brier + 标签集 F1。
ground truth 直接读 `moduleLabels`。

**3 次重复是必须的**：输出是概率，方差本身就是信号；且已经栽过一次 n=1 的跟头。

### MVP 明确不做什么

不跑模型轴、不报 CI、不报 p 值。
**n=20×3 给不出有意义的置信区间，不假装它能。**
MVP 的唯一作用是筛掉明显的失败模式。

### 四个判据（跑之前写死）

| | 条件 | 动作 |
|---|---|---|
| **停 1** | 裸跑六模块平均 Brier **< 0.10** | 题太简单 —— 最可能是泄漏字段没删干净。回去查，不是继续跑。对照：AMEND++ 在**更简单的二分类**上最好 AUROC 才 0.697 / Acc 64.4%（基础率 52.8%） |
| **停 2** | C 臂引用的 pattern 中，支撑来自**真实行业 item** 的比例 **< 30%** | 测的是教科书不是跨行业经验。先修语料再跑。该量 `pk/transfer.py` 已能算 |
| **停 3** | n=20 上 C 就明显差于 A | 这是个**结果**（与 ForecastBench 那次同族：在无关材料里找到支持、强化错误判断）。转去查有害性机制，不是继续扩规模 |
| **继续** | 方向为正 **且** trace 显示库被真用 **且** 裸跑不在天花板 | 三条全中才扩到 100 题 |

---

## 扩库：90 → 180

复用现有 pipeline（只读快照 → 提议 → triage 只出归并映射 → 代码逐字搬运）。
实测成本每 30 条约 $25–28（第 2 轮 $28），扩 90 条约 **$75–85**。

**三条设计约束**：

1. **按 90 的类型比例采**（事故 2/3 : 理论+正面案例 1/3）。新规模点与 90 同质，
   **顺手解掉规模轴与语料类型轴共线**那个问题 ——
   于是有 30/60/90/180 四个点、6 倍跨度，「斜率」这个词才站得住
   （验收标准要 ≥4 点，见 `docs/application-scan.md`）。
2. **优先补最稀缺的两类**：拦截案例（现 5 条）和干预失败（现 13 条）。
   **全世界的公开事故库都只记发生了什么，没有一个记「我打算做的这个动作别人做过没有、成没成」** ——
   这两类是护城河，不是补充。
3. **域选择：不抄 CSB / NTSB / ASRS。** 抄了就变成更小的同域库，打不过人家 140 万份免费报告。
   该补公开库结构上没有的地方 —— 会展、教育、非营利运营、市政、餐饮连锁、最后一公里物流。
   **跨域增益是靠距离长出来的。**

**不变的红线**：`heldout/` 六个保留域（采矿、航天、司法、影视档案、渔业海事、国防采办）
永远不许进库。扩库的语料 fan-out 必须有代码级闸门，不能靠 prompt 叮嘱。

---

## 顺序

```
① 出题管线 + 拉 100 道题的数据          半天    ← 原型已在 scratchpad 跑通
② MVP：20 题 × 3 臂 × 3 次              $22
   ↓ 过了四个判据才往下
③ 扩库 90 → 180（两轮）                 $75–85
④ 全量：100 题 × 4 个规模点
```

①② 之前不动库，所以扩库那笔钱只在 MVP 过关后才花。

## 工作量估算（全量 100 题）

| 阶段 | 内容 | 估计 |
|---|---|---|
| 数据管线 | 筛 5,133 个 history（~50 min API）+ 拉两版全文 + 分层抽样 | 0.5 天（原型 ~120 行已跑通） |
| 出题 | 去泄漏字段函数 + 100 道题人工 QA 抽查 20 道 | 1 天 |
| Ground truth | module-level 标签 + `Study Design` 规则 + AMEND++ NCT 排除 | 0.5 天（纯确定性代码） |
| 判分 + 预注册 | Brier + 标签集 F1 + 分层报告方案 + 理由 rubric（辅助） | 0.5 天 |
| 跑 + 分析 | 4 个规模点 × 100 题 × 2 臂 | 0.5 天 |
| **合计** | | **约 3 个 agent-日** |

比原计划那笔 $350–450 的斜率实验便宜 —— **因为 ground truth 是免费的、世界写的，我们不生成任何东西。**

---

## 一个操作陷阱（实测）

`/api/int/` 对 **python urllib 一律返回 403**，对 curl 返回 200 ——
换 UA、加 Accept 头都没用，是 TLS 指纹层的拦截。
解法：`subprocess` 调 curl，或用 `curl_cffi`。
实测 300 次 history + ~200 次 version 拉取、0.25s 间隔，**0 错误**。

## 复核状态

**本人（主 session）实拉复核**：`/api/int/` 端点可用、`moduleLabels` 内容、
NCT07502495 的 v2→v3 实际字段变更（`maximumAge 70→75`、`timeFrame 16→52 weeks`）、
v2 快照无 `derivedSection`/结果段、`Store.mask(strict=True)` 的实现语义。

**subagent 实拉实算、未经本人逐条复核**：40 个跃迁的保真度矩阵、
两个 150 样本的版本分布、`Study Design` 70% 账目噪声、8% 正类率、
token 量分布、openFDA 召回根因分布、5,133 筛选池规模。

**引用的外部数字**：Tufts CSDD 57% / 45% avoidable / Phase III $535k；
Advarra 30,000+ 试验；AMEND++ 的 161,970 / 52.8% / AUROC 0.697。

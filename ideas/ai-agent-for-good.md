# AI / Agent for Good：机会图谱与选题建议

> 整理日期：2026-09-05。所有数据均标注来源，注意时效性。

## 一、先把"不均衡"拆成三层，别混为一谈

"AI 发展迅猛但各行业不均衡"是对的，但这句话里其实叠了三个不同的问题，对应完全不同的行动：

| 层次 | 现象 | 证据 | 谁该解决 |
|---|---|---|---|
| **能力不均衡** | AI 对文本/代码/结构化推理很强，对物理世界、长尾数据很弱 | 长时程 agent 在 2026 才刚跨过"自主工作数小时"的阈值 | 实验室 |
| **采用不均衡** | 有钱有数据的行业先用 | 美国信息业 39.7% vs 零售 ~14%，全国均值 19.8%（Census, 2026-05）；全球用量与人均 GDP 强相关，新加坡 4.6× 预期、印尼/尼日利亚远低于预期 | 市场 |
| **供给不均衡** | 有些人群/场景**根本没有商业买家** | 罕见病、法援、照护、低资源语言 | ← **这一层才是 for good 的真空** |

**结论：impact 最大的位置 = 技术已经够用 × 采用率接近零 × 没有人愿意付钱。** 三个条件的交集很窄，但正因为窄才轮得到你做。

## 二、2026 的新变量：长时程 agent 让"行政流程"第一次可攻

以前的 AI4Good 大多是"知识型"的——给弱势群体一个问答机器人。但这些人群缺的常常不是知识，是**跑完流程的时间和精力**。

2026 的变化在于：agent 的任务时长大约每 4–7 个月翻一番，2026 被普遍认为是长时程 agent 主流化的一年，能自主工作数小时、自己发现并修正错误。这意味着"替人跑完一套吃人的行政流程"从演示变成了可交付。

→ **最被低估的方向不是"给弱势群体一个聊天机器人"，而是"替一线工作者/家属跑完行政流程"。**

## 三、三条硬教训（先看这个，能省一年）

1. **95% 的 AI pilot 到不了生产**，且成功案例的投入比例大约是 **10% 算法 / 20% 基建 / 70% 人和流程**。Demo 崩在真实的、脏的、割裂的数据上。
2. **直接把 AI 交到终端弱势用户手里，可能是有害的伪赋能。** 最扎心的证据：AI 辅助的自诉状看起来比历史上的 pro se 文书更专业，但**驳回率更高、胜诉率并没有提升**。斯坦福 Legal Design Lab 拿盖茨基金会的钱做的 Justice AI Co-Pilots，服务对象是**法援律师和工作人员**，不是当事人——这个选择是有道理的。
3. **缺口常常不在模型，在分发和成本。** 中国罕见病 AI 已经很能打：DeepRare 表型诊断首位准确率 57.18%，比此前国际最佳模型高 23.79 个百分点，确诊周期从平均 4.26 年压缩到"周"级；"协和·太初"已进临床。但基层医院的原话是："我们能看到好工具，却难以全面推广，购置成本对基层医院而言是不小的负担。" 再造一个模型的 impact，很可能远小于让基层免费用上现有模型。

## 四、四个候选方向（按"技术够用 × 无人在做 × 可验证"排序）

### A. 行政负担杀手（最看好）
- **问题规模**：预计 2026 年有多达 **520 万美国成年人因行政障碍（而非不符合资格）失去 Medicaid**；SNAP 的低领取率被研究界直接定义为"行政负担的空间投影"——交通不便、教育程度低的地区，在资格完全相同的情况下领取率系统性更低。申请要经历数小时电话排队、数天到数周的邮件等待。
- **已有玩家**：Anthropic × Code for America 在做 caseworker 侧的 SNAP Policy Navigator 及一套 Claude 工具；Nava Labs × Benefits Data Trust 在做 navigator 侧的 WIC/SNAP/Medicaid 资格识别。
- **空白**：这些几乎全部集中在美国联邦项目。**其他地区的等价物基本是空白**——低保/医保异地报销/残疾证办理/大病救助/公租房申请/工伤认定。这类问题的本质是"规则复杂度 × 申请人认知负担"，正好是 LLM 的甜区。

### B. 一线工作者的副驾驶（而非终端用户的聊天机器人）
- 对象：社工、乡村医生、特教老师、法援律师、护工、基层疾控。
- 共同特征：极度缺人 + 大量非核心文书 + **本人有专业判断力，天然是合格的 human-in-the-loop**。
- 这条路径规避了教训 2，也最容易做出可证伪的指标（每例节省分钟数、错误率、结案周期）。

### C. 照护缺口（体量最大、最真实、也最难）
- 美国预计到 2030 年缺 15.1 万带薪照护者 + 380 万无偿家庭照护者，2040 年扩大到 35.5 万 / 1100 万；65 岁以上阿尔茨海默及相关痴呆患者约 690 万，2060 年预计 1390 万；照护者平均每周 21 小时以上、持续 4 年以上。
- **agent 能做的不是替代照护（物理世界仍然不行），而是照护协调**：预约、用药提醒、保险与报销、多方沟通、文书。学界已有 AI-Care 这类面向阿尔茨海默照护任务协调的 agentic 系统。家庭照护者的行政+情绪负担是明确的真空地带。

### D. 语言与长尾数据（最像公共品，最需要非营利来做）
- 约 **90% 的非洲语言属于低资源语言**；全球 ~7000 种语言中，被 NLP 认真研究的不到 20 种；40% 的语言面临消失风险。主流 LLM 训练语料 90% 以上是英语。
- 这不是产品机会，是**基础设施机会**：高质量数据集和评测集比模型更稀缺、更长效。中国的方言与少数民族语言同理。适合"开源 + 学术"路径，可验证、可积累、可发表。

## 五、我会劝退的方向

- ❌ 再做一个"给 XX 群体的 ChatGPT 套壳"——见教训 2，可能帮倒忙。
- ❌ 依赖捐赠、需要持续人工运营的 web app——没有可持续运营主体的，基本活不过两年。
- ❌ 需要自研硬件的（照护机器人等）——除非本来就有硬件背景。
- ❌ 从"平台"起步。永远从"替代一个具体的、此刻有人正在手工重复做的动作"起步。

## 六、方法论：先找人，再找题

1. **先找组织，不要先找问题。** 成败 70% 在人和流程。去找一个已经在做这件事、但缺技术的机构，当他们的技术合伙人；不要自己凭空立项。
2. **定一个可证伪的指标**："申请通过率 +X%"、"确诊周期 −Y 周"、"每例文书节省 Z 分钟"，而不是"帮助了多少人"。
3. **从最脏的那段流程切入**，不要从最性感的那段切入。
4. **资金与资源**：OpenAI 的 People-First AI Fund 承诺 5000 万美元支持非营利；2026 年这类支持普遍是"现金 + 模型额度 + 工程支持"的组合。注意：资助方现在会问"你如何治理 AI"，整合了伦理、数据保护与运营准备度的提案明显跑赢一次性的 pilot 点子。

## 七、参考来源

- [The AI Adoption Gap Is Real: May 2026 Census Data](https://www.mattbritton.com/blog-posts/the-ai-adoption-gap-is-real-what-the-may-2026-census-data-reveals-about-u-s-business)
- [Anthropic Economic Index: Uneven geographic and sector adoption (arXiv)](https://arxiv.org/pdf/2511.15080) ・ [Learning curves 报告](https://www.anthropic.com/research/economic-index-march-2026-report)
- [A new Moore's Law for AI agents — AI Digest](https://theaidigest.org/time-horizons) ・ [2026: This is AGI — Sequoia](https://sequoiacap.com/article/2026-this-is-agi)
- [Overcoming the AI Pilot Trap — Argano](https://argano.com/insights/articles/overcoming-the-ai-pilot-trap.html) ・ [Pilot Purgatory — Velosio](https://www.velosio.com/blog/pilot-purgatory-why-ai-initiatives-fail-to-reach-production/)
- [Artificial Access to Justice: AI and the Surge in Pro Se Litigation (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6864398) ・ [Justice AI Co-Pilots — Stanford Legal Design Lab](https://justiceinnovation.law.stanford.edu/justice-ai-co-pilots) ・ [AI for Legal Help 2026 Class Report](https://justiceinnovation.law.stanford.edu/ai-for-legal-help-2026-class-report-scoping-building-and-testing-new-legal-aid-tech-systems/)
- [Closing the SNAP Gap (arXiv)](https://arxiv.org/pdf/2511.00080) ・ [Anthropic × Code for America — Nextgov](https://www.nextgov.com/artificial-intelligence/2026/05/anthropic-and-nonprofit-partner-streamline-benefits-administration-ai/413455/) ・ [Nava Labs 公共福利 AI 试点](https://www.navapbc.com/case-studies/ai-tools-public-benefits) ・ [AI-first Medicaid 政策简报 (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12663265/)
- [从四年到四周：中国罕见病"确诊难"加速破局](https://news.qq.com/rain/a/20260228A03IAZ00) ・ [可溯源 AI 诊断系统 DeepRare — 中新网](https://www.chinanews.com.cn/jk/2026/02-19/10574196.shtml) ・ [AI 诊疗（下）：还有几道坎要过 — 新华网](https://www.news.cn/health/20260616/b21ee1ef64f5405994e112fec597e347/c.html)
- [Redefining Elderly Care with Agentic AI (arXiv)](https://arxiv.org/pdf/2507.14912) ・ [AI-Care: Agentic System for Alzheimer's Care Coordination (arXiv)](https://arxiv.org/pdf/2605.08480) ・ [AI in AgeTech — Unite.ai](https://www.unite.ai/ai-in-elder-care-addressing-the-caregiver-shortage/)
- [Mapping the AI Divide in Africa (arXiv)](https://arxiv.org/pdf/2606.30656) ・ [The African Languages Lab (arXiv)](https://arxiv.org/pdf/2510.05644) ・ [Low-Resource Languages in AI](https://www.digitaldividedata.com/blog/low-resource-languages-in-ai)
- [OpenAI People-First AI Fund（5000 万美元）](https://openai.com/index/people-first-ai-fund/) ・ [AI Grants for Nonprofits 2026](https://www.whitelabel.ai/blog/ai-grants-for-nonprofits)

---

# 附：针对"纯技术背景 / 业余投入 / 开源 / 不为盈利"的具体路径

补充日期：2026-09-05。前提条件确认为：地区未定、每周只有零散时间、纯技术背景没有领域人脉、目的不是赚钱。

这四个条件叠起来，会**淘汰掉上面一半的方向**。诚实地说：

- ❌ 需要长期运营的产品/SaaS —— 业余时间给不了 SLA，而弱势用户是最经不起"作者忙别的去了"的一群人。半途而废的公益产品比不做更糟。
- ❌ 需要拿资助的项目 —— 资助方要治理方案、要交付承诺，这是全职的事。
- ❌ 需要领域深度的垂直应用 —— 没有领域人脉，你做出来的东西大概率解错题。

剩下的交集只有一类：**无运营负担、能积累、别人拿去就能用的公共品。** 而且不为钱这件事在这里是优势，不是劣势——公共品本来就没人愿意付钱做，所以才空着。

## 首选：给"真实世界脏输入"做鲁棒性评测

**这是我最推荐的方向。**

问题诊断已经有人替你做完了。ICML 2026 AI4Law workshop 的论文《Legal Reasoning Is Not Lawyering》指出：现有法律 benchmark（LegalBench、LEXam、LegalBench-RAG）测的是**上界**——输入是法律专家已经清洗整理过的。但真实的自诉当事人输入是"**嘈杂的叙述、被埋没的事实、遗漏、民间法律假设、以及表层错误**"，需要测的是**下界**。作者在 LEXam 上做扰动实验证明了这个落差，并明确呼吁重新设计 benchmark，让"AI 促进司法可及性"这个说法**变得可被实证检验**。

这正好解释了前面那个反直觉的数据：AI 辅助的自诉状看起来更专业，但驳回率更高。不是模型不够强，是**没人测过模型在真实脏输入下会怎样**。

### 为什么这件事适合你

| 你的约束 | 为什么这个方向匹配 |
|---|---|
| 业余时间 | 评测集做完就是做完了，没有用户等你回消息 |
| 纯技术背景 | 主体是写扰动器 + 跑模型 + 出榜单，纯代码活 |
| 没有领域人脉 | 可以先做出 v0 再拿着东西去找领域人验证——**有东西比有想法更容易约到人** |
| 不为钱 | 评测集天然是公共品，没有商业模式，所以才没人做 |
| 会伤害到人吗 | 不会。你不直接服务弱势用户，你是在给服务他们的人提供刹车 |

### 可以这周末开始的 v0

1. 挑一个已有的公开 benchmark（法律、医疗问诊、福利申请资格判断均可）。
2. 写一组**真实世界扰动算子**：口语化改写、方言/非母语表达、删掉一个关键事实、时间线打乱、加错别字、混入大量无关叙述、加入错误的"民间法律/医学常识"前提。
3. 跑几个主流模型，对比扰动前后的表现落差，公开代码 + 榜单。
4. 落差本身就是结论。这个数字目前没人有。

跑通一个领域之后，同一套扰动框架可以横向复制到福利申请、基层问诊、教育评估——这是可积累的。

## 次选：直接加入已有社区（如果你更想要"跟人一起做"）

纯技术背景没有领域接触时，**加入比立项高效得多**——社区本身就是你缺的那个人脉。

- **Masakhane**（非洲语言 NLP）：1000+ 参与者、覆盖 30 个非洲国家，明确列出了多种参与方式（训模型并贡献代码、贡献数据、做数据/模型分析——这条**不需要技术经验**、帮忙整理文档），用 Colab notebook 降低门槛，有 Slack、每周会议和 GitHub。对应的问题是真的大：约 90% 非洲语言属于低资源语言，40% 的语言面临消失风险。
- **DataKind**：3 万+ 数据科学志愿者社区。两种投入档位很清楚——**DataDives** 是 48 小时黑客松式活动（50–150 人规模），**DataCorps** 是 6–9 个月项目、每周 5–10 小时。当前在招募"消除贫困"主题的志愿者。这个 5–10 小时/周的档位基本就是为你这种情况设计的。

## 备选：无障碍（a11y）的工程债

如果想做马上有人受益、反馈最直接的事：**前 100 万个访问量最高的网站里，95.9% 的首页存在可检测的 WCAG 无障碍失败，平均每页约 56 个错误**，最常见的是低对比度文本（约 84% 的页面）。核心诊断是：这是个**集成问题**——无障碍标准从来没有被接进"写代码、评审、发布"的工作流里。

对一个 agent 时代的技术人来说，这里有个很自然的切口：**把无障碍检查做成 agent 能在 PR 阶段自动执行并给出修复补丁的东西**，而不是又一个扫描器报告。WordPress 无障碍团队到 2026 年 6 月已有 1464 人承诺投入时间——说明这类工作有接得住的社区。

## 一个明确的劝退：不要做"给残障人士的 AI 助手"

这看起来是最典型的 AI for good，但已经是大厂免费产品的红海：微软 Seeing AI、Be My Eyes 的 AI 功能、Google Live Transcribe、Apple 的 Braille Access（把 iPhone/iPad/Mac/Vision Pro 变成盲文记录器）、OrCam MyEye、以及 Google 与三星 2026 年推出的集成 Gemini 的 AI 音频眼镜。个人业余项目在这里没有胜算。

这个领域真正的空白不是技术，是"**残障人士被系统性排除在 AI 开发过程之外**"——那是参与机制问题，不是写代码能解决的。想在这个领域做事，正确姿势是去做上面那条 a11y 工程债，或者去支持由残障人士自己主导的项目。

## 补充来源

- [Legal Reasoning Is Not Lawyering: Rethinking Legal Benchmarks for Pro Se Access to Justice (arXiv, ICML 2026 AI4Law)](https://arxiv.org/pdf/2606.23716)
- [Masakhane 官网](https://www.masakhane.io/) ・ [masakhane-community（从这里开始）](https://github.com/masakhane-io/masakhane-community) ・ [Masakhane 论文](https://arxiv.org/pdf/2003.11529)
- [DataKind Volunteer](https://www.datakind.org/join-us/volunteer/) ・ [DataKind 社区](https://www.datakind.org/join-us/our-community/)
- [Accessibility Best Practices for Your Project — Open Source Guides](https://opensource.guide/accessibility-best-practices-for-your-project/) ・ [The A11Y Project](https://www.a11yproject.com/)
- [AI and Disability in 2026 综述](https://www.ameridisability.com/ai-and-disability-in-2026-a-comprehensive-guide-for-people-with-disabilities-caregivers-seniors-and-families) ・ [Cripping AI: Reimagining AI Through Lived Disability Experiences (arXiv)](https://arxiv.org/pdf/2605.02080)

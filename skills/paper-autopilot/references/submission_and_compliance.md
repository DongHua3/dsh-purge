# 投稿流程与合规（第 14、18、20、21 步作业指导）

> 政策部分全部来自出版商/机构官方页面的原文，出处见文末。
> **政策会变，投稿前必须再查目标刊当日页面。**

---

## 一、AI 使用政策（最重要的一节，先读这个）

### 1.1 Springer Nature / Nature Portfolio 的三级风险框架

Springer Nature 现行的 AI 政策不是"能不能用"的一刀切，而是**按风险分级**，
同一个框架适用于作者、审稿人和编辑：

| 级别 | 定义 | 典型例子 | 合规要求 |
|---|---|---|---|
| **绿 · 允许**（辅助性） | 支持表达、组织或效率，**不影响**科学判断 | 语言润色、建议章节结构、翻译、比较方法学选项、压力测试研究问题、数据清洗去重 | 允许。**声明能增强信任与透明度** |
| **黄 · 谨慎**（评价/解释性） | 可能影响解释、框架、强调或评价判断，但仍在人的控制下 | 建议分析/实验/方法学方案；撰写解释性摘要；**把结果与已有文献比较**；**大量文字编辑或写作支持**；探索性数据分析中的模式识别；用通俗语言解释统计模型输出；建议统计检验 | **允许，但必须有人监督、核验与透明声明**。若 AI 实质性影响了评价判断，责任必须明确由人承担 |
| **红 · 不允许** | 不透明、取代了可问责的人的工作、产生不可验证的输出、或损害保密性与诚信 | **生成假设/分析/结论并当作人做出来的**；伪造数据、引用或结果；**不声明就用 LLM 生成核心研究推理**；把作者身份或责任交给 AI；把同行评审交给 LLM；生成照片级真实图像（deepfake） | **不允许** |

四条核心期望（原文要点）：

- **人的问责不可转移**——对学术内容、评价和编辑决定的责任不能委托给 AI
- **AI 可以辅助，但不能取代学术判断**
- **透明建立信任**——公开声明 AI 使用情况能消除歧义
- **保密与数据保护是强制的**——稿件、评审意见和敏感数据不得上传到不安全的公共 AI 系统

### 1.2 这对你这篇论文意味着什么（说实话）

用 AI 起草整篇稿件，落在**黄区**（"大量文字编辑或写作支持"、"撰写解释性摘要"），
甚至可能触及红区（如果 AI 参与了研究推理而没声明）。

**结论很清楚：声明。** 不声明是红区，声明了最多是黄区且完全合规。
二者的风险差了一个数量级——不声明被抓是撤稿 + 学术不端记录，声明了什么事都没有。

同时必须做到：

- **每一条科学论断你自己能负责**。审稿人问"为什么用这个模型"，
  你必须能用人话答上来，不能说"AI 选的"。红区里最重的一条就是
  "generating hypotheses, analyses or conclusions and presenting them as
  human-derived"——**把 AI 生成的结论当成人做出来的，是不允许的**。
- **数据、引用、图表由你核过**。伪造数据/引用/结果是红区。
- **不要把稿件上传到不安全的公共 AI 服务**（这条主要针对审稿人，
  但作者用公共工具处理未发表数据同样有风险）。

### 1.3 ICMJE 的要求（医学刊普遍遵循，工程刊也常引用）

ICMJE 的措辞更具体，直接规定了**写在哪里**：

| AI 用途 | 声明位置 |
|---|---|
| **写作辅助**（writing assistance） | **致谢（Acknowledgements）** |
| **数据收集、分析或图件生成** | **方法（Methods）** |
| 全部情况 | **投稿信（cover letter）** 和 **稿件本身** 都要写 |

其他要点：

- 聊天机器人（如 ChatGPT）**不能列为作者**，也不能被引用为作者
- 人类对提交的任何含 AI 辅助技术的内容**负责**
- 必须仔细审阅与编辑 AI 的输出——"AI 能生成听起来很权威但错误、不完整或有偏见的输出"
- 作者须保证论文（含 AI 生成的文字与图像）**无抄袭**，引用材料须有完整出处

### 1.4 声明模板

**Acknowledgements 里（写作辅助）**：

> **Use of generative AI.** During the preparation of this manuscript the
> author(s) used [工具名与版本] to assist with language editing and to
> structure the manuscript. All scientific content, analyses, interpretation
> and conclusions are the authors' own. The author(s) reviewed and edited all
> output and take full responsibility for the content of this publication.

**Methods 里（数据处理/绘图）**：

> **Use of generative AI.** [工具名] was used to assist with [具体用途，如
> 代码调试、绘图脚本编写]. All results were verified by the authors against
> the raw simulation outputs.

**Cover letter 里（必写）**：

> The authors disclose the use of [工具名] for [用途]. All scientific
> content and conclusions remain the authors' own, and the authors take full
> responsibility for the manuscript.

**没用 AI 就不要写这几句。** 多写反而引起不必要的注意。

### 1.5 投稿前必查

1. 目标刊作者指南里 "Use of AI" / "Generative AI" / "AI Tools" 那一节
2. 声明放在哪个位置（Acknowledgements / Methods / 独立的 Declaration 段）
3. 有没有要求填**单独的 AI 使用声明表**
4. 图件是否用了 AI 生成——**很多刊对 AI 生成图像有额外限制或直接禁止**

---

## 二、选刊（第 14 步）

### 2.1 核查清单（逐项都要有来源）

| 要查什么 | 去哪查 | 坑 |
|---|---|---|
| 是否 SCIE 收录 | Clarivate **Master Journal List** | **不要只看中介网站或期刊自己的宣传** |
| 分区 | JCR（JIF 分区）；注意 **JIF 四分位 vs CiteScore 四分位 vs 中科院分区** 是三套不同的东西 | 同一个刊在大类分区和小类分区可能差一档 |
| APC | 期刊官网 "Open Access" / "Article Publishing Charge" 页 | **很多 Q4 是全 OA 要收钱；Q2/Q3 订阅制刊往往免费**——这是个反直觉的坑 |
| 接收情况 | 期刊官网 "Journal Metrics" / 编委报告 | 有些刊不公布 |
| 掠夺性刊 | DOAJ（白名单）、Think.Check.Submit. | 收到"约稿"邮件要提高警惕 |
| 审稿周期 | 期刊 metrics、同行的经验 | 影响你投哪个 |

### 2.2 匹配度怎么判断（比看分区有用）

1. 该刊**近两年**有没有发过同类文章？（没有 → 大概率桌拒）
2. 那些文章的方法与你的接近吗？（差太远 → 审稿人不好找）
3. 该刊的 aims & scope 里有没有覆盖你的方向？
4. 该刊平均篇幅、图表数量、引用数量与你的稿子匹配吗？

### 2.3 分区的现实

- 分区越高，**桌拒率越高**，而且桌拒通常不给理由。
- 投高分区期刊前，先用它的 **presubmission enquiry**（如果有）问一句，
  比投出去等两周被桌拒划算。
- 被拒后能不能改投？可以，但**必须按新刊要求重排格式**，
  不能直接换个封面就投（编辑看得出来）。

---

## 三、投稿材料清单（第 20 步）

按目标刊要求逐项勾，通用清单：

- [ ] **Cover letter**（见第四节）
- [ ] **正文**（含标题页：题目、作者、单位、通讯作者联系方式、ORCID）
- [ ] **摘要** + 关键词
- [ ] **图件**（按刊要求：单文件 or 正文内嵌；矢量 PDF / TIFF）
- [ ] **图注**（有些刊要求图注单独成节放在参考文献后）
- [ ] **表格**（可编辑，不要贴图）
- [ ] **补充材料**
- [ ] **声明段**：数据可得性、代码可得性、利益冲突、资金、作者贡献（CRediT）、
      伦理审查（如涉及）、AI 使用（如适用）
- [ ] **推荐审稿人**（见第五节）
- [ ] 所有作者的 **ORCID** 与确认邮件

### 数据与代码可得性（Nature 系的要求，其他刊趋势相同）

Nature Portfolio 的要求可以直接当模板用：

- **数据可得性声明是强制的**，必须让读者清楚"理解、验证和延伸这项研究所需的最小数据集"
  如何获取
- 优先存放在公共仓储：**Figshare、Zenodo、Dryad**（或学科专用仓储）
- **不建议**把大数据集塞进补充材料
- **代码可得性声明**是独立的一节，位置在**数据可得性之后、参考文献之前**
- 代码建议存到能发 DOI 的仓储（**Zenodo、Code Ocean**），并**作为正式引用列进参考文献表**
- 建议用 OSI 认可的开源许可证
- 若代码对结论至关重要，**同行评审期间就要提供给编辑和审稿人**

**给本项目的直接建议**：把仿真脚本 + 派生数据 + 出图脚本一起打包传 Zenodo，
拿一个 concept DOI，写进数据/代码可得性声明，并在参考文献里正式引用这个数据集。
本项目此前已经预留了占位符，提交前替换即可。

---

## 四、Cover letter（第 18 步）

### 4.1 编辑真正想看的三件事

1. **这篇论文做了什么**（一句话，不要铺垫）
2. **为什么值得这个刊的读者读**（不是"很重要"，而是"解决了什么问题"）
3. **为什么适合这个刊**（引该刊近期一篇同类文章，说明读者群重合）

### 4.2 结构（一页以内）

```
[日期]

Dear Dr. [编辑姓名] / Dear Editor,

第一段：投稿声明
  我们提交题为 "..." 的稿件，希望考虑作为 [文章类型] 发表在 [期刊名]。

第二段：一句话讲做了什么
  我们研究/提出了 ... ，用 ... 方法，得到了 ... 。

第三段：2-3 条具体贡献（每条带数字）
  1. ...
  2. ...
  3. ...

第四段：为什么适合这个刊
  该刊近期发表的 [作者, 年] 关注 ... ，我们的工作与之一致并推进了 ... 。

第五段：声明
  本稿为原创，未在别处发表，未同时投给其他期刊。所有作者同意投稿，
  无利益冲突。[如有 AI 使用，在此声明。]

  推荐审稿人（可选）：...

此致
[通讯作者姓名、单位、邮箱、ORCID]
```

### 4.3 不要做的事

- 不要复述摘要（编辑会自己读摘要）
- 不要写"本研究具有重大意义"这类空话——换成具体的量
- 不要超过一页
- 不要群发式称呼（能查编辑名字就查，查不到用 "Dear Editor"）
- 不要忘了写 AI 使用声明（如果适用）

---

## 五、推荐审稿人

- 数量：通常 3–5 位
- **不能推荐**：同一单位的、近三年合作发表过的、导师/学生关系、有利益冲突的
- 适合推荐：在相关方向发过论文、但与你无合作关系的研究者
- 提供：姓名、单位、**机构邮箱**（不要给 gmail 之类的个人邮箱）、
  一句话说明为什么合适
- 编辑不一定会用，但**没有推荐名单会被视为不专业**

---

## 六、审稿流程与状态（第 20、21 步）

| 状态 | 含义 | 你该做什么 |
|---|---|---|
| Submitted | 已提交 | 等 |
| With Editor / Editor Assigned | 编辑在初筛 | 等；超过 2 周可礼貌询问 |
| **Desk Reject** | 编辑直接拒，不进外审 | 通常几天内；看有没有给理由，没有就换刊 |
| Under Review | 送外审了 | 等；周期从几周到几个月不等 |
| Required Reviews Complete | 审稿意见齐了 | 等编辑决定 |
| Decision in Process | 编辑在写决定信 | 等 |
| Major Revision | 大修 | 认真改，逐条回；改完要重跑去 AI 与总检 |
| Minor Revision | 小修 | 别大意；小修也可能被拒 |
| Reject with Option to Resubmit | 拒但欢迎重投 | 视为大修，改透 |
| Transfer Offer | 建议转投姊妹刊 | 看你愿不愿意 |

**催稿**：超过期刊公布的平均周期，可以发一封简短礼貌的询问信。
不要频繁催。

---

## 七、返修回复（第 21 步）

### 7.1 点对点回复信的结构

```
Dear Editor and Reviewers,

We thank the reviewers for their careful reading. We have revised the
manuscript accordingly. Our point-by-point responses follow; reviewer
comments are in italic, our responses in roman, and all changes are marked
in the revised manuscript.

Reviewer 1

Comment 1.1: [原文照抄审稿意见]
Response: [感谢 → 你怎么理解这条意见 → 你做了什么 → 在正文哪一页哪一行改了]
Changes: Page 7, lines 210-218; also new Table 4.

Comment 1.2: ...
```

### 7.2 每条回复的固定四段

1. **感谢**（一句，不要过度）
2. **复述你对意见的理解**（显示你读懂了；若意见有歧义，在这里说明你的理解）
3. **你做了什么**——附**具体位置**（页/行/图/表号）
4. **如果没改，说清为什么**——用证据，不要用情绪

### 7.3 不要做的事

- ❌ 只回"已修改"而不说改了哪里
- ❌ 为了显得听话而改坏本来对的地方——审稿人也会错，**有理有据地说明比盲从更受尊重**
- ❌ 一份回复信里提到另一位审稿人的意见（审稿人之间是互盲的）
- ❌ 大改未要求改的部分（会引入新问题，也让编辑难判断改了什么）
- ❌ 改完不做第 19 步复查——**返修加入的新文字同样会带机器味，而且正是审稿人重点读的地方**

### 7.4 返修后的回环（重要）

```
收到意见
   ↓
逐条修改正文
   ↓
第 19 步：对「改动的章节」重跑去 AI 痕迹扫描
   ↓
第 20 步：对「改动的章节」重跑引用/数字/图号核验
   ↓
提交修改稿 + 回复信 + 修改标记稿
```

---

## 出处

- Springer Nature / Nature Portfolio — *Artificial Intelligence (AI)* editorial
  policy（三级风险框架、四条核心期望、角色责任）：
  https://www.nature.com/commsphys/editorial-policies/ai
- ICMJE — *Defining the Role of Authors and Contributors*，第 II.A.4 节
  "Artificial Intelligence (AI)-Assisted Technology"：
  https://www.icmje.org/recommendations/browse/roles-and-responsibilities/defining-the-role-of-authors-and-contributors.html
- Nature Portfolio — *Reporting standards and availability of data, materials,
  code and protocols*（数据与代码可得性）：
  https://www.nature.com/nature-portfolio/editorial-policies/reporting-standards
- Nature — *Formatting guide*：
  https://www.nature.com/nature/for-authors/formatting-guide
- COPE — *Authorship and AI tools*（立场声明；抓取时返回 403，需人工核）：
  https://publicationethics.org/guidance/cope-position/authorship-and-ai-tools

> 原始抓取文本（含 HTTP 状态码与日期）保存在 `_sources/`。
> COPE 页面抓取时被 WAF 拦截，本文件未引用其具体措辞——**投稿前请人工打开核对**。

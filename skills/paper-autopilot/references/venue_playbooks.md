# 目标刊写法手册（第 14、15 步作业指导）

> Nature 部分的数字来自 `nature.com/nature/for-authors/formatting-guide` 原文（已抓取留存）。
> Science / Cell 的页面被 WAF 拦截无法直接抓取，相关条目已标注**待人工核**——
> 投稿前请打开官网确认，不要按本文件的转述投出去。

---

## 一、先问一个问题：你投的是哪一类刊？

写法和结构完全取决于答案：

| 类型 | 代表 | 读者 | 摘要 | 篇幅观 |
|---|---|---|---|---|
| **综合顶刊** | Nature / Science / Cell | 全学科，包括非本行科学家 | ≤200 词，一句话讲结论 | 极短，图表极少 |
| **学科旗舰** | Nature Physics、Cell Reports、PRL… | 本学科全体 | 200–250 词 | 短 |
| **专业顶刊** | MSSP、JSV、IJMS、Acta Mater.… | 本方向同行 | 200–300 词 | 中等，公式与图多 |
| **应用/工程刊** | IJAMT、Proc IMechE、JVET… | 本领域工程人员 | 200–250 词 | 中等偏长，强调可实施性 |

**投综合顶刊和专业刊是两种文体**，不能把一篇 IJAMT 的稿子改改投 Nature，
也不能把 Nature 的稿子改改投 IJAMT——后者会因为"没有可复现的细节"被拒。

---

## 二、Nature / Nature Portfolio（已核实）

### 2.1 文章类型与篇幅

| 类型 | 篇幅 | 图表 | 参考文献 |
|---|---|---|---|
| **Article**（物理科学） | 印刷约 6 页，正文约 **2500 词** | **4 个**中等尺寸图表 | **≤50 条** |
| **Article**（生物/临床/社科） | 印刷约 8 页，正文约 **4300 词** | **5–6 个**中等尺寸图表 | ≤50 条 |
| 一页纯文字 | 约 1250 词 | — | — |

- "中等尺寸图表"= 含图注约占**四分之一页**（约等于 270 词）。
- 一张多面板组合图若需要占半页，正文要相应缩短（半页 ≈ 600 词）。
- **字数只算正文**——题目、作者、致谢、参考文献不计入。
- Methods **不计入**正文字数，单独计算，**通常不超过 3000 词**。

### 2.2 摘要（summary paragraph）—— 这是 Nature 最独特的写法

原文要求：

- **不超过 200 词**，且**要有引用**
- 与正文分开，**避免出现数字、缩写、首字母缩略语和测量值**，除非必不可少
- 面向**本学科之外的读者**
- 固定四段式结构：

| 段 | 内容 | 篇幅 |
|---|---|---|
| 1 | 该领域的**基础性**介绍 | 2–3 句 |
| 2 | 背景与研究动机 | 简要 |
| 3 | **主要结论**，用 "**Here we show**" 或其等价说法引出 | 1–2 句 |
| 4 | 把主要发现放进更广阔的语境，说明领域因此前进了什么 | 2–3 句 |

**注意**：这与工程刊摘要完全不同。工程刊摘要通常是
"背景 → 本文做了什么 → 关键结果（带数字）→ 意义"，
而 Nature 要求**给外行看的、不带数字的、有引用的**四段式。

不要硬套。投 Nature 系就按 Nature 的写法；投工程刊就按工程刊的写法。

### 2.3 稿件顺序（Nature Article，原文规定）

```
Title
Authors
Affiliations (+ present addresses)
加粗的第一段（就是 summary paragraph）
Main text
Main references
Tables
Figure legends
Methods
  ├─ 数据可得性声明（独立）
  └─ 代码可得性声明（独立）
Methods references
Acknowledgements
Funding statement
Author contributions
Competing interest declaration
Additional information（补充材料说明行、通讯作者行）
Extended Data figure/table legends
```

**注意几个特殊点**：

- **图表放在参考文献之后**，不在正文里（初投可以文图合一，定稿必须分开）
- **Methods 在正文和图注之后**，且在 PDF 和 HTML 版里有、**印刷版里没有**
- **Methods 里不能放图和表**（重要的图表移到 Extended Data 或补充材料）
- Methods 用**简短的加粗小标题**分节，鼓励单独设 statistics / reagents / animal models 小节

### 2.4 参考文献

- **顺序编号**，按在正文、表格、图注、Methods、Extended Data 中出现的先后排
- 正文引用为**上标数字**（不加方括号，除非会和上标混淆）
- **正文最多 50 条**；Methods 和补充材料的引用**不计入**这个数，且**接续编号**，
  列在 Methods 之后
- 每个编号**只能列一篇文献**
- 只收：已发表、已被接收、或已上传到认可预印本平台（arXiv、bioRxiv）的
- 作者数超过 5 位时**只列第一作者 + et al.**
- 期刊名**斜体并缩写**；卷号**加粗**；**必须有文章标题**
- 数据集有 DOI 就可以进参考文献表
- 预印本可以进参考文献表

### 2.5 语言风格要求（原文）

- 面向**其他学科**的读者，也面向**英语非母语**的读者
- **尽量避免技术行话**；不可避免时要解释
- **缩写越少越好**，尤其是非标准缩写
- 题目和摘要尤其要写得任何科学家都能读懂
- 专业术语要简洁解释，**但不要说教**

### 2.6 致谢的写法（原文，很能说明 Nature 的调性）

> 致谢要简短。**不要感谢匿名审稿人和编辑**，不要写废话，不要写溢美之词。
> 可以感谢某人提供了帮助，但不要写"出色的帮助"；可以感谢某人提了意见，
> 但不要写"深刻的意见"。

这条对中文作者尤其重要——中文写作习惯里的敬语和铺垫，在 Nature 系是减分项。

---

## 三、Science / Cell（**待人工核实**）

> 以下为通行认知，**未经本次抓取验证**。science.org 与 cell.com 均返回 403。
> 投稿前必须打开官网核对。

### Science（Research Article / Report）

- 结构：Abstract（一段）+ **One-sentence summary**（一句话，给目录用）
- 正文按 Introduction / Results / Discussion / Materials and Methods 组织
- 图表数量严格受限，超出部分进 Supplementary Materials
- 参考文献按编号顺序，风格与 Nature 不同（作者姓名格式、期刊缩写规则不同）
- **Methods 放在正文之后**，或部分移入 Supplementary

### Cell / Cell Press

- 要求 **Highlights**：3–4 条，**每条不超过 85 个字符**（含空格）
- 要求 **eTOC blurb**（目录用一句话）
- 要求 **Graphical abstract**
- 结构：Introduction / Results / Discussion / STAR Methods
- **STAR Methods** 是 Cell Press 特有的结构化方法格式，
  含 Key Resources Table、Experimental Model and Subject Details、
  Method Details、Quantification and Statistical Analysis
- Lead contact 与 author contributions 要求明确

**共同点**：这三家都要求"一句话讲清结论"的东西（summary / one-sentence summary /
highlights），而且都对正文篇幅极其吝啬。写这类稿子的第一课是**删**。

---

## 四、工程类专业刊（MSSP / JSV / IJMS / IJAMT / Proc IMechE 等）

这一类没有统一规定，但有几条共通的、决定生死的：

### 4.1 结构

```
Title / Authors / Affiliations
Abstract（200–250 词，含具体数字）
Keywords（4–6 个）
Nomenclature（部分刊要求，符号表）
1 Introduction（背景 → 已有工作 → 缺口 → 本文贡献）
2 Problem formulation / Model
3 Method（数值方法、求解设置、验证）
4 Results and discussion
5 Conclusions
Declarations（数据可得性、利益冲突、资金、作者贡献）
References
Appendix（长的推导放这里）
```

### 4.2 这一档刊最看重什么

| 看重 | 不看重 |
|---|---|
| **可复现性**：参数给全、单位明确、求解设置写清 | 华丽的语言 |
| **验证**：和你比对的解析解/文献值/实验 | 只有漂亮结果的算例 |
| **与已有工作的定量对比** | 泛泛说"比现有方法好" |
| **工程意义**：这个方法怎么用、成本多少、边界在哪 | 纯数学上的精巧 |
| 图表清晰、可读 | 图多图少 |

### 4.3 常见的桌拒理由（工程刊）

1. **超出范围**（scope mismatch）——最常见，且往往不给理由
2. **没有验证**：只有仿真，没和任何东西对过
3. **增量太小**：只是把已有方法换了个工况
4. **参数不全**：别人照着重做不出来
5. **写作太差**：语法错误多到读不懂（这在非英语母语投稿中很常见）

**第 1 条的现实含义**：投之前一定确认该刊近两年发过同类文章。
这一条比影响因子重要得多。

### 4.4 与顶刊的写法差异（同一份工作，两种写法）

| | 综合顶刊写法 | 工程刊写法 |
|---|---|---|
| 开篇 | 从领域大问题讲起 | 从具体工程问题讲起 |
| 摘要 | 不带数字，给外行看 | **必须带具体数字** |
| 方法 | 详细部分进 Methods / SI | **方法细节是正文核心** |
| 验证 | 可以放 SI | **必须在正文，而且要单独成节** |
| 结论 | 强调对领域的推进 | 强调**可用性与边界** |
| 局限 | 简短 | **必须诚实、具体** |

---

## 五、第 15 步怎么做（目标期刊深度学习）

1. **下载该刊作者指南**，逐条抄成 checklist
2. **下载该刊近两年的 3–5 篇同类文章**，只看四件事：
   - 摘要的结构与长度、有没有数字
   - Introduction 最后一段怎么列贡献
   - 结果部分怎么组织（按什么分组）
   - 局限性写在哪、写了什么
3. **建一个"他们怎么说"的短语表**：
   把该刊常用的句式抄下来（例如 "The results demonstrate that…"、
   "A good agreement is observed between…"），写作时照着用。
   这比任何"润色"都有效——用目标刊自己的语言习惯写，天然就不像机器。
4. **对照检查格式**：摘要字数、关键词数、引用风格（编号/作者-年）、
   要不要 nomenclature、图表数量上限、声明项。
5. **字数统计按该刊口径**（算不算摘要、算不算参考文献、算不算图注）。

---

## 六、通用写作原则（跨刊适用）

1. **一段一个意思**。段落第一句是该段的主张，后面是支撑。
2. **先给结论再给理由**（尤其在 Results）。不要让读者读到段尾才知道你要说什么。
3. **具体打败笼统**。"降低了 21%" 永远优于 "显著降低"。
4. **主动语态优先**（Discussion 和 Introduction），方法部分可保留被动。
5. **动词承载信息**。少用 "performed an analysis of"，直接写 "analysed"。
6. **术语一致**。同一件事全文用同一个词，不要同义词轮换。
7. **符号一致**。变量斜体、单位正体、单位与数值间留空格（`15 mm`、`37 °C`）。
8. **删掉所有读起来"顺得像模板"的句子**——那通常就是没有信息量的句子。

---

## 出处

- Nature — *Formatting guide*（篇幅、摘要结构、稿件顺序、参考文献、致谢规则）：
  https://www.nature.com/nature/for-authors/formatting-guide
- Nature Portfolio — *Reporting standards*：
  https://www.nature.com/nature-portfolio/editorial-policies/reporting-standards

**未核实**：Science（science.org）与 Cell Press（cell.com）的作者指南页面
在本次抓取时返回 HTTP 403，第三节内容为通行认知而非原文，
**投稿前必须人工打开官网核对**。核对后请把实际要求更新回本文件。

# 第 19 步 · 终稿去 AI 痕迹与合规声明（详细作业指导）

> 这是流水线里**最后一道写作工序**，位置在第 18 步（Cover Letter）之后、
> 第 20 步（投稿前总检）之前。顺序不能颠倒——原因见第五节。
>
> **本文件的每条动作都标了证据等级**：
> `[S]` 同行评审研究实测 · `[P]` 预印本实测 · `[G]` 权威写作指南 ·
> `[D]` 编辑社群/厂商文档 · `[U]` 未查证（实践惯例）。
> 完整的证据底账与来源见附带的 `_sources/AI_detection_evidence.md`。

---

## 一、先把两件事分清（不弄清楚，后面全错）

| | 做什么 | 能不能做 |
|---|---|---|
| **A. 文体打磨** | 把机器写作的**风格特征**改掉，让文字读起来像同行写的 | **必须做** |
| **B. 隐瞒 AI 使用** | 期刊政策要求声明时不声明 | **绝对不能做** |

### 1.1 分界线不在"改得多狠"，而在"是否披露"

政策原文判据：

| 机构 | 原文 | 含义 |
|---|---|---|
| **Elsevier** | "Basic checks of grammar, spelling and punctuation do not need a declaration statement. **However, when an AI tool makes substantive changes to sentence structure or organization of a part of the text, this should be disclosed.**" | 改动一旦触及**句子结构或段落组织**——**这正是去 AI 痕迹的核心动作**——就触发披露义务 |
| **COPE** | "Authors who use AI tools **in the writing of a manuscript** … must be transparent in disclosing … how the AI tool was used and which tool was used." | 写作过程中用了 AI 就要披露**用途和工具名** |
| **ICMJE** | 期刊**应当要求**作者披露是否使用了 AI 辅助技术，并描述如何使用——**在投稿信和稿件本身两处** | 披露是双向的 |
| **Springer Nature** | 三级风险框架；另写明 "beyond copyediting, **we do not permit** the use of AI for content generation" | 不强制声明 ≠ 可以隐瞒 |

**结论，精确表述：**

- **(a) 为文体而编辑** + **按政策披露** = 被明确许可甚至鼓励。
  Elsevier 明说 AI 可用于 "improving language and readability"；
  ICMJE 明说 "Authors should carefully review and **edit** the result"。
- **(b) 以规避披露为目的的编辑** = 与上述所有政策文本直接冲突。
- **同一套动作，披露了是 (a)，为了藏起来做就是 (b)。**
- ⚠️ 若目标刊**禁止 AI 生成内容**（如 Nature Portfolio 的红线），
  那么把 AI 生成的正文改写后当作人类原创提交，**本身就是违规**——
  **编辑不能治愈来源违规**。这种情况必须提示作者自己重写。

### 1.2 不披露的实际后果（有据可查）

《Ethics & Behavior》2025 年分析了 Retraction Watch 收录的撤稿案例，
其中 **91 例涉及未声明的 AI 生成内容**：

- 用途分布：**新增内容 49%、重组既有内容 33%、语言与格式检查 18%**
- 位置分布：**引言/文献综述 34%、结果与讨论 31%、方法 22%**

也就是说，**"只是做语言检查"也占了 18%**——这和 Elsevier "基础语法拼写检查
无需声明" 的口径有张力（来源冲突，已记录）。**保守做法：有疑问就声明。**

### 1.3 硬性行为约束（做这一步时必须遵守）

1. 每次交付去 AI 编辑结果，**必须同时输出一份可粘贴的 AI 使用声明草稿**
   （工具名 + 用途 + 责任承担），并提示作者核对目标刊的具体政策。
2. **不得**提供规避披露的建议；不得删除或模糊化 AI 使用的记录。
3. 目标刊是"允许辅助写作但强制披露" → **照常编辑 + 照常披露**。
4. 目标刊**禁止** AI 生成内容 → **不得**把 AI 生成的正文改写后包装为人类原创。
5. **不得以"通过某个检测器"作为编辑目标或验收标准**——理由见第三节。

### 1.4 声明模板

**Acknowledgements（写作辅助）**：

> **Use of generative AI.** During the preparation of this manuscript the
> author(s) used [工具名与版本] to assist with language editing and to
> structure the manuscript. All scientific content, analyses, interpretation
> and conclusions are the authors' own. The author(s) reviewed and edited all
> output and take full responsibility for the content of this publication.

**Methods（数据处理 / 绘图 / 代码）**：

> **Use of generative AI.** [工具名] was used to assist with [具体用途].
> All results were verified by the authors against the raw simulation outputs.

**Cover letter（必写）**：

> The authors disclose the use of [工具名] for [用途]. All scientific content
> and conclusions remain the authors' own, and the authors take full
> responsibility for the manuscript.

**没用 AI 就一个字都不要写。**

---

## 二、先建"目标期刊基线"——这一步决定了后面所有判断

**这整套方法的正确用法不是"对照固定阈值"，而是"对照你自己建的期刊基线"。**

同一项特征在不同语料里差异极大（例：破折号在人类文本中的密度区间是
**0.33–17.12 次/千词**，跨度超过 50 倍），拿全局阈值卡必然误判。

**建基线的做法**：

1. 从目标期刊**近 1–2 年**同类文章中抽 **8–20 篇**（最好同体裁：都是研究论文）
2. 把这些文章转成纯文本
3. 跑一次扫描，得到该刊的**特征区间**：

```bash
python scripts/prose_scan.py baseline/ --json 19_deai/journal_baseline.json
```

4. 再跑自己的稿子，**只处理落在基线区间之外的特征**

```bash
python scripts/prose_scan.py manuscript/ --strict --json 19_deai/scan_before.json
```

**`--baseline` 参数**可以把两步连起来：

```bash
python scripts/prose_scan.py manuscript/ \
    --baseline 19_deai/journal_baseline.json \
    --strict --json 19_deai/scan_after.json
```

> 拿不到期刊全文时（订阅制、无权限），退而求其次：
> 用该刊的**开放获取文章**，或该刊已发表文章的**摘要集合**建基线。
> 摘要也算——它们出自同一批编辑和审稿人之手。

---

## 三、判定项、参考项，以及哪些"特征"其实不成立

### 3.1 证据强度排序（先看这个，别把民间说法当铁律）

| 特征 | 证据强度 | 说明 |
|---|---|---|
| **句长更均匀 / 更短** | **较强** | 意大利语议论文语料：AI 每句词数 SD **7.08** vs 人类 **14.01**（p≈0）；EMNLP 2025：GPT-4 平均句长 **18.21** vs 人类 **23.53**。**但**有一篇研究方向相反，且 EMNLP 原文说"没有清晰模式"——**只能作组合判据，不能单点定案** |
| **句尾 `, -ing` 附加评论** | **较强** | 多篇文献一致报告 LLM 过度使用 |
| **名词化** | **较强** | Biber 特征分析：名词化在 **LLM 过度使用 Top 5** 之列 |
| **"in conclusion" 类模板化段首** | **较强** | 有研究显示同一模型生成的所有文章结论段开头完全相同 |
| **LLM 高频词（delve/underscore/showcase…）** | **较强** | Kobak 等（Science Advances 2025）对 **14,448,711 篇** PubMed 摘要的统计分析：`delves` 超额率 **28.0 倍**、`underscores` 10.9、`showcasing` 10.2 |
| **段落长度均匀** | **未查证** | 唯一找到的量化对比 n=4/组、p=0.974，不显著。**"LLM 段落更均匀"没有给出效应量的同行评审研究** |
| **em dash 滥用** | **半民间说法** | GPT-4.1 未受限时 10.62 次/千词 vs 人类均值 3.23，**但人类区间 0.33–17.12 完全覆盖了模型区间**；Llama 全系列为 0.00。维基百科《Signs of AI writing》已在 2026-09 把它标注为"疑似历史指标" |
| **规则三连（rule of three）** | **未查证** | 只有编辑社群文档，**没有同行评审的频次研究** |
| **TTR / 词汇多样性** | **方向不一致** | 有研究报告人类 > GPT-3 但 < GPT-4；TTR 的判别力来自**分布形状**而非高低 |
| **可读性指标** | **不成立** | PLOS ONE 2026：9 个可读性公式**跨学科全部无显著差异** |

**所以脚本里这些项的处理是**：

- **判定项** = 有证据支持、且不会在正常科技英语上误报的
- **参考项** = 报数但不判定（规则三连、名词化、被动）
- **观察项** = 只报数，自己跟基线比（MSTTR、破折号密度、句均长、段落均长）

---

### 3.2 `prose_scan.py` 的判定项

| 指标 | 门槛 | 依据 |
|---|---|---|
| 句子长度变异系数（burstiness） | > 0.40 | `[S]` 最强单项信号 |
| AI 式附加衔接词（每 100 句） | < 2.0 | `[G]` moreover/furthermore/additionally… |
| 同一句首最长重复次数 | ≤ 4 | `[S]` 模板化段首 |
| 跨文件重复整句 | = 0 | `[S]` 复制粘贴痕迹 |
| LLM 高频词（每 1000 词） | < 8.0 | `[S]` Kobak 等超额词表 |
| 句尾 -ing 附加评论（每 100 段） | < 2.0 | `[S]` 多篇文献一致 |
| 宣传性词汇（每 1000 词） | < 1.0 | `[G]` |
| 模糊归因（每 100 段） | < 1.5 | `[G]` 无出处的断言 |
| 叠加式模糊限定 | = 0 | `[S]` "may potentially be somewhat…" |

### 3.3 参考项与观察项（**不要**当作必须清零的指标）

- **段落长度变异系数**：报数，但**不作为判定项**——它没有同行评审的效应量支持。
  段落长短交错仍然是好文风，所以建议改，但**不要为了凑一个数字去硬拆段落**。
- **破折号密度**：报**次/千词**，和基线比。**不要一律清零**——
  人类作者也用破折号（区间上限 17.12 次/千词）。
- **规则三连**：只报数。
- **名词化**：报数；LLM 确实过度使用（`[S]`），但工程论文本身就名词化密集，
  要和基线比。
- **被动语态**：报数。**当心反向信号**——如果你的被动比例明显**低于**期刊基线，
  说明你可能"过度主动化"了，这本身也是特征。方法部分保留被动是正常的。
- **MSTTR / TTR**：与文体和篇幅强相关，不给阈值。

### 3.4 词表里哪些有据、哪些是推测

`EXCESS_VOCAB` 词表的**主要来源**是 Kobak 等 2025 关于 PubMed 摘要超额词的研究。
但要注意：

- ✅ **有实证**：`delve/delves/delving`、`underscore(s/ing)`、`showcase(s/ing)`、
  `intricate/intricacies`、`pivotal`、`realm`、`meticulous`、`garner`、
  `interplay`、`multifaceted`、`holistic` + `landscape`（Liang 2024）
- ⚠️ **未经上述清单直接确认**：`leverage`、`testament`、`robust`
  ——这三个是**广泛流传但本次未能核实**的，脚本里保留是因为它们同时也是
  第 3.3 节意义上的"宣传腔/空泛词"，删掉也不损失信息，但**不要把"用了 leverage"
  当成 AI 证据**。

**词表可以按学科增补**：把你自己方向里"审稿人看到就皱眉"的套话加进
`EXCESS_VOCAB`。这部分是经验，标成 `[U]` 就好。

---

## 四、为什么不要把"通过检测器"当验收标准

这条必须单独说，因为它直接关系到你的论文安全。

**检测器的实测表现**：

| 证据 | 数字 |
|---|---|
| Liang 等 2023（同行评审） | 7 个检测器对 **91 篇托福作文**的平均误判率 **61.22%**；同批 **88 篇美国八年级作文**仅 **5.19%**。**97.80% 的托福作文至少被一个检测器判为 AI** |
| 同上 | 把词句改写之后，误判率降到 11.77% |
| IJEI 2026（同行评审） | 宏观准确率：Turnitin **0.61**、Originality.ai **0.69**，两者宏观 F1 均 **< 0.55**；**混合文本近乎完全失效**；**理工科文本准确率暴跌到 0.51 / 0.58** |
| Acta Neurochirurgica 2025 | 250 篇 ChatGPT 出现**之前**的真实论文：Corrector 误判 **30.4%**、ZeroGPT **16%** |
| 厂商自报 | Turnitin 称 >20% AI 文档 FPR<1%，同时声明"**不得作为行动的唯一依据**" |

**三个直接结论**：

1. **对非英语母语作者存在系统性误判**。61% vs 5% 这个对比，就是冲着你这样的
   作者来的。写得"太规整"的英文会被判成 AI。
2. **理工科文本检测准确率只有五成左右**——约等于抛硬币。
3. **没有任何一家出版社把检测器当作裁决依据**。COPE、ICMJE、Elsevier、
   Springer Nature 的共同底线是**披露**与**作者担责**。

**所以**：不要去"过检测器"。要做的是**把文字改到和目标期刊的基线一致**，
并且**如实披露**。这两件事都做到了，检测器判什么都无关紧要。

---

## 五、为什么这一步必须在"投稿前总检"之前

去 AI 痕迹会**改写句子**。改写句子会动到：

- 句子里的数字（"reduced by 21 %" 可能被顺手写成 "20 %"）
- 引用标号的位置（删一句可能把 [12] 一起删掉）
- 图表号（"Figure 3 shows" 被改写后可能变成 "Figure 2"）
- 量纲与单位

所以顺序固定为：

```
第 19 步  去 AI 痕迹（改文本）
   ↓
第 20 步  投稿前总检（对改完的文本重跑：引用、数字、图表号逐条核）
   ↓
投稿
```

**反过来做，等于检查了一份你不会投出去的稿子。**

同理：**每轮返修后，对改动章节重跑第 19 步，再对改动章节重跑第 20 步。**
返修加入的新文字同样可能带机器味，而且正是审稿人重点读的地方。

---

## 六、操作清单（30 条可执行动作）

> 每条后面的方括号是证据等级。§3.1 说过哪些特征证据强、哪些弱——
> **优先做证据强的那些**。

### A. 句子层

1. 逐段点数句长；把连续 3 句以上长度相近（差值 <5 词）的句子中，
   至少一句拆成短句（≤8 词）或并成 30 词以上的长句。`[S][G]`
2. **合并相邻短句**——把同段中并列的 2–3 个短句用冒号、分号或
   `because`/`although` 合成一句。
   **实验证明这是单项最有效的对抗动作。** `[S]`
3. 删掉所有 `, highlighting…` / `, underscoring…` / `, emphasizing…` /
   `, showcasing…` 句尾分词短语，改成独立从句或直接删。`[S]`
4. 把 `That … is/was …` 开头的句子改成正常主谓句。`[S]`
5. 检查被动比例：与期刊基线比。若**明显低于**基线，把 1–2 处改回被动，
   免得出现"过度主动化"的反向信号。`[S]`
6. 把 `the effect observed in X` 这类过去分词后置定语改成关系从句。`[S]`

### B. 段落与结构层

7. 统计每段句数；若全篇都是 4 句，把至少 2 段改成 2 句或 6–7 句。`[G][U]`
8. 删掉所有段首"总起句"——只重复小标题或预告下文、不含信息的那种。`[G]`
9. 按论证顺序重排段落，不要沿用"背景—现状—问题—对策"的模板顺序。`[G]`
10. 删掉模板化的结论开头，特别检查是否每节都以同一句式起头
    （例如全部 `In conclusion,`）。`[S][G]`
11. 重写论点句/贡献句，确保是**具体的、可反驳的断言**，
    而不是"X 既有优势也有挑战"这种两头堵的表述。`[G]`

### C. 词汇层

12. 全局搜索并替换：`delve into`、`showcase`、`underscore`、`intricate`、
    `pivotal`、`realm`、`testament to`、`landscape`、`underscores the importance of`。
    逐个换成**本领域的具体术语**或直接删。`[S][P]`
    （`leverage` / `robust` / `crucial` 也建议检查，但它们的超额性**未核实**）
13. **把名词化还原为动词**：`implementation of` → `implement`；
    `utilization of` → `use`；`assessment of` → `assess`；
    `the reduction of` → `we reduced`。LLM 确实过度使用名词化 `[S]`；
    目标是降到期刊基线附近。
14. 删掉冗余 additive 连接词（`Moreover,` / `Furthermore,` / `Additionally,` /
    `In addition,`），改为直接陈述或改用因果/对比关系。`[G]`
15. **补上让步与转折从属连词**（`although`、`though`、`whereas`、`while`）——
    文献报告这是 LLM **使用不足**的结构。`[S]`
16. 在**你确实不确定**的地方补上情态与认识立场标记
    （`may`、`might`、`appears to`、`we suspect`、`it is plausible that`）。`[S]`
    ⚠️ 不要为了凑数而加——只在真有不确定性的地方加。
17. 降低 `-ing` 分词修饰密度。`[S]`
18. 拆掉抽象名词堆叠（`the enhancement of the optimization of…`），改写成动词句。`[S]`

### D. 内容层（信息密度与可验证性）

19. 每处泛化断言补一个具体数字（样本量、效应量、单位、温度、时间窗）。`[G]`
20. 每处"某某方法被广泛使用"补具体出处。`[G]`
21. 把泛化动词换成可复现操作：`analyzed` → `ran a two-way ANOVA`；
    `evaluated` → `measured by X at Y`。`[G]`
22. 核对所有参考文献真实存在、引用内容与原文一致。
    **这是 ICMJE 明确列为不可委托给 AI 的作者责任。** `[S]`
23. 在方法与结果中补入**只可能来自实际工作的细节**
    （求解器版本、网格规模、异常值处理、失败的尝试）。`[G]`

### E. 标点与排版层

24. 统计破折号密度（次/千词），与期刊基线比较。
    **仅在明显高于基线时**替换部分为逗号/分号/括号——**不要一律清零**。`[P]`
25. 确认破折号前后无多余空格（AI 生成常见 `" — "` 形式）。`[D]`
26. 清除所有弯引号（`“ ” ‘ ’`），按期刊模板统一。`[D]`
27. 删掉加粗强调与标题式大小写（期刊模板要求处除外）；
    把"粗体+冒号"的伪列表改写成连续散文。`[D]`
28. 删除所有 emoji、`Let's dive in`、`Here's what you need to know` 类
    对话式引导语与结尾客套。`[D]`

### F. 校验层

29. **朗读全文**。任何读起来不像本领域学者会说的话，重写该句。`[G]`
30. 改完重算所有特征，确认落在期刊基线区间内。
    **不要以"通过某检测器"作为验收标准。** `[S]`

---

## 七、执行流程

1. **备份**：`cp -r manuscript manuscript_pre_deai`。改坏了能回退。
2. **建期刊基线**（第二节）。
3. **基准扫描**：`prose_scan.py manuscript/ --json 19_deai/scan_before.json`
4. **逐节改写**：按第六节的动作表改，**优先做证据强的**。
   一节点一次扫描，别攒着。
5. **复扫**：`--strict` 判定项全 PASS，且特征落在基线区间内。
6. **对照检查**（最容易被跳过，但最重要）：
   - diff 逐段看改了哪些句子
   - **每处数字逐一确认没被改错**
   - **每处引用标号确认还在**
   - **每处图表号确认没变**
7. **写 AI 使用声明**（第 1.4 节模板），放进目标刊要求的位置。
8. **换一双眼睛**：隔一天再读，或换一个模型/同事读。
   刚改完的时候你看什么都是对的。
9. 交给第 20 步。

---

## 八、通过标准

- `prose_scan.py --strict` 判定项**全部 PASS**
- 特征值**落在自建期刊基线区间内**
- 改写前后的**数字 / 引用 / 图表号逐条对得上**
- AI 使用声明**已写、位置正确、措辞符合目标刊模板**
- **没有为了"像人写的"而降低信息密度**——删掉的必须是废话，不是内容
- **没有以"过了检测器"为由结案**

最后一条要特意说：**去 AI 痕迹不是把文章改短改空，而是把空话换成实指。**
一篇信息密度高、每个论断都带具体数字和出处的文章，天然就不像机器写的——
因为机器写不出你实验里的那些具体细节。

---

## 九、没有脚本 / 没有工具时怎么裸做

1. 打开正文，逐段问三个问题：
   - 这一段有没有一句可以删掉而信息不减？（有 → 删）
   - 这一段里有没有一个具体数字，还是全是定性描述？（没有 → 补，或标为待补）
   - 这一段和上一段是不是同一个句式开头？（是 → 换）
2. 全局搜 `Moreover` / `Furthermore` / `Additionally` / `Notably` / `Importantly` /
   `It is worth noting`，逐个删或改。
3. 全局搜 `delve` / `underscore` / `showcase` / `pivotal` / `intricate` /
   `realm` / `meticulous` / `testament` / `interplay` / `crucial` / `landscape`，
   换成实指。
4. 全局搜 `studies have shown` / `researchers have found` / `it is widely believed`，
   要么补文献，要么删句。
5. 全局搜 `, highlighting` / `, underscoring` / `, emphasizing` / `, showcasing`，
   全删或改写。
6. 全局搜 `may ` / `might ` / `could `，看有没有一句里出现两个以上。
7. 全局搜破折号，数出密度（次/千词），**和手边同刊文章比**，
   只在明显偏高时改。
8. 朗读全文。
9. 写披露声明。

---

## 附：证据底账

本文件的全部实证数字、来源 URL、以及**未能核实项与来源冲突**
（包括同篇论文表格与正文自相矛盾、句长方向跨研究相反、
连接词方向与编辑指南相反、非母语偏差方向依工具而异等 7 组冲突）
见 `_sources/AI_detection_evidence.md`。

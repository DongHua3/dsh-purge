# 文献检索与真实性核验（第 02、03、07、08、19、20 步作业指导）

> **本文件配套脚本**：`scripts/litsearch.py`（真实检索 + 参考文献核验）
>
> 核心规则一句话：
> **论文里出现的每一条参考文献，都必须能被 `litsearch.py verify` 确认为真实存在，
> 元数据正确，且未被撤稿。做不到的，一条都不能引。**

---

## 一、铁律：不许编，也不许"看起来像真的"

编造参考文献有几种形态，**全部禁止**：

| 形态 | 例子 | 为什么必须禁 |
|---|---|---|
| **整条虚构** | 编一个作者、标题、期刊、卷页，看起来很合理 | 审稿人一查就露，直接拒稿 |
| **拼凑** | 把 A 的作者、B 的标题、C 的期刊凑成一条 | 同上，而且更难辩解 |
| **真实文献配错 DOI** | 文献是真的，DOI 是猜的 | 点开链接跳到别的文章，比虚构更尴尬 |
| **张冠李戴** | 文献真实存在，但内容不支持你引它来说的那句话 | 这是**最常被抓**的一种——见第四节 |
| **引用已撤稿文献** | 文献确实存在，但已被撤稿 | 撤稿文献的结论不可信，引用它 = 立场问题 |
| **凑数引用** | 为了凑参考文献数量，加几篇没读过的 | 审稿人问细节就答不上来 |

**本机能力**：`litsearch.py` 能自动查前四种里的大部分（虚构、拼凑、错 DOI、撤稿），
第五种（张冠李戴）需要人工确认，第六种靠自觉。

---

## 二、工具：`litsearch.py`

### 2.1 真实检索（第 02、03 步）

```bash
python scripts/litsearch.py search \
    --query "magnetorheological elastomer dynamic vibration absorber rotor" \
    --source openalex,crossref,pubmed,europepmc,arxiv,doaj \
    --limit 50 --out refs/search_20260920.json
```

**已实测可用的数据源**：

| 数据源 | 覆盖 | 速度 | 备注 |
|---|---|---|---|
| `openalex` | 全学科，2.5 亿+ 作品 | ~1.5 s | 有摘要、被引数；**首选** |
| `crossref` | 全学科，DOI 注册库 | ~2 s | 元数据最权威；**核验首选** |
| `pubmed` | 生物医学 | ~1.4 s | E-utilities，官方 |
| `europepmc` | 生物医学 + 预印本 | ~1 s | 含全文链接 |
| `arxiv` | 物理/数学/CS 预印本 | ~0.8 s | 预印本，**要标明** |
| `doaj` | 开放获取期刊 | ~0.9 s | 判断期刊是否正规 |

**Semantic Scholar 默认不用**：无 API key 时返回 HTTP 429。有 key 就设
`LITSEARCH_S2_KEY`。

**速率**：脚本内置 0.34 s 最小间隔 + 退避重试，并带 `mailto`（OpenAlex/Crossref
的 polite pool）。**不要绕过这两个做并发轰炸**，会被封。

### 2.2 核验参考文献（第 19、20 步，也可随时跑）

```bash
python scripts/litsearch.py verify \
    --refs manuscript/references.md \
    --out refs/citation_verify.json
```

判定结果五种：

| 判定 | 含义 | 处理 |
|---|---|---|
| `VERIFIED` | 定位到真实文献，元数据对得上 | 可以用 |
| `FIX` | 文献真实，但年份/作者/刊名/DOI 有出入 | 按 `fix` 字段改正 |
| `NOT_FOUND` | 查不到 | **不能引**，删掉或换成真实文献 |
| `RETRACTED` | 已撤稿 | **绝对不能引**，删除 |
| `UNVERIFIED` | 未能确认（如完全离线） | 标 `UNVERIFIED` 并写进交付说明 |

**核验逻辑（按证据强度排序）**：

1. **有 DOI 且能解析** → 以注册库记录为准，不再用标题去猜。
   只做年份与第一作者姓氏的合理性检查。
2. **没有 DOI，或 DOI 解析不到** → 用多个候选标题检索 Crossref + OpenAlex，
   相似度 **≥0.72** 才认。
3. **都不匹配** → `NOT_FOUND`。

DOI 解析不到这件事**本身就是强信号**——说明这个 DOI 很可能是编的。

### 2.3 撤稿检查

```bash
python scripts/litsearch.py retract --doi 10.1016/j.micpro.2020.103576
python scripts/litsearch.py retract --refs manuscript/references.md
```

用的是 **Crossref Labs 的 Retraction Watch 数据**（19.7 万条索引）。
第一次跑会把 66 MB 的数据集下到 `~/.cache/litsearch/` 缓存起来，之后离线可用。

### 2.4 其他

```bash
# 解析单个 DOI 的权威元数据
python scripts/litsearch.py doi 10.1126/sciadv.adt3813

# 谁引用了这篇（找相关工作、判断影响力）
python scripts/litsearch.py cited-by --doi 10.1126/sciadv.adt3813

# 导出成引用管理器能吃的格式
python scripts/litsearch.py export --in refs/search.json --style ris
```

---

## 三、写论文时的正确流程

```
第 02 步  生成三档检索式
              ↓
第 03 步  litsearch.py search  →  refs/search_*.json   ← 真实检索，不是凭记忆
              ↓
第 06 步  筛选（按标题/摘要），记入 SELECTION.csv
              ↓
第 07 步  export → ris/bibtex，导入引用管理器
              ↓
第 08 步  精读，笔记里记下「哪句话出自哪篇的哪一页」
              ↓
第 11–13 步 写作   ← 每一处引用都指向一个已核验的条目
              ↓
第 19 步  去 AI 痕迹（会改文字，可能动到引用标号）
              ↓
第 20 步  litsearch.py verify  →  refs/citation_verify.json
              ↓
          selfcheck.py 会检查这个报告；有 NOT_FOUND/RETRACTED 就是阻断项
```

**关键**：`refs/citation_verify.json` 是第 20 步的**必需产出**，
`autopilot.py done` 缺它会拒绝前进，`selfcheck.py` 也会阻断。

---

## 四、最难的一种：张冠李戴

工具查不出"这篇文献到底支不支持你这句话"。**这一条必须人工过。**

做法：精读笔记里对每个要引用的论断记三样东西：

```
论断：MRE 的剪切模量随磁场单调增大并在高场饱和
出处：Kallio et al. 2007, Smart Mater. Struct. 16, 506 — p. 508, Fig. 4
原话："the storage modulus increases with magnetic field and saturates above ~0.5 T"
```

写正文时**直接从这个笔记里搬**，不要凭印象写。
`selfcheck.py` 查不出这个，但审稿人能——而且这是最伤信誉的一种错误。

**三个自查问题**（写完引用后逐个问）：

1. 我真的读过这篇吗？（没读过就删掉，或去读）
2. 这篇里的原话/原图支持我这句话吗？（把页码写进笔记）
3. 如果审稿人问"你为什么引这篇"，我能说出它具体讲了什么吗？

---

## 五、预印本、数据集、网页怎么处理

| 类型 | 能不能引 | 怎么标 |
|---|---|---|
| 期刊论文 | 能 | 正常引 |
| **预印本**（arXiv/bioRxiv） | 能，但要谨慎 | **必须标 "Preprint"**；优先换成正式发表版 |
| 会议论文 | 能 | 注明会议名与年份 |
| **数据集**（有 DOI） | 能 | DataCite 格式：作者、标题、仓储名、DOI |
| 软件/代码 | 能 | 存 Zenodo 拿 DOI，列进参考文献 |
| 网页 | 尽量不引 | 必须引时给作者、页面标题、URL、访问年份 |
| **AI 生成的内容** | **绝对不能引** | 不能把 AI 列为作者，也不能"引用 AI" |
| 撤稿文献 | **绝对不能引** | — |
| 查不到的文献 | **绝对不能引** | — |

---

## 六、给 agent 的执行纪律

1. **不许凭记忆写文献。** 任何一条参考文献都必须先经过 `litsearch.py`。
2. **`litsearch.py` 说查不到，就是不能引。** 不要"再想想"、不要换个写法让它看起来能查到。
3. **DOI 不许猜。** 只能从检索结果里复制。解析不到的 DOI 一定不要留在稿子里。
4. **预印本要标明。** 不要把 arXiv 预印本写成期刊论文。
5. **`script` 报告的核验状态要原样写进交付说明**，
   包括 `NOT_FOUND` / `UNVERIFIED` / `FIX` 各多少条。
6. **完全离线时**：把该步标为降级（`skip --reason "无网络，文献未核验"`），
   **不要假装核验过**。降级会被 `selfcheck.py` 检查并要求写进交付说明。

---

## 七、环境与依赖

| 需要 | 说明 |
|---|---|
| `requests` | 联网检索 |
| 网络 | 至少能访问 `api.openalex.org` 与 `api.crossref.org` |
| 磁盘 | 撤稿库缓存约 66 MB（`~/.cache/litsearch/`） |

**环境变量**：

- `LITSEARCH_MAILTO` — 填你自己的邮箱，进 OpenAlex/Crossref 的 polite pool，**建议设**
- `LITSEARCH_CACHE` — 缓存目录，默认 `~/.cache/litsearch`

**已实测**（本机，2026-09）：

```
OpenAlex search            200    1.9s
Crossref search            200    2.1s
Crossref DOI               200    0.9s
PubMed E-utilities         200    1.4s
Europe PMC                 200    1.0s
arXiv                      200    0.8s
DOAJ                       200    0.9s
Retraction Watch           200   19.9s  (66 MB, 首次下载后走缓存)
Semantic Scholar           429          (无 key 不可用，默认不启用)
```

## 八、一次真实的核验记录（本机实测）

拿一份**故意掺假**的参考文献表跑核验：

```
[OK  ] [1] Delving into LLM-assisted writing in biomedical publications...   ← 真实，正确
[OK  ] [2] GPT detectors are biased against non-native English writers...    ← 真实，正确
[MISS] [3] Adaptive magnetorheological elastomer vibration absorber...       ← 编的
       ! DOI 10.1016/j.jsv.2019.116131 在两个数据源都解析不到 —— 这个 DOI 很可能是编的
       ! 最接近的候选只有 0.51 相似度，不足以确认是同一篇
[MISS] [4] A novel quantum-enhanced magnetorheological damper...            ← 编的
       ! DOI 10.1038/s41586-021-99999-9 解析不到
[OK  ] [5] Points of view: Color blindness                                   ← 真实，正确

VERIFIED 3 · NOT_FOUND 2 → 2 条不能直接引用
```

再拿一条**真实但已撤稿**的文献：

```
[RETR] [1] Application of Embedded Network Distributed Network in Student...
       ! **这篇文献已被撤稿，不能作为依据引用**（撤稿日期 2/9/2024，性质 Retraction）
       -> year 应为：2021
       -> authors 应为：Sui, Yong; Yao, Fuguang
```

**编的查得出来，撤稿的也查得出来。** 这就是"论文里的东西必须真实"的技术保障。

---

## 九、用真实手稿校准的过程（这节很重要）

工具写完后，我拿**本项目那份已经完成的手稿**（22 条参考文献）跑了一遍核验。
第一轮结果：**VERIFIED 1 / FIX 20 / NOT_FOUND 1**。

看着像"稿子有 20 处错"。**但其中 19 处是我自己的误判。**

| 误判 | 原因 | 修法 |
|---|---|---|
| 第一作者姓氏全错（「y」「t」「g」「av」…） | 稿子用的是 **"Bently DE"、"Den Hartog JP"** 这种「姓+首字母」格式，我原来的解析取最后一个 token，取到了首字母 | 识别**尾部首字母组**：末尾 token 若只由大写字母和连字符组成，就是首字母，姓氏在它前面 |
| 刊名全对不上 | 稿子写 **"Smart Mater. Struct."、"Int J Mech Mater Des"**（缩写，还省掉了 and/of/the），注册库是全称 | 改成**按词前缀匹配**：注册库刊名的每个实词都要在条目里找到前缀相容的伙伴 |
| 图书/会议文献的"刊名"对不上 | 注册库把书的"容器"写成出版社或会议名 | 识别 `book` / `proceedings-article` / `standard` 等类型，**跳过刊名比对**，作者顺序差异降为提示 |
| ASME V&V 20-2009 判成"查不到" | **标准与技术报告根本不在 Crossref/OpenAlex 里** | 新增 `MANUAL_CHECK` 判定，单独提示"去发布机构官网核对" |
| 年份 2011 vs 2010 判成错误 | 注册库记的是**在线首发年**，稿子写的是**正式卷期年** | 相差恰好一年时降为提示，并说明原因 |

修完之后：**VERIFIED 21 / MANUAL_CHECK 1（就是那条 ASME 标准）**，
**零误判**，且剩下的那条提示是真实需要人工确认的。

**这段经历本身就是一条纪律**：

> **一个会误报的检查器比没有检查器更糟。**
> 它会让作者去"修"根本没坏的地方，也可能让人干脆不信任这个工具。
> **任何核验工具的判定门槛，都必须拿已知合格的样本校准过。**
> 校准时要问的不是"它报了多少问题"，而是"它报的问题里有多少是真的"。

本项目那条 `[21] 2011 vs 2010` 的提示，就是校准后剩下的**真问题**——
需要作者按目标刊的引用规范决定取哪一年。工具的价值在这里体现出来了。

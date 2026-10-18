# 技能对照表与裸做回退

流水线的每一步在**理想情况**下可以调用一个现成技能；在**没有装任何技能**的 AI 上，
按同一节的「裸做」流程用基础工具做完，效果一样，只是慢一点。

**先跑一次环境探测**，知道手上有什么：

```bash
python scripts/check_env.py
```

下表左列是技能名（不同技能库叫法不同），中列是它干什么，右列是**没装时怎么办**——
右列才是这份流水线可移植的关键。

> **本机已核实的技能名**（`C:\Users\ASUS\.dsh\skills`，用
> `Get-ChildItem C:\Users\ASUS\.dsh\skills -Directory` 逐个核对过，下表标 ✓ 的都在）。
> 换机器后请重新核一遍——**名字对不对得上不影响能不能干活，影响的是走"调用技能"
> 还是走"裸做"**。

---

## 检索与文献

| 技能名（可能的名字） | 用于哪一步 | 没装时怎么办 |
|---|---|---|
| `nature-academic-search` ✓、`research-lit` ✓、`literature-review` ✓、`paper-lookup` ✓ | 02 03 | 用 **OpenAlex** / **Crossref** 公开 API（免登录、免 key）<br>`https://api.openalex.org/works?search=<q>&per-page=50`<br>`https://api.crossref.org/works?query.bibliographic=<q>&rows=50`<br>PubMed 用 E-utilities，arXiv 用 `http://export.arxiv.org/api/query` |
| `openalex` ✓、`semantic-scholar` ✓、`deep-research` ✓ | 02 03 | 同上；`scripts/litsearch.py search` 已把它们封成一条命令 |
| `citation-management` ✓、`pyzotero` ✓ | 03 07 | 维护一个 `refs.csv`（键名/作者/年份/标题/期刊/DOI），正文引用直接用键名 |
| `literature-management` ✓、`meta-abstract-screener` ✓ | 06 | 用 CSV 手工筛：标题过一遍、摘要过一遍，两列理由 |
| `literature-close-read` ✓、`nature-paper-card` ✓ | 05 08 | 每篇只读摘要 + 验证小节 + 图表标题，写 5 行笔记 |
| `novelty-check` ✓、`idea-discovery` ✓ | 04 | 做"他们做了什么 / 没做什么 / 为什么没做"三栏表 |
| `citation-audit` ✓、`nature-ref-verifier` ✓、`citation-formatter` ✓ | 19 | 逐条查 Crossref：`https://api.crossref.org/works/<doi>` 看标题作者年份对不对 |
| `nature-downloader` ✓、`pmc-official-download` ✓、`find-paper-references` ✓ | 07 | 拿不到全文就标"仅摘要"，不要假装读过 |
| `format-references-zotero` ✓、`format-references-endnote` ✓、`bib-formatter` ✓ | 13 19 | GB/T 7714 表由 `scripts/build_refs.py` 从 `refs.csv` 生成，不依赖这些技能 |

## 写作与润色

| 技能名 | 用于哪一步 | 没装时怎么办 |
|---|---|---|
| `nature-writing` ✓、`academic-paper` ✓、`scientific-writing` ✓ | 11 12 13 | 照 `references/writing_rules.md` 的章节骨架自己写 |
| `humanizer` ✓、`humanizer-academic` ✓、`polish-zh` ✓、`content-proofreading` ✓ | 16 | 跑 `python scripts/prose_scan.py`，按报告做具体修改动作 |
| `sci-mech-fluid-polishing` ✓（机械/流体方向）、`mechanical-engineering-research` ✓ | 15 16 | 抄目标刊近两年文章的表达习惯，建一个"他们怎么说"的短语表 |
| `method-writing` ✓ | 12 | 方法部分按"别人照着重做需要什么"来写 |
| `nature-polishing` ✓、`nature-reviewer` ✓、`academic-paper-reviewer` ✓ | 16 21 | 自己按"审稿人最可能打的三处"逐条自问自答 |
| `nature-response` ✓、`rebuttal` ✓ | 21 | 三栏表：意见 / 回复 / 改动位置 |

## 中文学位论文成品层（本技能自己的活）

| 技能名 | 用于哪一步 | 没装时怎么办 |
|---|---|---|
| `thesis-pipeline` ✓ | 全程（本技能的主要来源之一） | 本包已内联它的成品层脚本，直接跑 `scripts/build_docx.py` 等 |
| `docx` ✓、`documents` ✓、`docx-pro` ✓ | 13 19 20 | `python-docx` 生成 DOCX；`scripts/build_docx.py` 已实现学位论文排版口径 |
| `pdf` ✓、`pdf-processor` ✓ | 20 | `reportlab` 或 Word/WPS COM；中文记得**注册 CJK 字体**，否则全是空白方框 |
| `spreadsheet-ops` ✓、`xlsx` ✓ | 03 06 10 | `openpyxl` 或直接写 CSV（CSV 更通用） |
| `paper-deck` ✓、`pptx` ✓、`nature-paper2ppt` ✓、`paper-slides` ✓ | 答辩 PPT | 本科 12–18 页、每页一个要点；见 `references/chinese_thesis_format.md` 第七节 |
| `academic-norm-review` ✓、`paper-claim-audit` ✓、`experiment-audit` ✓ | 19 20 | `scripts/check_refs.py` + `scripts/wordcount.py` + `scripts/final_check.py` 覆盖同类检查 |

## 图表与可视化

| 技能名 | 用于哪一步 | 没装时怎么办 |
|---|---|---|
| `figure-legend-gen` ✓ | 10 | 图注四要素：画的是什么 / 数据怎么来的 / 误差棒是什么 / n 是多少 |
| `scientific-visualization` ✓、`nature-figure` ✓、`matplotlib` ✓、`intelligrapher` ✓ | 10 | 直接用 matplotlib；**换掉默认配色和默认字号**。中文图必须显式设 `font.sans-serif` |
| `figure-spec` ✓、`scientific-figure-generator` ✓、`paper-figure` ✓ | 10 | `scripts/figure_kit.py` 已做中文字体探测 + Okabe-Ito 色盲友好配色 + PNG/PDF 双输出 |
| `paper-poster-html` ✓、`latex-posters` ✓、`pptx-posters` ✓ | 汇报海报 | HTML/CSS 单文件海报；不在学位论文主链路里 |

## 选刊与投稿（仅 SCI 模式）

| 技能名 | 用于哪一步 | 没装时怎么办 |
|---|---|---|
| `journal-recommender` ✓、`journal-skills` ✓ | 14 | 查 Master Journal List 确认 SCIE 收录；查该刊近两年同类文章数；查 APC |
| `open-access-scout` ✓ | 14 | 逐刊看是否在 DOAJ / 是否被列入掠夺性刊名单 |
| `venue-templates` ✓、`academic-paper` ✓（format-convert） | 15 | 下载作者指南，抄成 checklist 逐条打勾 |
| `cover-letter-generator` ✓ | 18 | 照 `pipeline_steps.md` 第 18 步的五段结构写 |
| `overleaf-sync` ✓、`paper-compile` ✓ | 15 20 | 本地 LaTeX 编译；中文学位论文不走这条线 |

## 环境类

| 技能名 | 用于哪一步 | 没装时怎么办 |
|---|---|---|
| `academic-pipeline` ✓ | 00 总控 | 用 `python scripts/pipeline_state.py status` 代替 |
| `research-wiki` ✓ | 全程知识积累 | 用项目文件夹里的 `NOTES/` 就好 |
| `video-reader` ✓ | 学方法、看教程视频 | 装在本机 skills 根的独立技能，不在本包内；没装就不用 |

---

## 关于"技能名对不上"这件事

不同 AI 的技能库命名不同。**不要因为找不到某个技能名就停下来问用户**。
判断顺序是：

1. 列一遍本机技能名，找语义最接近的（`check_env.py` 会打印技能目录和数量）
2. 找不到就直接走"裸做"列
3. 只有当"裸做"也做不了（比如完全没有任何联网检索能力）时，才回来告诉用户缺什么

**永远不要**因为找不到技能就编一个技能名出来，或者假装调用了某个技能。

## 中文本科毕业论文的默认技能组合（本机实测可用的最小集）

| 步骤段 | 技能 | 备注 |
|---|---|---|
| 04 05 08 | `thesis-pipeline` + `literature-review` | 选题与对标精读 |
| 10 | `nature-figure`（或 `scientific-visualization`） | 出图；配色与字号别用默认值 |
| 11–13 | `nature-writing`（或 `academic-paper`） | 中文章节骨架见 `references/chinese_thesis_format.md` |
| 16 19 | `humanizer` + `polish-zh` | 先跑 `prose_scan.py` 再改，别边改边猜 |
| 20 | `docx` + `pdf` + `final_check.py` | 生成与终检 |
| 答辩 | `pptx`（或 `paper-deck`） | 12–18 页，留一页"研究局限" |

这张表是**默认值**，不是硬要求：任一项缺就按对应行的"没装时怎么办"裸做。

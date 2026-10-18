---
name: paper-autopilot
description: |
  论文全自动流水线（单技能，自带流程引擎、检索核验、数据溯源、成品构建脚本，不依赖其它技能）。
  给一句话方向，按 22 步自动走完「选题—检索—核验—证据—框架—数据—图表—写作—去AI痕迹—选刊/格式—投稿或答辩—交付」，
  全程不向用户提问，进度落盘可跨会话续跑。两种模式：SCI 英文期刊（IMRaD）与中文论文/学位论文
  （本科/硕士/博士/课程/开题，GB/T 7714 顺序编码制 + Word/PDF 成品）。
  触发词：写论文、帮我写论文、毕业论文、学位论文、本科论文、硕士论文、博士论文、课程论文、开题报告、
  写一篇SCI、全自动写论文、自动走完流程、接着上次的论文继续、论文进度、查文献、核验引用、排参考文献、
  生成Word/PDF、答辩PPT、检查能不能交、去AI味、润色、选刊、投稿、返修、答复信。
  English: write a paper, write a thesis, dissertation, manuscript, run the paper pipeline,
  continue my paper, verify citations, build the reference list, format for submission.
license: MIT
---

# 论文全自动流水线 · paper-autopilot

一句话方向进，成品出来。中文项目走中文成品层（Word/PDF + GB/T 7714），英文项目走 SCI 层（LaTeX/投稿包）。

## 开工判据（先判模式，再敲命令）

| 用户说的是 | 模式 | 第一条命令 |
|---|---|---|
| 毕业论文 / 学位论文 / 本科 / 硕士 / 博士 / 课程论文 / 开题报告 | **CN 模式**（默认） | `scaffold.py` 建骨架 → 再 `autopilot.py start` |
| SCI / 期刊 / 英文 / 投稿 / 影响因子 | **SCI 模式** | `autopilot.py start --direction "<方向>"` |
| 接着上次继续 / 进度到哪了 | **续跑** | 读 `PIPELINE.md` + `PAPER_STATE.json` → `autopilot.py status` |

模式只影响第 09–21 步的产出形态；第 00–08 步（选题、检索、证据）两种模式完全一致。

## 五条铁律

1. **不编数据、不编文献。** 数字必须能追到 `data/` 或代码；引用必须真检索、真核验。查不到写"未验证"，不补一个像真的。
2. **每步过闸。** `autopilot.py done` 会核查产出是否真存在且非空，缺文件拒绝前进。过不了闸就回头改，不带着问题往下走。
3. **不停下来提问。** 本该问用户的事，改成：自己选一个能自圆其说的 → 记进 `DECISIONS.md` → 继续。唯一允许停的三种情况见 `references/autopilot_contract.md`。
4. **去 AI 终检（第 19 步）必须排在投稿前总检（第 20 步）之前。** 终检会改句子，改句子会动数字、引用、图表号；先检后改等于检了一份不投的稿。
5. **降级可以，隐瞒不行。** 走不通的步子用 `skip --reason` 留痕，`selfcheck.py` 会查它有没有写进最终交付说明。没写＝阻断项。

## 主循环（三个命令）

```bash
PY=<带 requests/matplotlib/python-docx 的解释器>     # 见下节「依赖」
SK=<本技能目录>

python $SK/scripts/autopilot.py start --dir <项目目录> --direction "<方向或题目>"
python $SK/scripts/autopilot.py next  --dir <项目目录>   # 打印本步工单：产出路径 + 通过标准 + 该读哪份参考
python $SK/scripts/autopilot.py done  --dir <项目目录>   # 交工，核查产出后前进
```

`start` 自动定下刊/分区/篇幅/图表数/参考文献上限/论文类型/有无实验数据/作者占位符，全部记进 `DECISIONS.md`，事后可改。
`next` 的工单是**唯一权威指令**：照着做，不要自己想下一步做什么。
辅助：`skip`（降级留痕）、`decide`（记决策）、`check`（核对已完步骤产出）、`status`（完整进度）。

**降级必须留痕**：

```bash
python $SK/scripts/autopilot.py skip --dir <项目目录> --step 04 --reason "<为什么做不了>"
```

## 22 步

| 步 | 名称 | 步 | 名称 |
|---:|---|---:|---|
| 00 | 总控进度判断 | 11 | 摘要与引言 |
| 01 | 项目初始化（BRIEF） | 12 | 方法与结果 |
| 02 | 检索式生成 | 13 | 讨论与结论 |
| 03 | 检索与导出 | 14 | 目标刊选择 / 学位论文改为格式学习 |
| 04 | 选题与空白识别 | 15 | 格式规范核对 |
| 05 | 对标库深度学习 | 16 | 润色与去 AI 初检 |
| 06 | 文献筛选分类 | 17 | 图片版权 / 图表授权 |
| 07 | 导入引用库取全文 | 18 | Cover Letter / AI 使用声明 + 答辩问答 |
| 08 | 文献精读（证据表） | **19** | **终稿去 AI 痕迹 + 合规声明（不可跳）** |
| 09 | 论文框架搭建 | 20 | 投稿前总检（对 19 之后的文本） |
| 10 | 图表制作与引用 | 21 | 返修与回复 / 答辩与定稿 |

每步的产出物、通过标准、"本机没有对应技能时怎么裸做"：`references/pipeline_steps.md`（主参考）。
CN 模式每一步具体落什么文件、SCI 默认值怎么被改写、真实事故：`references/chinese_thesis_playbook.md`。

**别跳 05–08。** 看着像能跳，但 09 的框架和 11–13 的每一句引用都靠它们；跳了等于把编造风险留到最后。

## CN 模式成品层（六条命令）

```bash
python $SK/scripts/scaffold.py   --dir <项目目录> --title "论文题目" --type 本科
python $SK/scripts/figure_kit.py --data <数据.csv> --spec <图定义.json> --out figures/
python $SK/scripts/build_refs.py --csv refs.csv --manuscript manuscript/ --out 05_稿件/参考文献.md
python $SK/scripts/build_docx.py --config thesis.json --manuscript manuscript/ --out deliverables/论文.docx
python $SK/scripts/docx_to_pdf.py deliverables/论文.docx
python $SK/scripts/final_check.py --dir <项目目录> --write
```

成品层三条纪律：**md 是唯一真源**（docx/pdf 一律由脚本生成，绝不反向编辑）；**正文禁止手写数字**（由数据回填）；**分章存 md**（单文件整覆盖会把摘要整节写没，本项目真实发生过）。

## 依赖

| 用来做什么 | 需要 | 说明 |
|---|---|---|
| 检索核验 `litsearch.py` | `requests` | 缺它这一步直接报错退出 |
| 出图 `figure_kit.py` / `simulate.py` | `matplotlib` `numpy` `pandas` | 缺了只能出纯文本结果 |
| 统计 `uncertainty` 相关 | `scipy` | 缺了用自实现的蒙特卡洛 |
| Word / PDF `build_docx.py` `docx_to_pdf.py` | `python-docx` `pymupdf`（或 Word COM） | 缺了只能交 md |

**本机已验证可用的解释器**：`D:\py\Python311\python.exe`（requests 2.34 / matplotlib 3.11 / scipy 1.17 / python-docx 1.2 / pymupdf 1.28 全在）。
DSH 内置 python 缺 `requests`/`matplotlib`/`scipy`，只能跑流程驱动与成品层的一部分——**跑之前先确认解释器**。

## 换机器 / 换 AI / 隔了一个月回来，先跑这两个

```bash
python $SK/scripts/check_env.py                 # 本机有哪些工具、缺什么
python $SK/scripts/selftest.py                  # 真跑一次仿真 + 无人值守走完流程，最后打印 PASS
```

**看到 PASS 再开工。** 看不到 PASS 时按它打印的失败项修环境，不要硬跑。

## 按需加载（走到哪一步读哪一份，别一次全读）

| 文件 | 用途 |
|---|---|
| `references/autopilot_contract.md` | 全自动运行契约：唯一输入、主循环、不停提问、降级留痕、完成定义 |
| `references/pipeline_steps.md` | **22 步完整定义 + 通过标准 + 裸做流程（主参考）** |
| `references/chinese_thesis_playbook.md` | **CN 模式实操手册**：中文项目每步落什么、原型默认值改写表、真实事故库 |
| `references/chinese_thesis_format.md` | 中文学位论文格式规范（章-节-条、图表题注、页码、字体字号） |
| `references/literature_and_verification.md` | 文献检索与真实性核验、预印本与撤稿处理、张冠李戴的防范 |
| `references/simulation_and_data.md` | 仿真与数据溯源：模型自检、`.prov.json` 指纹、公差与蒙特卡洛 |
| `references/simulation_vv.md` | 代码验证 / 解验证 / 确认 / 不确定度量化（第 12 步） |
| `references/computational_paper_playbook.md` | 纯仿真论文怎么写才专业：验证阶梯、无实验时的证据、局限的写法 |
| `references/deai_protocol.md` | **第 16、19 步作业指导**：11 项判定、逐条改写动作、AI 声明模板 |
| `references/venue_playbooks.md` | Nature/Science/Cell 与工程刊的写法差异、结构、字数（第 14、15 步） |
| `references/figure_standards.md` | 图件尺寸/分辨率/字体/配色/误差棒规范（第 10 步） |
| `references/submission_and_compliance.md` | 选刊、投稿材料、审稿流程、AI 使用政策（第 14、18、20、21 步） |
| `references/writing_rules.md` | 章节骨架、证据纪律、局限写法 |
| `references/skill_aliases.md` | 同行技能对照表 + 没装技能时怎么裸做 |
| `references/packaging_and_migration.md` | 把本技能搬到另一台机器/另一个客户端的完整步骤 |
| `assets/` | `PIPELINE.md` / `PAPER_STATE.json` / `BRIEF.md` / `DECISIONS.md` 模板 + 一个跑通过的实战案例 |

脚本索引：`autopilot.py`（驱动）`pipeline_state.py`（底层状态）`litsearch.py`（检索核验）`simulate.py`（数据溯源）`prose_scan.py`（AI 腔扫描）`selfcheck.py`（内容自检）`selftest.py`（自测）`check_env.py`（环境探测）`scaffold.py`（骨架）`figure_kit.py`（出图）`build_refs.py`（参考文献表）`build_docx.py`（Word）`docx_to_pdf.py`（PDF）`final_check.py`（成品总检）`math2unicode.py`（公式转 Unicode）`wordcount.py`（字数与图表编号）`check_refs.py`（引用一致性）。

## 交付前不许跳的六项

1. `final_check.py --dir <项目> --write` 全绿（12 项：目录、字数、图表编号、引用对应、内容匹配、LaTeX 残留、公式编号、小节编号、数字一致、作者占位符、页数图表数、哈希）
2. `selfcheck.py` 无阻断项（占位符、数字溯源、引用核验报告、降级披露、去 AI 判定）
3. 悬空引用 0 / 孤立文献 0 / 引用与文献内容不匹配 0
4. 正文每个数字能追到 `data/` 下的文件或代码
5. 降级项已写进交付说明（没写＝阻断）
6. AI 使用声明（期刊/学校要求时）如实写

## 什么时候不要用这个技能

- 只查几篇文献 → 直接检索，不用建项目
- 只改一篇文章的格式 → 直接改
- 已有成稿只差投稿 → 从第 14 步进（`pipeline_state.py init --start 14`）
- 只担心 AI 痕迹 → 直接读 `references/deai_protocol.md` + 跑 `prose_scan.py`，不用起整条流水线

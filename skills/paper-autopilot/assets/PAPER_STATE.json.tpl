{
 "_note": "模板：PAPER_STATE.json（机器可读进度真源）。由 autopilot.py / pipeline_state.py 维护，不要手工编辑状态字段。本文件必须是合法 JSON——不要往里加注释。复制到 <项目>/PAPER_STATE.json 后替换 <尖括号> 占位符。",
 "schema": "paper-pipeline/1.3",
 "project_type": "<undergraduate_thesis | master_thesis | doctoral_thesis | course_paper | sci_article>",
 "title": "<论文题目>",
 "direction": "<方向>",
 "language": "<zh-CN | en>",
 "mode": "autopilot",
 "created_at": "<YYYY-MM-DDTHH:MM:SS+08:00>",
 "updated_at": "<YYYY-MM-DDTHH:MM:SS+08:00>",
 "current": "00",
 "completed": [],
 "brief": {
  "type": "<研究型毕业论文>",
  "venue": "<学位论文（无期刊投稿环节）>",
  "length_target": "正文 <字数目标> 中文字符",
  "length_actual": 0,
  "figure_budget": "<N> 图",
  "table_budget": "<M> 表",
  "ref_style": "GB/T 7714—2015 顺序编码制",
  "refs_cited": 0,
  "refs_extended": 0,
  "has_experiment": "<simulation-only | measured>",
  "data_kind": "<literature-calibrated semi-analytical model>",
  "authors": "占位符（待用户补真实姓名/学号/专业/导师/学院）",
  "deliverables": [
   "deliverables/<文件名>.docx",
   "deliverables/<文件名>.pdf"
  ],
  "pages": 0,
  "curve_points": 0,
  "design_points": 0
 },
 "steps": {
  "00": {"artifacts": ["00_总控进度判断/README.md"], "gate": "", "finished_at": ""},
  "01": {"artifacts": ["01_项目初始化/BRIEF.md"], "gate": "", "finished_at": ""},
  "02": {"artifacts": ["02_检索式生成/SEARCH_STRINGS.md"], "gate": "", "finished_at": ""},
  "03": {"artifacts": ["06_文献筛选分类/SELECTION.csv"], "gate": "", "finished_at": ""},
  "04": {"artifacts": ["04_选题与空白识别/TOPIC.md"], "gate": "", "finished_at": ""},
  "05": {"artifacts": ["05_对标库深度学习/BENCHMARK.md"], "gate": "", "finished_at": ""},
  "06": {"artifacts": ["06_文献筛选分类/SELECTION.csv"], "gate": "", "finished_at": ""},
  "07": {"artifacts": ["07_导入引用库取全文/PDF_STATUS.md"], "gate": "", "finished_at": ""},
  "08": {"artifacts": ["08_文献精读/EVIDENCE_TABLE.md"], "gate": "", "finished_at": ""},
  "09": {"artifacts": ["09_论文框架搭建/OUTLINE.md"], "gate": "", "finished_at": ""},
  "10": {"artifacts": ["figures/", "figures/FIGLIST.md", "data/"], "gate": "", "finished_at": ""},
  "11": {"artifacts": ["manuscript/part1_摘要与绪论.md"], "gate": "", "finished_at": ""},
  "12": {"artifacts": ["manuscript/part2_理论基础与模型.md", "manuscript/part3_数值试验设计.md"], "gate": "", "finished_at": ""},
  "13": {"artifacts": ["manuscript/part4_结果与分析.md", "manuscript/part5_结论展望与附录.md"], "gate": "", "finished_at": ""},
  "14": {"artifacts": ["14_目标期刊选择/VENUE.md"], "gate": "", "finished_at": ""},
  "15": {"artifacts": ["15_目标期刊格式学习/FORMAT_SPEC.md"], "gate": "", "finished_at": ""},
  "16": {"artifacts": ["16_润色与语言打磨/POLISH_LOG.md"], "gate": "", "finished_at": ""},
  "17": {"artifacts": ["17_图片版权/FIG_RIGHTS.md"], "gate": "", "finished_at": ""},
  "18": {"artifacts": ["18_Cover Letter/AI_USAGE_STATEMENT.md", "18_Cover Letter/DEFENSE_QA.md"], "gate": "", "finished_at": ""},
  "19": {"artifacts": ["19_终稿去 AI 痕迹与合规声明/COMPLIANCE.md"], "gate": "", "finished_at": ""},
  "20": {"artifacts": ["20_投稿前总检/"], "gate": "", "finished_at": ""},
  "21": {"artifacts": ["21_返修与回复/REVISION_CHECKLIST.md"], "gate": "", "finished_at": ""}
 },
 "gates": {
  "word_count": {"target": 0, "actual": 0, "pass": false},
  "figure_refs_contiguous": {"expected": "<1-1..N-M>", "actual": "", "pass": false},
  "citation_dangling": {"count": 0, "pass": false},
  "citation_orphan": {"count": 0, "pass": false},
  "latex_residue": {"count": 0, "pass": false},
  "pdf_pages": 0,
  "pdf_embedded_images": 0,
  "numerical_validation": {"specific_modulus_in_range": "<a/b>", "specific_strength_in_range": "<a/b>", "pass": false}
 },
 "decisions": [
  {
   "at": "<YYYY-MM-DDTHH:MM:SS+08:00>",
   "step": "01",
   "q": "<流水线自己问了什么>",
   "choice": "<选了什么>",
   "why": "<为什么这么选>",
   "how_to_change": "<想改的话动哪个文件>"
  }
 ],
 "log": [
  {"at": "<YYYY-MM-DDTHH:MM:SS+08:00>", "event": "start", "step": "00", "note": "<方向与体裁>"}
 ],
 "known_gaps": [
  "<未达标项 1，与 PIPELINE.md 的「未达标项」保持同一措辞>"
 ]
}

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""建立中文论文项目骨架（thesis-pipeline 第 1 步）

生成 22 个阶段目录 + 分章 md 模板 + refs.csv 模板 + thesis.json 排版配置。

用法：
    python scaffold.py --dir D:\\论文\\我的课题 --title "论文题目" --type 本科
    python scaffold.py --dir . --title "XXX" --type 硕士 --mode sci
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

STAGES = [
    "00_总控进度判断", "01_项目初始化", "02_检索式生成", "03_检索与导出",
    "04_选题与空白识别", "05_对标库深度学习", "06_文献筛选分类",
    "07_导入引用库取全文", "08_文献精读", "09_论文框架搭建",
    "10_图表制作与引用", "11_摘要与引言", "12_方法与结果", "13_讨论与结论",
    "14_目标期刊选择", "15_目标期刊格式学习", "16_润色与语言打磨",
    "17_图片版权", "18_Cover Letter", "19_终稿去 AI 痕迹与合规声明",
    "20_投稿前总检", "21_返修与回复",
]

EXTRA = ["code", "data", "figures", "manuscript", "deliverables", "refs"]

# 按论文类型给字数与章节建议
PROFILES = {
    "本科": dict(words=20000, chapters=5, abstract_cn=600, refs=40),
    "硕士": dict(words=35000, chapters=6, abstract_cn=800, refs=60),
    "博士": dict(words=60000, chapters=7, abstract_cn=1000, refs=100),
    "课程": dict(words=8000, chapters=4, abstract_cn=300, refs=15),
    "期刊": dict(words=12000, chapters=5, abstract_cn=300, refs=40),   # SCI 模式另走 paper-pipeline
}

THESIS_JSON = {
    "schema": "thesis-pipeline/1.0",
    "type": "本科",
    "title": "",
    "language": "zh-CN",
    "author": {"name": "〔待填：姓名〕", "sid": "〔待填：学号〕", "major": "〔待填：专业〕",
               "advisor": "〔待填：导师姓名/职称〕", "school": "〔待填：学院名称〕",
               "date": "〔待填：年 月 日〕"},
    "page": {"size": "A4", "margin_top_cm": 2.54, "margin_bottom_cm": 2.54,
             "margin_left_cm": 2.8, "margin_right_cm": 2.8},
    "fonts": {"body_cn": "宋体", "body_latin": "Times New Roman", "heading_cn": "黑体",
              "code_latin": "Consolas"},
    "sizes": {"body_pt": 12, "h1_pt": 16, "h2_pt": 14, "h3_pt": 12,
              "caption_pt": 10.5, "ref_pt": 10.5, "formula_pt": 11.5},
    "line_spacing_pt": 22,
    "first_line_indent_chars": 2,
    "figure_width_cm": 15.2,
    "manuscript_order": [
        "part0_摘要与目录.md", "part1_绪论.md", "part2_理论基础与模型.md",
        "part3_研究设计.md", "part4_结果与分析.md", "part5_结论展望与附录.md"
    ],
    "reference_style": "GB/T 7714-2015 顺序编码制",
    "notes": [
        "本文件控制 Word/PDF 排版；学校模板到手后按模板改这里，不要改脚本。",
        "md 是唯一真源，docx/pdf 由 build_docx.py 生成，禁止反向编辑。"
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser(description="建立中文论文项目骨架")
    ap.add_argument("--dir", required=True, help="项目目录（不存在则创建）")
    ap.add_argument("--title", required=True, help="论文题目")
    ap.add_argument("--type", default="本科", choices=list(PROFILES),
                    help="论文类型，决定字数与章节数建议")
    ap.add_argument("--mode", default="thesis", choices=["thesis", "sci"],
                    help="thesis=中文学位论文（本技能）；sci=英文期刊（转 paper-pipeline）")
    ap.add_argument("--force", action="store_true", help="目录非空时仍继续")
    args = ap.parse_args()

    root = Path(args.dir).resolve()
    if root.exists() and any(root.iterdir()) and not args.force:
        print(f"目录非空：{root}\n如需继续请加 --force（不会覆盖已存在的文件）")
        return 1
    root.mkdir(parents=True, exist_ok=True)

    made = 0
    for d in STAGES + EXTRA:
        (root / d).mkdir(exist_ok=True)
        made += 1

    prof = PROFILES[args.type]

    # thesis.json
    cfg = json.loads(json.dumps(THESIS_JSON))
    cfg["type"] = args.type
    cfg["title"] = args.title
    cfg["mode"] = args.mode
    cfg["targets"] = prof
    cfg["created_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    (root / "thesis.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")

    # 分章 md 模板（只补不覆盖）
    templates = {
        "part0_摘要与目录.md": f"""## 摘要

（写 300–500 字：研究对象、方法、主要结果 3–4 条、结论一句话。最后一段必须写明研究的范围与局限。）

**关键词**：关键词1；关键词2；关键词3；关键词4；关键词5

---

## Abstract

（与中文摘要对应，150–250 词。）

**Keywords**: keyword1; keyword2; keyword3; keyword4; keyword5

---

## 目录

（用 `python scripts/final_check.py --dir .` 会提示缺失章节；目录可手写或由脚本生成。）
""",
        "part1_绪论.md": f"""## 第 1 章 绪论

### 1.1 研究背景与意义

（说明领域现状、为什么做这个题。每个论断挂真实文献引用，如 [1]。）

### 1.2 国内外研究现状

（按主题分子节，不要按时间流水账。引用必须真实。）

### 1.3 现有研究的不足

（3 条以内，每条对应 1.4 节的一个研究内容。）

### 1.4 本文研究内容与技术路线

（列出研究内容，配技术路线图 图 1-1。）
""",
        "part2_理论基础与模型.md": """## 第 2 章 理论基础与模型

（理论推导与模型假设。公式按标准 LaTeX 语法书写并编号；build_docx.py 会自动转成可读文本。）

### 2.1 理论基础
### 2.2 模型假设
### 2.3 控制方程
""",
        "part3_研究设计.md": """## 第 3 章 研究设计

### 3.1 研究对象与参数

**表 3-1 参数设置**

| 参数 | 符号 | 取值 | 单位 | 依据 |
|---|---|---|---|---|
| | | | | |

### 3.2 方法
### 3.3 数据分析方法
### 3.4 可复现性说明

（数据由哪个脚本生成、随机种子、文件哈希。）
""",
        "part4_结果与分析.md": """## 第 4 章 结果与分析

### 4.1 结果一

（图用 `![](figures/fig4-1_xxx.png)` 插入，图题单独一行写成 `**图 4-1 标题**`。）

### 4.2 结果二
### 4.3 讨论
""",
        "part5_结论展望与附录.md": """## 第 5 章 结论与展望

### 5.1 主要结论

（逐条对应第 4 章的结果，不要出现第 4 章没有的结论。）

### 5.2 研究局限

（**第一条必须是最根本的局限**，不要放在最后轻描淡写。）

### 5.3 后续工作展望

---

## 致谢

（务必如实说明 AI 使用情况。）

---

## 附录 A 核心代码

## 附录 B 数据文件清单与复现方式
""",
    }
    for name, body in templates.items():
        p = root / "manuscript" / name
        if not p.exists():
            p.write_text(body, encoding="utf-8", newline="\n")

    # refs.csv 模板
    rc = root / "refs.csv"
    if not rc.exists():
        rc.write_text(
            "id,作者,年份,标题,期刊,DOI,类型,主题分类,是否核心,备注\n"
            'L001,"Smith J; Doe A",2024,"Paper title here","Journal Name",'
            '10.xxxx/xxxxx,journal,主题,是,"DOI 已经 Crossref 核实"\n',
            encoding="utf-8-sig")

    # PIPELINE.md 起头
    pl = root / "PIPELINE.md"
    if not pl.exists():
        pl.write_text(
            f"""# 流水线进度 · {args.title}

- **类型**：{args.type}　**模式**：{"中文学位论文" if args.mode == "thesis" else "SCI 英文期刊"}
- **字数目标**：{prof['words']}　**参考文献目标**：{prof['refs']}
- **创建**：{cfg['created_at']}

进度表由 paper-pipeline 的 autopilot.py 维护；本文件可手工补充说明。

## 下一步

1. `python ~/.dsh/skills/paper-pipeline/scripts/autopilot.py start --dir . --direction "{args.title}"`
2. 填 `refs.csv` 与 `manuscript/`，用 `scripts/build_refs.py` 生成编号
3. 跑 `scripts/final_check.py --dir .` 直到全绿再交付
""", encoding="utf-8")

    print(f"已建立项目骨架：{root}")
    print(f"  目录 {made} 个 | 分章模板 {len(templates)} 个 | thesis.json / refs.csv / PIPELINE.md")
    print(f"  字数目标 {prof['words']}，参考文章节数建议 {prof['chapters']}")
    print()
    print("提示：排版参数在 thesis.json，学校模板到手后改那里，不要改脚本。")
    if args.mode == "sci":
        print("注意：SCI 模式请改用 paper-pipeline 技能（它面向英文期刊全流程）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 manuscript/ 下的分章 md 编译为学位论文格式的 Word 文档（第 20 步交付构建）。

排版口径（按中文学位论文惯例）：
    - A4 纸，上下 2.54 cm / 左右 2.8 cm 页边距
    - 一级标题（章）：黑体 三号 居中，段前段后 12 pt
    - 二级标题（节）：黑体 四号 左对齐
    - 三级标题：黑体 小四 左对齐
    - 正文：宋体/仿宋 小四，行距 22 pt，首行缩进 2 字符
    - 图表题注：宋体 五号 居中
    - 参考文献：宋体 五号，悬挂缩进

md 语法支持：# 标题、正文、- 列表、1. 有序列表、| 表格 |、```代码```、
![图注](路径) 图片、$公式$（原样保留为文本）、**粗体**。

用法：
    python code/build_docx.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

ROOT = Path(__file__).resolve().parents[1]
MAN = ROOT / "manuscript"
FIG = ROOT / "figures"
OUTDIR = ROOT / "deliverables"
OUTDIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from math2unicode import convert_text  # noqa: E402  LaTeX -> Unicode 公式转换

ORDER = ["part0_摘要与目录.md",
         "part1_摘要与绪论.md", "part2_理论基础与模型.md",
         "part3_数值试验设计.md", "part4_结果与分析.md",
         "part5_结论展望与附录.md"]

# 字体（中文字体名 + 西文字体名）
F_HEI = "黑体"
F_SONG = "宋体"
F_LATIN = "Times New Roman"

BLACK = RGBColor(0, 0, 0)
GREY = RGBColor(0x59, 0x59, 0x59)


# ---------------------------------------------------------------------------
# 底层工具
# ---------------------------------------------------------------------------
def set_font(run, cn=F_SONG, latin=F_LATIN, size=12, bold=False, color=BLACK):
    run.font.name = latin
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:ascii"), latin)
    rFonts.set(qn("w:hAnsi"), latin)
    rFonts.set(qn("w:eastAsia"), cn)
    return run


def para_fmt(p, first_indent_chars=0, line_pt=22, before=0, after=0,
             align=WD_ALIGN_PARAGRAPH.JUSTIFY, keep_next=False):
    pf = p.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    pf.line_spacing = Pt(line_pt)
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    p.alignment = align
    if first_indent_chars:
        # 中文字符缩进必须用 w:firstLineChars（值为"百分之一字符"）
        pPr = p._element.get_or_add_pPr()
        ind = pPr.find(qn("w:ind"))
        if ind is None:
            ind = OxmlElement("w:ind")
            pPr.append(ind)
        ind.set(qn("w:firstLineChars"), str(int(first_indent_chars * 100)))
        ind.set(qn("w:firstLine"), str(int(first_indent_chars * 12 * 20)))
    if keep_next:
        pPr = p._element.get_or_add_pPr()
        kn = OxmlElement("w:keepNext")
        pPr.append(kn)
    return p


BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def add_rich_text(p, text, cn=F_SONG, size=12, base_bold=False):
    """处理 **粗体** 片段，其余按普通文本。"""
    pos = 0
    for m in BOLD_RE.finditer(text):
        if m.start() > pos:
            set_font(p.add_run(text[pos:m.start()]), cn=cn, size=size, bold=base_bold)
        set_font(p.add_run(m.group(1)), cn=cn, size=size, bold=True)
        pos = m.end()
    if pos < len(text):
        set_font(p.add_run(text[pos:]), cn=cn, size=size, bold=base_bold)
    if not text:
        set_font(p.add_run(""), cn=cn, size=size, bold=base_bold)
    return p


TAG_RE = re.compile(r"^(.*?)　　（(\d+-\d+)）$")


def render_display_formula(doc, line: str):
    """行间公式：公式居中，编号右对齐（用右对齐制表位，避免编号换行）。

    版心宽度 = 21.0 - 2.8×2 = 15.4 cm；右制表位设在版心右边界，
    使编号紧贴右边距。
    """
    p = doc.add_paragraph()
    para_fmt(p, line_pt=20, before=6, after=6, align=WD_ALIGN_PARAGRAPH.LEFT)
    m = TAG_RE.match(line.strip())
    body = m.group(1).strip() if m else line.strip()
    tag = m.group(2) if m else ""

    # 右对齐制表位。位置必须略小于版心宽度（15.4 cm）——恰好等于边界时
    # Word 会把制表符判为溢出而换行。实测 14.4 cm 可稳定同行。
    pPr = p._element.get_or_add_pPr()
    tabs = OxmlElement("w:tabs")
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "right")
    tab.set(qn("w:pos"), str(int(14.4 * 567)))   # 1 cm = 567 twips
    tabs.append(tab)
    pPr.append(tabs)

    # 公式居中：左缩进取 1.2 cm，使公式视觉上接近居中
    p.paragraph_format.left_indent = Cm(2.4)
    set_font(p.add_run(body), cn=F_SONG, size=11.5)
    if tag:
        set_font(p.add_run("\t（" + tag + "）"), cn=F_SONG, size=11)
    return p


# ---------------------------------------------------------------------------
# 文档骨架
# ---------------------------------------------------------------------------
def new_doc() -> Document:
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = F_LATIN
    st.font.size = Pt(12)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), F_SONG)

    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.top_margin = sec.bottom_margin = Cm(2.54)
    sec.left_margin = sec.right_margin = Cm(2.8)
    return doc


def add_page_number(doc):
    for sec in doc.sections:
        footer = sec.footer
        p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        set_font(run, cn=F_SONG, size=9, color=GREY)
        fld = OxmlElement("w:fldSimple")
        fld.set(qn("w:instr"), "PAGE")
        run._element.addnext(fld)


def add_cover(doc):
    for _ in range(3):
        para_fmt(doc.add_paragraph(), line_pt=20)
    p = doc.add_paragraph()
    para_fmt(p, line_pt=40, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_font(p.add_run("本科毕业论文"), cn=F_HEI, size=22, bold=True)

    p = doc.add_paragraph()
    para_fmt(p, line_pt=40, before=24, after=6, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_font(p.add_run("面向熔融沉积成形的点阵结构参数化建模"), cn=F_HEI, size=18, bold=True)
    p = doc.add_paragraph()
    para_fmt(p, line_pt=40, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_font(p.add_run("与准静态压缩性能数值研究"), cn=F_HEI, size=18, bold=True)

    p = doc.add_paragraph()
    para_fmt(p, line_pt=26, before=18, after=24, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_font(p.add_run("Parametric Modeling and Numerical Study on the Quasi-Static\n"
                       "Compressive Performance of Lattice Structures for\n"
                       "Fused Deposition Modeling"),
             cn=F_SONG, size=11, color=GREY)

    rows = [("作　　者", "〔待填：姓名〕"), ("学　　号", "〔待填：学号〕"),
            ("专　　业", "〔待填：专业〕"), ("指导教师", "〔待填：导师姓名 / 职称〕"),
            ("学　　院", "〔待填：学院名称〕"), ("完成日期", "〔待填：年 月 日〕")]
    tbl = doc.add_table(rows=len(rows), cols=2)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (k, v) in enumerate(rows):
        for j, txt in enumerate((k, v)):
            cell = tbl.cell(i, j)
            cell.text = ""
            p = cell.paragraphs[0]
            para_fmt(p, line_pt=26, align=WD_ALIGN_PARAGRAPH.LEFT if j else WD_ALIGN_PARAGRAPH.RIGHT)
            set_font(p.add_run(txt), cn=F_SONG, size=12)
    doc.add_page_break()


def add_toc(doc, entries):
    p = doc.add_paragraph()
    para_fmt(p, before=6, after=14, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_font(p.add_run("目　　录"), cn=F_HEI, size=16, bold=True)
    for level, text in entries:
        p = doc.add_paragraph()
        indent = {1: 0, 2: 1.0, 3: 2.0}.get(level, 0)
        para_fmt(p, line_pt=22, align=WD_ALIGN_PARAGRAPH.LEFT)
        if indent:
            p.paragraph_format.left_indent = Cm(indent)
        set_font(p.add_run(text), cn=F_HEI if level == 1 else F_SONG,
                 size=12 if level == 1 else 11, bold=(level == 1))
    doc.add_page_break()


# ---------------------------------------------------------------------------
# markdown 渲染
# ---------------------------------------------------------------------------
def render_table(doc, rows: list[list[str]]):
    if not rows:
        return
    ncol = max(len(r) for r in rows)
    tbl = doc.add_table(rows=len(rows), cols=ncol)
    tbl.style = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(rows):
        for j in range(ncol):
            txt = row[j] if j < len(row) else ""
            txt = txt.replace("**", "").replace("$", "")
            cell = tbl.cell(i, j)
            cell.text = ""
            p = cell.paragraphs[0]
            para_fmt(p, line_pt=14,
                     align=WD_ALIGN_PARAGRAPH.CENTER if i == 0 or j == 0 else WD_ALIGN_PARAGRAPH.LEFT)
            set_font(p.add_run(txt), cn=F_SONG, size=9, bold=(i == 0))
    # 表后空行
    para_fmt(doc.add_paragraph(), line_pt=6)


def render_code(doc, lines: list[str]):
    for ln in lines:
        p = doc.add_paragraph()
        para_fmt(p, line_pt=12, align=WD_ALIGN_PARAGRAPH.LEFT)
        p.paragraph_format.left_indent = Cm(0.6)
        set_font(p.add_run(ln if ln else " "), cn=F_SONG, latin="Consolas", size=9, color=RGBColor(0x1F, 0x3A, 0x5F))
    para_fmt(doc.add_paragraph(), line_pt=6)


def render_image(doc, path: Path, caption: str):
    if not path.exists():
        print(f"  !! 图片缺失，跳过：{path}")
        return
    p = doc.add_paragraph()
    para_fmt(p, line_pt=14, before=6, after=2, align=WD_ALIGN_PARAGRAPH.CENTER)
    run = p.add_run()
    # 版心宽度约 15.4 cm，图宽限制在 14 cm
    run.add_picture(str(path), width=Cm(15.2))
    if caption:
        cp = doc.add_paragraph()
        para_fmt(cp, line_pt=16, after=10, align=WD_ALIGN_PARAGRAPH.CENTER)
        set_font(cp.add_run(caption.replace("**", "")), cn=F_SONG, size=10.5)


def render_markdown(doc, text: str, heading_offsets: dict[str, int]):
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()

        # 代码块
        if s.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            render_code(doc, buf)
            continue

        # 表格
        if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:\-\|]+\|$", lines[i + 1].strip()):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not re.match(r"^[\s:\-]+$", "".join(cells)):
                    rows.append(cells)
                i += 1
            render_table(doc, rows)
            continue

        # 图片
        m = re.match(r"^!\[(.*?)\]\((.*?)\)$", s)
        if m:
            cap = m.group(1)
            render_image(doc, MAN.parent / m.group(2), cap)
            i += 1
            continue

        # 水平线
        if s in ("---", "***", "___"):
            p = doc.add_paragraph()
            para_fmt(p, line_pt=8, after=4)
            pPr = p._element.get_or_add_pPr()
            pbdr = OxmlElement("w:pBdr")
            bottom = OxmlElement("w:bottom")
            bottom.set(qn("w:val"), "single")
            bottom.set(qn("w:sz"), "6")
            bottom.set(qn("w:color"), "AAAAAA")
            pbdr.append(bottom)
            pPr.append(pbdr)
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{2,4})\s+(.*)$", s)
        if m:
            level = len(m.group(1)) - 1        # ## -> 1
            txt = m.group(2).replace("**", "")
            p = doc.add_paragraph()
            if level == 1:
                para_fmt(p, line_pt=30, before=16, after=10,
                         align=WD_ALIGN_PARAGRAPH.CENTER, keep_next=True)
                set_font(p.add_run(txt), cn=F_HEI, size=16, bold=True)
            elif level == 2:
                para_fmt(p, line_pt=26, before=12, after=6,
                         align=WD_ALIGN_PARAGRAPH.LEFT, keep_next=True)
                set_font(p.add_run(txt), cn=F_HEI, size=14, bold=True)
            else:
                para_fmt(p, line_pt=24, before=8, after=4,
                         align=WD_ALIGN_PARAGRAPH.LEFT, keep_next=True)
                set_font(p.add_run(txt), cn=F_HEI, size=12, bold=True)
            i += 1
            continue

        # 空行
        if not s:
            i += 1
            continue

        # 图题 / 表题（**图 x-x ...** 单独成行）
        if re.match(r"^\*\*(图|表)\s", s) and s.endswith("**"):
            p = doc.add_paragraph()
            para_fmt(p, line_pt=16, before=2, after=8, align=WD_ALIGN_PARAGRAPH.CENTER)
            set_font(p.add_run(s.strip("*")), cn=F_SONG, size=10.5)
            i += 1
            continue

        # 引用块
        if s.startswith(">"):
            p = doc.add_paragraph()
            para_fmt(p, line_pt=20, align=WD_ALIGN_PARAGRAPH.LEFT)
            p.paragraph_format.left_indent = Cm(0.8)
            add_rich_text(p, s.lstrip("> ").strip(), cn=F_SONG, size=10.5)
            i += 1
            continue

        # 有序列表
        m = re.match(r"^(\d+)\.\s+(.*)$", s)
        if m:
            p = doc.add_paragraph()
            para_fmt(p, line_pt=22, after=2, align=WD_ALIGN_PARAGRAPH.LEFT)
            p.paragraph_format.left_indent = Cm(0.75)
            add_rich_text(p, f"{m.group(1)}. {m.group(2)}", cn=F_SONG, size=12)
            i += 1
            continue

        # 无序列表
        if re.match(r"^[-*]\s+", s):
            p = doc.add_paragraph()
            para_fmt(p, line_pt=22, after=2, align=WD_ALIGN_PARAGRAPH.LEFT)
            p.paragraph_format.left_indent = Cm(0.75)
            add_rich_text(p, "· " + re.sub(r"^[-*]\s+", "", s), cn=F_SONG, size=12)
            i += 1
            continue

        # 参考文献条目（[n] 开头，悬挂缩进）
        if re.match(r"^\[\d+\]", s) or re.match(r"^E\d+\.", s):
            p = doc.add_paragraph()
            para_fmt(p, line_pt=16, after=2, align=WD_ALIGN_PARAGRAPH.LEFT)
            p.paragraph_format.left_indent = Cm(0.95)
            p.paragraph_format.first_line_indent = Cm(-0.95)
            add_rich_text(p, s, cn=F_SONG, size=10.5)
            i += 1
            continue

        # 参考文献表头（"### 延伸阅读…" 已由标题分支处理）

        # 行间公式（转换后形如 "E*/Eₛ = C₁ ρ̄ⁿ　　（2-2）" 或纯公式行）
        if re.search(r"（\d+-\d+）$", s) and " " in s and not s.startswith(("**", "|", "[")):
            render_display_formula(doc, s)
            i += 1
            continue

        # 普通段落
        p = doc.add_paragraph()
        para_fmt(p, first_indent_chars=2, line_pt=22, after=2)
        add_rich_text(p, s, cn=F_SONG, size=12)
        i += 1


def collect_toc(text: str) -> list[tuple[int, str]]:
    out = []
    for ln in text.split("\n"):
        m = re.match(r"^(#{2,4})\s+(.*)$", ln.strip())
        if m:
            lvl = len(m.group(1)) - 1
            out.append((lvl, m.group(2).replace("**", "")))
    return out


def main() -> int:
    # 组装全文
    parts = []
    for f in ORDER:
        parts.append((MAN / f).read_text(encoding="utf-8").strip())
    refs = (ROOT / "05_稿件" / "参考文献.md")
    p5 = parts[-1]
    if refs.exists() and "## 参考文献" not in p5:
        reftext = refs.read_text(encoding="utf-8").strip()
        if "## 致谢" in p5:
            head, tail = p5.split("## 致谢", 1)
            p5 = head.rstrip() + "\n\n" + reftext + "\n\n---\n\n## 致谢" + tail
        else:
            p5 = p5.rstrip() + "\n\n" + reftext
    parts[-1] = p5
    full = "\n\n".join(parts)

    # 公式转换：LaTeX -> Unicode（代码块内的内容必须原样保留，故先切分保护）
    segments = re.split(r"(```.*?```)", full, flags=re.S)
    full = "".join(seg if seg.startswith("```") else convert_text(seg)
                   for seg in segments)

    doc = new_doc()
    add_page_number(doc)
    add_cover(doc)

    # 目录由 part0_摘要与目录.md 末尾的静态"## 目录"章节提供（内容由脚本维护），
    # 因此这里不再自动生成 second TOC，避免出现两份目录。
    render_markdown(doc, full, {})

    out = OUTDIR / "3D打印点阵结构本科毕业论文.docx"
    doc.save(str(out))
    print(f"已生成 Word：{out}")
    print(f"  文件大小：{out.stat().st_size / 1024:.0f} KB")

    # 统计与残留检查
    import re as _re
    from math2unicode import WARNINGS
    cjk = len(_re.findall(r"[\u4e00-\u9fff]", full))
    print(f"  全文中文字符：{cjk}")
    if WARNINGS:
        print(f"  !! 未转换的 LaTeX 命令：{sorted(set(WARNINGS))}")
    else:
        print("  公式转换：无残留 LaTeX 命令")
    if "$" in full:
        print(f"  !! 仍有 {full.count('$')} 个 $ 符号未转换")
    return 0


if __name__ == "__main__":
    sys.exit(main())

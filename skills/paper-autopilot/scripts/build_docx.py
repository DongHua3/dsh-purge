#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把分章 md 编译为学位论文格式的 Word 文档（thesis-pipeline）

排版参数全部来自 thesis.json（字体、字号、行距、页边距、图宽、章节顺序），
学校模板到手后改 thesis.json，不要改本脚本。

md 语法支持：# 标题、正文、- 列表、1. 有序列表、| 表格 |、```代码```、
![](图片) + 紧随的 **图 x-y 题注**、$行内公式$、$$行间公式 \tag{2-1}$$、（GB/T 7714）[n] 引用。
LaTeX 公式由 math2unicode.py 转为 Unicode 文本（python-docx 无法生成 OMML 公式）。

用法：
    python build_docx.py --config thesis.json --manuscript manuscript/ --out deliverables/论文.docx
    python build_docx.py --config thesis.json          # 用 thesis.json 里的 manuscript_order
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from docx import Document
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from math2unicode import convert_text, WARNINGS  # noqa: E402

BLACK = RGBColor(0, 0, 0)
GREY = RGBColor(0x59, 0x59, 0x59)
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
TAG_RE = re.compile(r"^(.*?)　　（(\d+[-.]\d+|[A-Z]?\d+)）$")


class Cfg:
    """把 thesis.json 读成带默认值的配置对象。"""

    def __init__(self, path: Path | None):
        d = {}
        if path and path.exists():
            d = json.loads(path.read_text(encoding="utf-8"))
        self.raw = d
        p = d.get("page", {})
        self.margin = (p.get("margin_top_cm", 2.54), p.get("margin_bottom_cm", 2.54),
                       p.get("margin_left_cm", 2.8), p.get("margin_right_cm", 2.8))
        f = d.get("fonts", {})
        self.f_body = f.get("body_cn", "宋体")
        self.f_latin = f.get("body_latin", "Times New Roman")
        self.f_head = f.get("heading_cn", "黑体")
        self.f_code = f.get("code_latin", "Consolas")
        s = d.get("sizes", {})
        self.s_body = s.get("body_pt", 12)
        self.s_h1 = s.get("h1_pt", 16)
        self.s_h2 = s.get("h2_pt", 14)
        self.s_h3 = s.get("h3_pt", 12)
        self.s_cap = s.get("caption_pt", 10.5)
        self.s_ref = s.get("ref_pt", 10.5)
        self.s_math = s.get("formula_pt", 11.5)
        self.line = d.get("line_spacing_pt", 22)
        self.indent = d.get("first_line_indent_chars", 2)
        self.fig_w = d.get("figure_width_cm", 15.2)
        self.order = d.get("manuscript_order", [])
        self.title = d.get("title", "论文")
        self.author = d.get("author", {})


def set_font(run, cn, latin, size, bold=False, color=BLACK):
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


def para_fmt(p, cfg: Cfg, indent=0, line=None, before=0, after=0,
             align=WD_ALIGN_PARAGRAPH.JUSTIFY, keep_next=False):
    pf = p.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    pf.line_spacing = Pt(line if line is not None else cfg.line)
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    p.alignment = align
    if indent:
        pPr = p._element.get_or_add_pPr()
        ind = pPr.find(qn("w:ind"))
        if ind is None:
            ind = OxmlElement("w:ind")
            pPr.append(ind)
        ind.set(qn("w:firstLineChars"), str(int(indent * 100)))
        ind.set(qn("w:firstLine"), str(int(indent * cfg.s_body * 20)))
    if keep_next:
        pPr = p._element.get_or_add_pPr()
        pPr.append(OxmlElement("w:keepNext"))
    return p


def add_rich(p, text, cfg: Cfg, cn=None, size=None):
    cn = cn or cfg.f_body
    size = size or cfg.s_body
    pos = 0
    for m in BOLD_RE.finditer(text):
        if m.start() > pos:
            set_font(p.add_run(text[pos:m.start()]), cn, cfg.f_latin, size)
        set_font(p.add_run(m.group(1)), cn, cfg.f_latin, size, bold=True)
        pos = m.end()
    if pos < len(text):
        set_font(p.add_run(text[pos:]), cn, cfg.f_latin, size)
    if not text:
        set_font(p.add_run(""), cn, cfg.f_latin, size)
    return p


def new_doc(cfg: Cfg) -> Document:
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = cfg.f_latin
    st.font.size = Pt(cfg.s_body)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), cfg.f_body)
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    t, b, l, r = cfg.margin
    sec.top_margin, sec.bottom_margin = Cm(t), Cm(b)
    sec.left_margin, sec.right_margin = Cm(l), Cm(r)
    # 页脚页码
    footer = sec.footer
    fp = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = fp.add_run()
    set_font(run, cfg.f_body, cfg.f_latin, 9, color=GREY)
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    run._element.addnext(fld)
    return doc


def add_cover(doc: Document, cfg: Cfg):
    for _ in range(3):
        para_fmt(doc.add_paragraph(), cfg, line=20)
    p = doc.add_paragraph()
    para_fmt(p, cfg, line=40, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_font(p.add_run(f"{cfg.raw.get('type', '本科')}毕业论文"), cfg.f_head, cfg.f_latin,
             22, bold=True)
    for seg in re.split(r"[：:]", cfg.title) or [cfg.title]:
        p = doc.add_paragraph()
        para_fmt(p, cfg, line=40, before=24, after=6, align=WD_ALIGN_PARAGRAPH.CENTER)
        set_font(p.add_run(seg), cfg.f_head, cfg.f_latin, 18, bold=True)
    a = cfg.author
    rows = [("作　　者", a.get("name", "〔待填〕")), ("学　　号", a.get("sid", "〔待填〕")),
            ("专　　业", a.get("major", "〔待填〕")), ("指导教师", a.get("advisor", "〔待填〕")),
            ("学　　院", a.get("school", "〔待填〕")), ("完成日期", a.get("date", "〔待填〕"))]
    tbl = doc.add_table(rows=len(rows), cols=2)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (k, v) in enumerate(rows):
        for j, txt in enumerate((k, v)):
            cell = tbl.cell(i, j)
            cell.text = ""
            pp = cell.paragraphs[0]
            para_fmt(pp, cfg, line=26,
                     align=WD_ALIGN_PARAGRAPH.RIGHT if j == 0 else WD_ALIGN_PARAGRAPH.LEFT)
            set_font(pp.add_run(txt), cfg.f_body, cfg.f_latin, cfg.s_body)
    doc.add_page_break()


def render_table(doc, rows, cfg: Cfg):
    if not rows:
        return
    ncol = max(len(r) for r in rows)
    tbl = doc.add_table(rows=len(rows), cols=ncol)
    tbl.style = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(rows):
        for j in range(ncol):
            txt = (row[j] if j < len(row) else "").replace("**", "")
            cell = tbl.cell(i, j)
            cell.text = ""
            pp = cell.paragraphs[0]
            para_fmt(pp, cfg, line=14,
                     align=WD_ALIGN_PARAGRAPH.CENTER if (i == 0 or j == 0)
                     else WD_ALIGN_PARAGRAPH.LEFT)
            set_font(pp.add_run(txt), cfg.f_body, cfg.f_latin, 9, bold=(i == 0))
    para_fmt(doc.add_paragraph(), cfg, line=6)


def render_code(doc, lines, cfg: Cfg):
    for ln in lines:
        p = doc.add_paragraph()
        para_fmt(p, cfg, line=12, align=WD_ALIGN_PARAGRAPH.LEFT)
        p.paragraph_format.left_indent = Cm(0.6)
        set_font(p.add_run(ln if ln else " "), cfg.f_body, cfg.f_code, 9,
                 color=RGBColor(0x1F, 0x3A, 0x5F))
    para_fmt(doc.add_paragraph(), cfg, line=6)


def render_image(doc, path: Path, caption: str, cfg: Cfg):
    if not path.exists():
        print(f"  !! 图片缺失，跳过：{path}")
        return
    p = doc.add_paragraph()
    para_fmt(p, cfg, line=14, before=6, after=2, align=WD_ALIGN_PARAGRAPH.CENTER)
    p.add_run().add_picture(str(path), width=Cm(cfg.fig_w))
    if caption:
        cp = doc.add_paragraph()
        para_fmt(cp, cfg, line=16, after=10, align=WD_ALIGN_PARAGRAPH.CENTER)
        set_font(cp.add_run(caption), cfg.f_body, cfg.f_latin, cfg.s_cap)


def render_formula(doc, line: str, cfg: Cfg):
    """行间公式：公式居中，编号右对齐（右制表位略小于版心宽度，否则会换行）。"""
    p = doc.add_paragraph()
    para_fmt(p, cfg, line=20, before=6, after=6, align=WD_ALIGN_PARAGRAPH.LEFT)
    m = TAG_RE.match(line.strip())
    body, tag = (m.group(1).strip(), m.group(2)) if m else (line.strip(), "")
    text_w = 21.0 - cfg.margin[2] - cfg.margin[3]
    pPr = p._element.get_or_add_pPr()
    tabs = OxmlElement("w:tabs")
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "right")
    tab.set(qn("w:pos"), str(int((text_w - 1.0) * 567)))
    tabs.append(tab)
    pPr.append(tabs)
    p.paragraph_format.left_indent = Cm(2.4)
    set_font(p.add_run(body), cfg.f_body, cfg.f_latin, cfg.s_math)
    if tag:
        set_font(p.add_run(f"\t（{tag}）"), cfg.f_body, cfg.f_latin, cfg.s_math - 0.5)


def render_md(doc, text: str, cfg: Cfg, base: Path):
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()

        if s.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            render_code(doc, buf, cfg)
            continue

        if s.startswith("|") and i + 1 < len(lines) and \
                re.match(r"^\|[\s:\-\|]+\|$", lines[i + 1].strip()):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not re.match(r"^[\s:\-]+$", "".join(cells)):
                    rows.append(cells)
                i += 1
            render_table(doc, rows, cfg)
            continue

        m = re.match(r"^!\[(.*?)\]\((.*?)\)$", s)
        if m:
            render_image(doc, (base / m.group(2)).resolve(), m.group(1), cfg)
            i += 1
            continue

        if s in ("---", "***", "___"):
            p = doc.add_paragraph()
            para_fmt(p, cfg, line=8, after=4)
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

        m = re.match(r"^(#{2,4})\s+(.*)$", s)
        if m:
            level = len(m.group(1)) - 1
            txt = m.group(2).replace("**", "")
            p = doc.add_paragraph()
            if level == 1:
                para_fmt(p, cfg, line=30, before=16, after=10,
                         align=WD_ALIGN_PARAGRAPH.CENTER, keep_next=True)
                set_font(p.add_run(txt), cfg.f_head, cfg.f_latin, cfg.s_h1, bold=True)
            elif level == 2:
                para_fmt(p, cfg, line=26, before=12, after=6,
                         align=WD_ALIGN_PARAGRAPH.LEFT, keep_next=True)
                set_font(p.add_run(txt), cfg.f_head, cfg.f_latin, cfg.s_h2, bold=True)
            else:
                para_fmt(p, cfg, line=24, before=8, after=4,
                         align=WD_ALIGN_PARAGRAPH.LEFT, keep_next=True)
                set_font(p.add_run(txt), cfg.f_head, cfg.f_latin, cfg.s_h3, bold=True)
            i += 1
            continue

        if not s:
            i += 1
            continue

        # 图题/表题
        if re.match(r"^\*\*(图|表)\s", s) and s.endswith("**"):
            p = doc.add_paragraph()
            para_fmt(p, cfg, line=16, before=2, after=8, align=WD_ALIGN_PARAGRAPH.CENTER)
            set_font(p.add_run(s.strip("*")), cfg.f_body, cfg.f_latin, cfg.s_cap)
            i += 1
            continue

        # 行间公式（转换后形如 "E/Eₛ = C₁ ρ̄ⁿ　　（2-2）"）
        if re.search(r"（[\dA-Z]+[-.]\d+）$", s) and " " in s and \
                not s.startswith(("**", "|", "[")):
            render_formula(doc, s, cfg)
            i += 1
            continue

        if s.startswith(">"):
            p = doc.add_paragraph()
            para_fmt(p, cfg, line=20, align=WD_ALIGN_PARAGRAPH.LEFT)
            p.paragraph_format.left_indent = Cm(0.8)
            add_rich(p, s.lstrip("> ").strip(), cfg, size=cfg.s_cap)
            i += 1
            continue

        m = re.match(r"^(\d+)\.\s+(.*)$", s)
        if m:
            p = doc.add_paragraph()
            para_fmt(p, cfg, line=cfg.line, after=2, align=WD_ALIGN_PARAGRAPH.LEFT)
            p.paragraph_format.left_indent = Cm(0.75)
            add_rich(p, f"{m.group(1)}. {m.group(2)}", cfg)
            i += 1
            continue

        if re.match(r"^[-*]\s+", s):
            p = doc.add_paragraph()
            para_fmt(p, cfg, line=cfg.line, after=2, align=WD_ALIGN_PARAGRAPH.LEFT)
            p.paragraph_format.left_indent = Cm(0.75)
            add_rich(p, "· " + re.sub(r"^[-*]\s+", "", s), cfg)
            i += 1
            continue

        # 参考文献条目（悬挂缩进）
        if re.match(r"^\[\d+\]", s) or re.match(r"^E\d+\.", s):
            p = doc.add_paragraph()
            para_fmt(p, cfg, line=16, after=2, align=WD_ALIGN_PARAGRAPH.LEFT)
            p.paragraph_format.left_indent = Cm(0.95)
            p.paragraph_format.first_line_indent = Cm(-0.95)
            add_rich(p, s, cfg, size=cfg.s_ref)
            i += 1
            continue

        p = doc.add_paragraph()
        para_fmt(p, cfg, indent=cfg.indent, line=cfg.line, after=2)
        add_rich(p, s, cfg)
        i += 1


def main() -> int:
    ap = argparse.ArgumentParser(description="编译 md 为学位论文格式 Word")
    ap.add_argument("--config", default="thesis.json", help="排版配置")
    ap.add_argument("--manuscript", default="manuscript", help="分章 md 目录")
    ap.add_argument("--out", default="", help="输出 docx 路径")
    args = ap.parse_args()

    cfg_path = Path(args.config)
    cfg = Cfg(cfg_path)
    man = Path(args.manuscript)
    if not man.is_dir():
        print(f"找不到目录 {man}")
        return 1

    order = cfg.order or [p.name for p in sorted(man.glob("*.md"))]
    parts, missing = [], []
    for name in order:
        p = man / name
        if p.exists():
            parts.append(p.read_text(encoding="utf-8").strip())
        else:
            missing.append(name)
    if missing:
        print(f"!! thesis.json 的 manuscript_order 里这些文件不存在：{missing}")
    if not parts:
        print("没有可编译的 md 文件")
        return 1
    full = "\n\n".join(parts)

    # 公式转换（保护代码块）
    segs = re.split(r"(```.*?```)", full, flags=re.S)
    full = "".join(seg if seg.startswith("```") else convert_text(seg) for seg in segs)

    doc = new_doc(cfg)
    add_cover(doc, cfg)
    render_md(doc, full, cfg, man)

    out = Path(args.out) if args.out else Path("deliverables") / f"{cfg.title[:20] or '论文'}.docx"
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))

    cjk = len(re.findall(r"[\u4e00-\u9fff]", full))
    print(f"已生成 Word：{out}")
    print(f"  文件大小：{out.stat().st_size / 1024:.0f} KB | 全文中文字符：{cjk}")
    if WARNINGS:
        print(f"  !! 未转换的 LaTeX 命令：{sorted(set(WARNINGS))}")
    else:
        print("  公式转换：无残留 LaTeX 命令")
    if "$" in full:
        print(f"  !! 仍有 {full.count('$')} 个 $ 未转换")
    print(f"  下一步：python scripts/docx_to_pdf.py \"{out}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())

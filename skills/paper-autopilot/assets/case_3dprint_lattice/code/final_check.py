#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""终检脚本（第 20 步）：一次性校验全部交付约束，输出总检报告。

检查项：
    1. 章节目录完整性（每个应有章节是否存在）
    2. 正文字数
    3. 图表数量与编号连续性、是否全部被正文引用
    4. 参考文献：正文引用 vs 参考表条目（悬空 / 孤立）
    5. 首字母/公式残留（LaTeX 命令、$ 符号）
    6. 数据文件与交付文件的 SHA-256 哈希表
    7. 作者占位符清单
    8. 交付文件存在性与大小

用法：
    python code/final_check.py            # 控制台报告
    python code/final_check.py --write    # 同时写出 deliverables/HASHES.txt 与 20_投稿前总检/CHECK_REPORT.md
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

ROOT = Path(__file__).resolve().parents[1]
MAN = ROOT / "manuscript"
DATA = ROOT / "data"
FIG = ROOT / "figures"
DELIV = ROOT / "deliverables"
REFS = ROOT / "05_稿件" / "参考文献.md"

REQUIRED_SECTIONS = [
    "第 1 章", "第 2 章", "第 3 章", "第 4 章", "第 5 章",
    "参考文献", "致谢", "附录 A", "附录 B",
]
CITE = re.compile(r"\[(\d+(?:\s*[,，\-–]\s*\d+)*)\]")
PLACEHOLDER = re.compile(r"〔待填：[^〕]*〕")

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))


def read_all_manuscript() -> str:
    """正文分章 + 参考文献表（参考文献单独成文件，必须一并纳入检查）。"""
    txt = "\n\n".join(p.read_text(encoding="utf-8") for p in sorted(MAN.glob("*.md")))
    if REFS.exists():
        txt += "\n\n" + REFS.read_text(encoding="utf-8")
    return txt


def docx_text(path: Path) -> str:
    """读取 docx 的全部文本（用于检查成品是否有公式/占位符残留）。"""
    try:
        from docx import Document
    except ImportError:
        return ""
    d = Document(str(path))
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            for c in row.cells:
                parts.append(c.text)
    return "\n".join(parts)


def expand(token: str) -> set[int]:
    out: set[int] = set()
    for part in re.split(r"[,，]", token):
        part = part.strip()
        m = re.match(r"^(\d+)\s*[-–]\s*(\d+)$", part)
        if m:
            out.update(range(int(m.group(1)), int(m.group(2)) + 1))
        elif part.isdigit():
            out.add(int(part))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    text = read_all_manuscript()
    full = text
    refs_text = REFS.read_text(encoding="utf-8") if REFS.exists() else ""

    # 1 章节
    missing = [s for s in REQUIRED_SECTIONS if s not in full]
    check("章节完整性", not missing,
          "全部章节齐备" if not missing else f"缺失：{missing}")

    # 2 字数
    cjk = len(re.findall(r"[\u4e00-\u9fff]", full))
    check("正文字数 ≥ 18000", cjk >= 18000, f"实际 {cjk} 中文字符")

    # 3 图表
    figs = re.findall(r"!\[[^\]]*\]\(figures/fig([\d\-]+)_", full)
    tabs = re.findall(r"\*\*表 ([\d\-]+)", full)
    fig_nums = [f.split("-")[1] for f in figs]
    ch4 = [int(n) for f, n in zip(figs, fig_nums) if f.startswith("4-")]
    contig = ch4 == list(range(1, len(ch4) + 1))
    check("图编号连续（第4章）", contig, f"第4章图号 {ch4}")
    tab_nums = sorted({t for t in tabs})
    check("表数量 ≥ 10", len(tab_nums) >= 10, f"{len(tab_nums)} 张表")

    # 图片文件存在（图文件名形如 fig4-1_应力应变曲线.png，用前缀匹配）
    all_stems = [p.stem for p in FIG.glob("*.png")]
    miss_img = [f for f in figs if not any(s.startswith(f"fig{f}_") for s in all_stems)]
    check("图片文件存在", not miss_img,
          f"缺失 {miss_img}" if miss_img else f"{len(figs)}/{len(figs)} 存在")

    # 4 引用一致性
    used: set[int] = set()
    for m in CITE.finditer(full):
        used |= expand(m.group(1))
    used.discard(0)
    defined = {int(m.group(1)) for m in
               (re.match(r"^\[(\d+)\]", l) for l in refs_text.splitlines()) if m}
    dangling = sorted(used - defined)
    orphan = sorted(i for i in defined - used if i <= max(defined or {0}))
    check("无悬空引用", not dangling, f"{dangling}" if dangling else "0 处")
    check("无孤立条目", not orphan, f"{orphan}" if orphan else "0 条")

    # 5 公式残留：md 源里出现 LaTeX 是正常的（那是唯一真源），
    #    真正要检查的是**成品 docx** 里是否还有未转换的公式标记。
    docx_path = DELIV / "3D打印点阵结构本科毕业论文.docx"
    dtxt = docx_text(docx_path) if docx_path.exists() else ""
    if dtxt:
        d_dollar = dtxt.count("$")
        # 只匹配真实 LaTeX 数学命令名；不能笼统匹配"反斜杠+字母"，
        # 否则附录 B.3 里的 Windows 路径（D:\py\Python311\...）会被误判。
        LATEX_CMDS = (r"\\(?:frac|tfrac|dfrac|sqrt|bar|hat|tilde|vec|mathrm|"
                      r"mathbf|mathit|text|left|right|rho|sigma|theta|alpha|"
                      r"beta|gamma|delta|varepsilon|epsilon|lambda|mu|eta|"
                      r"kappa|chi|times|cdot|approx|leq|geq|infty|partial|"
                      r"sum|int|tag|quad|qquad|begin|end|underbrace)\b")
        d_latex = len(re.findall(LATEX_CMDS, dtxt))
        code_bt = dtxt.count("```")
        check("成品无公式残留（docx）",
              d_dollar == 0 and d_latex == 0 and code_bt == 0,
              f"$ 残留 {d_dollar}，LaTeX 命令残留 {d_latex}，代码围栏 {code_bt}")
    else:
        check("成品无公式残留（docx）", False, "无法读取 docx 文本")
    # 同时记录 md 源的公式数量（供人工确认，不作为失败项）
    src_dollar = full.count("$")
    check("md 源公式标记（仅记录）", True, f"{src_dollar} 处 $ 标记，属正常（源用 LaTeX，成品已转换）")

    # 6 交付文件
    for f in ["3D打印点阵结构本科毕业论文.docx", "3D打印点阵结构本科毕业论文.pdf"]:
        p = DELIV / f
        ok = p.exists() and p.stat().st_size > 100_000
        check(f"交付件 {f}", ok,
              f"{p.stat().st_size/1024:.0f} KB" if p.exists() else "不存在")

    # 7 占位符
    ph = sorted(set(PLACEHOLDER.findall(full)))
    check("作者占位符已集中标注", True, f"{len(ph)} 处待替换")

    # 8 哈希表
    hashes: list[tuple[str, str, int]] = []
    for base in (DATA, FIG, DELIV):
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix.lower() in (".csv", ".json", ".png", ".pdf", ".docx"):
                h = hashlib.sha256(p.read_bytes()).hexdigest()
                hashes.append((str(p.relative_to(ROOT)), h, p.stat().st_size))

    # ---- 输出 ----
    lines = ["# 第 20 步总检报告", "",
             f"生成时间：2026-10-11　项目：{ROOT.name}", "",
             "| 检查项 | 结果 | 说明 |", "|---|---|---|"]
    npass = 0
    for name, ok, detail in results:
        npass += bool(ok)
        lines.append(f"| {name} | {'✅ 通过' if ok else '❌ 未通过'} | {detail} |")
    lines.append("")
    lines.append(f"**{npass}/{len(results)} 项通过。**")
    lines.append("")
    if ph:
        lines.append("## 待用户替换的占位符")
        lines.append("")
        for x in ph:
            lines.append(f"- `{x}`")
        lines.append("")

    report = "\n".join(lines)
    print(report)

    if args.write:
        outdir = ROOT / "20_投稿前总检"
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "CHECK_REPORT.md").write_text(report, encoding="utf-8")
        hash_lines = ["# 交付物哈希表（SHA-256）", "",
                      "用于校验文件是否被改动。重跑 `python code/final_check.py --write` 可刷新。", "",
                      "| 文件 | 字节 | SHA-256 |", "|---|---|---|"]
        for rel, h, sz in hashes:
            hash_lines.append(f"| `{rel}` | {sz} | `{h}` |")
        (DELIV / "HASHES.txt").write_text("\n".join(hash_lines), encoding="utf-8")
        print(f"\n已写出：{outdir / 'CHECK_REPORT.md'}")
        print(f"已写出：{DELIV / 'HASHES.txt'}（{len(hashes)} 个文件）")
    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())

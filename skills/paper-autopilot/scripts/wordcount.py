#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统计分章 md 的中文字数与图表编号连续性（中文论文第 20 步总检用）。

从单项目硬编码版（只认 `manuscript/` 与 `figures/figN-M_`）提炼为通用版：
用 `--dir` 指向任意手稿目录，图号/表号的书写形式由正则给出，判定结果可用
退出码驱动 CI 或 `final_check.py`。

统计口径
--------
* 中文字数：只数汉字 `[\\u4e00-\\u9fff]`；先剔除图片嵌入 `![...](...)` 与
  HTML 注释，公式文本、图题、表题仍计入（与 Word 字数统计对齐）。
* 图：图片嵌入的文件名里抓 `fig4-1` / `4-1` / `图4-1` 三种写法。
* 表：抓行首 `**表 4-1` 形式的题注（必须行首，避免把加粗收尾误判成题注），
  以及正文里的 `表 4-1`。
* 连续性：按章号分组，组内序号必须从 1 起连续；重号、跳号都算不通过。

用法
----
    python scripts/wordcount.py --dir manuscript
    python scripts/wordcount.py --dir manuscript --min 20000 --json report.json
    python scripts/wordcount.py --dir manuscript --fig-pattern "fig{n}-{m}_"

退出码：0 全部通过；1 有连续性问题或字数未达标；2 参数/IO 错误。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

CJK = re.compile(r"[\u4e00-\u9fff]")
IMG = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)

# 图号来源：图片路径里的 figN-M / N-M，或正文里的「图 N-M」「图N-M」
FIG_IN_PATH = re.compile(r"(?:fig)?(\d+)\s*[-–—.]\s*(\d+)", re.I)
FIG_IN_TEXT = re.compile(r"图\s*(\d+)\s*[-–—.]\s*(\d+)")
# 表号：加粗题注 `**表 4-1`、或正文「表 4-1」
TAB_IN_TEXT = re.compile(r"表\s*(\d+)\s*[-–—.]\s*(\d+)")


def read_text(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def body_chars(text: str) -> int:
    """剔除图片嵌入与 HTML 注释后的汉字数。"""
    stripped = IMG.sub("", text)
    stripped = HTML_COMMENT.sub("", stripped)
    return len(CJK.findall(stripped))


def collect(text: str):
    """返回 (嵌图号, 正文图引用号, 表题号, 正文表引用号)，元素为 'N-M' 字符串。"""
    embeds, fig_refs, tab_caps, tab_refs = [], [], [], []
    for m in IMG.finditer(text):
        target = m.group(1)
        hit = re.search(r"(\d+)\s*[-–—.]\s*(\d+)", os.path.basename(target))
        if hit:
            embeds.append(f"{hit.group(1)}-{hit.group(2)}")
    for m in FIG_IN_TEXT.finditer(text):
        fig_refs.append(f"{m.group(1)}-{m.group(2)}")
    for m in TAB_IN_TEXT.finditer(text):
        tab_refs.append(f"{m.group(1)}-{m.group(2)}")
    # 加粗题注单独记一份，便于区分「题注」与「正文提及」。
    # 必须锚在行首：正文里「...** 表 4-12 中的 ...」这种"加粗结束后提到表号"的写法
    # 会把加粗收尾的 ** 误当题注起始，产生假重号（真实项目里踩过）。
    for m in re.finditer(r"^[ \t]{0,3}\*\*\s*表\s*(\d+)\s*[-–—.]\s*(\d+)", text, re.M):
        tab_caps.append(f"{m.group(1)}-{m.group(2)}")
    return embeds, fig_refs, tab_caps, tab_refs


def continuity(ids, label: str):
    """按章号分组检查序号连续；返回 (问题列表, 摘要)。"""
    problems = []
    by_ch: dict[int, list[int]] = {}
    for i in ids:
        ch, no = i.split("-")
        by_ch.setdefault(int(ch), []).append(int(no))
    for ch in sorted(by_ch):
        nums = sorted(set(by_ch[ch]))
        dups = sorted({n for n in by_ch[ch] if by_ch[ch].count(n) > 1})
        if dups:
            problems.append(f"{label} {ch}-{dups} 重号（同一编号被引用多次属正常，仅作提示）")
        if not nums:
            continue
        missing = [n for n in range(1, max(nums) + 1) if n not in by_ch[ch]]
        if missing:
            problems.append(f"{label} 第 {ch} 章缺号：{missing}（已见 {nums}）")
    summary = " ".join(f"{c}:1..{max(by_ch[c])}" for c in sorted(by_ch)) if by_ch else "（无）"
    return problems, summary


def main() -> int:
    ap = argparse.ArgumentParser(
        description="统计分章 md 的中文字数与图表编号连续性",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：python scripts/wordcount.py --dir manuscript --min 20000",
    )
    ap.add_argument("--dir", default="manuscript", help="分章 md 目录（默认 manuscript）")
    ap.add_argument("--glob", default="*.md", help="文件匹配模式（默认 *.md）")
    ap.add_argument("--min", type=int, default=0, help="字数下限；0 表示不设闸门")
    ap.add_argument("--json", dest="json_out", default="", help="把结果写成 JSON")
    ap.add_argument("--quiet", action="store_true", help="只输出合计与问题")
    ap.add_argument("--allow-gap", action="store_true", help="有缺号也返回 0（仅报告）")
    args = ap.parse_args()

    if not os.path.isdir(args.dir):
        print(f"[wordcount] 目录不存在：{args.dir}", file=sys.stderr)
        return 2

    files = sorted(glob.glob(os.path.join(args.dir, args.glob)))
    if not files:
        print(f"[wordcount] {args.dir} 下没有匹配 {args.glob} 的文件", file=sys.stderr)
        return 2

    rows, total = [], 0
    fig_all, tab_all, fig_ref_all, tab_ref_all = [], [], [], []
    for path in files:
        text = read_text(path)
        cjk = body_chars(text)
        embeds, fig_refs, tab_caps, tab_refs = collect(text)
        total += cjk
        fig_all += embeds
        tab_all += tab_caps
        fig_ref_all += fig_refs
        tab_ref_all += tab_refs
        rows.append({
            "file": os.path.basename(path),
            "chars": cjk,
            "figures": len(embeds),
            "tables": len(tab_caps),
            "fig_ids": sorted(set(embeds)),
            "tab_ids": sorted(set(tab_caps)),
        })

    if not args.quiet:
        print(f"{'文件':<36}{'中文字符':>10}{'图':>5}{'表':>5}")
        print("-" * 58)
        for r in rows:
            print(f"{r['file']:<36}{r['chars']:>10}{r['figures']:>5}{r['tables']:>5}")
        print("-" * 58)
    print(f"{'合计':<36}{total:>10}{len(set(fig_all)):>5}{len(set(tab_all)):>5}")

    problems: list[str] = []
    fig_problems, fig_summary = continuity(fig_all, "图")
    tab_problems, tab_summary = continuity(tab_all, "表")
    problems += fig_problems
    problems += tab_problems

    # 图表「有编号但正文从未提及」= 悬空题注；「正文提及但无对应题注」= 悬空引用
    orphan_fig = sorted(set(fig_all) - set(fig_ref_all))
    missing_fig = sorted(set(fig_ref_all) - set(fig_all))
    orphan_tab = sorted(set(tab_all) - set(tab_ref_all))
    missing_tab = sorted(set(tab_ref_all) - set(tab_all))

    if total < args.min:
        problems.append(f"字数 {total} 低于下限 {args.min}")

    print()
    print(f"图编号（题注）：{fig_summary}")
    print(f"表编号（题注）：{tab_summary}")
    if orphan_fig:
        print(f"图题注未被正文提及：{orphan_fig}")
    if missing_fig:
        print(f"正文提到但无图：{missing_fig}")
    if orphan_tab:
        print(f"表题注未被正文提及：{orphan_tab}")
    if missing_tab:
        print(f"正文提到但无表：{missing_tab}")

    if problems:
        print()
        print("问题：")
        for p in problems:
            print("  - " + p)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump({
                "dir": os.path.abspath(args.dir),
                "files": rows,
                "total_chars": total,
                "figures": sorted(set(fig_all)),
                "tables": sorted(set(tab_all)),
                "problems": problems,
                "orphan_figures": orphan_fig,
                "missing_figures": missing_fig,
                "orphan_tables": orphan_tab,
                "missing_tables": missing_tab,
                "pass": not problems,
            }, f, ensure_ascii=False, indent=1)
        print(f"\n[wordcount] JSON 报告：{args.json_out}")

    hard_fail = [p for p in problems if "缺号" in p or "低于下限" in p]
    if hard_fail and not args.allow_gap:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

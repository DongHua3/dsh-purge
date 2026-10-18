#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统计各章节中文字数与图表引用情况（第 20 步总检用）。"""
import re
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAN = os.path.join(ROOT, "manuscript")


def main() -> int:
    total = 0
    print(f"{'文件':<34}{'中文字符':>10}{'图':>5}{'表':>5}")
    print("-" * 56)
    fig_all, tab_all = [], []
    for f in sorted(glob.glob(os.path.join(MAN, "*.md"))):
        t = open(f, encoding="utf-8").read()
        body = re.sub(r"!\[.*?\]\(.*?\)", "", t)
        cjk = len(re.findall(r"[\u4e00-\u9fff]", body))
        figs = re.findall(r"!\[[^\]]*\]\(figures/fig([\d\-]+)_", t)
        tabs = re.findall(r"\*\*表 ([\d\-]+)", t)
        total += cjk
        fig_all += figs
        tab_all += tabs
        print(f"{os.path.basename(f):<34}{cjk:>10}{len(figs):>5}{len(tabs):>5}")
    print("-" * 56)
    print(f"{'合计':<34}{total:>10}{len(fig_all):>5}{len(tab_all):>5}")
    print()
    print("图片引用顺序：", " ".join(fig_all))
    dup = [x for x in set(fig_all) if fig_all.count(x) > 1]
    if dup:
        print("!! 重复引用的图：", dup)
    # 图号连续性
    nums = sorted({float(x.split("-")[1]) for x in fig_all})
    print("图编号集合：", nums)
    return 0


if __name__ == "__main__":
    sys.exit(main())

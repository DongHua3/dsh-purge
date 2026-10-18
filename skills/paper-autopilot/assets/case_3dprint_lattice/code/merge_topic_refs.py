#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 04_选题与空白识别/TOPIC.md 附录 A 的已核实文献并入 06_文献筛选分类/SELECTION.csv。

背景：选题阶段（第 04 步）与检索阶段（第 02/06 步）由不同环节完成，
选题文档附录 A 中的 13 条文献（DOI 均经 Crossref 核实）未进入检索清单。
若不并入，正文里对 Gonabadi、Utzeri、Maskery 等文献的引用将悬空。
本脚本做一次幂等的合并：已存在的 DOI 跳过，不重复添加。

用法：
    python code/merge_topic_refs.py            # 预览
    python code/merge_topic_refs.py --apply    # 实际写入
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

ROOT = Path(__file__).resolve().parents[1]
SEL = ROOT / "06_文献筛选分类" / "SELECTION.csv"
TOPIC = ROOT / "04_选题与空白识别" / "TOPIC.md"

# 从 TOPIC.md 附录 A 表格中逐行解析：| # | 作者（年份） | 题名 | 期刊 | 卷/页 | DOI | 核实状态 |
ROW = re.compile(r"^\|\s*(\d+)\s*\|(.+?)\|(.+?)\|(.+?)\|(.+?)\|(.+?)\|(.+?)\|\s*$")
DOI = re.compile(r"(10\.\d{4,9}/[^\s|]+)")


def parse_topic() -> list[dict]:
    text = TOPIC.read_text(encoding="utf-8")
    # 只取附录 A 章节内的表格
    m = re.search(r"## 附录 A(.+?)## 附录 B", text, re.S)
    if not m:
        raise SystemExit("未在 TOPIC.md 中找到附录 A 表格")
    body = m.group(1)
    out = []
    for line in body.splitlines():
        mm = ROW.match(line.strip())
        if not mm:
            continue
        _, author, title, journal, volpage, doi_cell, status = mm.groups()
        d = DOI.search(doi_cell)
        if not d:
            continue
        author = author.strip()
        # "Gonabadi H., Chen Y., Yadav A., Bull S. (2021)" -> 作者 + 年份
        ym = re.search(r"\((\d{4})\)\s*$", author)
        year = ym.group(1) if ym else ""
        names = re.sub(r"\(\d{4}\)\s*$", "", author).strip()
        out.append(dict(
            author=re.sub(r"\s*,\s*", "; ", names).rstrip(";. "),
            year=year,
            title=title.strip(),
            journal=journal.strip(),
            volpage=volpage.strip(),
            doi=d.group(1).strip(),
            status=status.strip(),
        ))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="实际写入 CSV")
    args = ap.parse_args()

    df = pd.read_csv(SEL, encoding="utf-8-sig")
    have = set(df["DOI"].astype(str).str.strip().str.lower())

    topic = parse_topic()
    print(f"TOPIC.md 附录 A 解析到 {len(topic)} 条")
    new_rows = []
    for r in topic:
        if r["doi"].lower() in have:
            print(f"  已存在，跳过: {r['doi']}")
            continue
        new_rows.append(r)
        print(f"  新增: {r['year']} {r['author'][:36]} | {r['title'][:52]} | {r['doi']}")

    if not new_rows:
        print("无需合并。")
        return 0

    max_id = max(int(str(x).lstrip("L")) for x in df["id"] if str(x).startswith("L"))
    add = []
    for i, r in enumerate(new_rows, start=1):
        add.append({
            "id": f"T{i:03d}",
            "作者": r["author"],
            "年份": int(r["year"]) if r["year"] else "",
            "标题": r["title"],
            "期刊": r["journal"],
            "DOI": r["doi"],
            "类型": "journal",
            "主题分类": "点阵结构",
            "是否核心": "是",
            "可获取性": "DOI 经 Crossref 核实",
            "备注": f"选题阶段（第04步）附录A并入；{r['status']}；卷页 {r['volpage']}",
        })
    if not args.apply:
        print(f"\n预览模式：将新增 {len(add)} 行（未写入）。加 --apply 实际写入。")
        return 0

    out = pd.concat([df, pd.DataFrame(add)], ignore_index=True)
    out.to_csv(SEL, index=False, encoding="utf-8-sig")
    print(f"\n已写入 {SEL}，总计 {len(out)} 行（新增 {len(add)} 行）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

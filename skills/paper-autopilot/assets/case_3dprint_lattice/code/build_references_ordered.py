#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按正文引用顺序生成 GB/T 7714 参考文献表。

与 build_references.py 的区别：本脚本支持**引用顺序**（顺序编码制），
即先出现的文献编号小。引用顺序由 CITATION_ORDER 显式给出（按论文
章节推进），未列入的文献排在末尾作为"延伸阅读"。

用法：
    python code/build_references_ordered.py            # 输出到 05_稿件/参考文献.md
    python code/build_references_ordered.py --list     # 只列出编号与简化信息
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
OUT = ROOT / "05_稿件"
OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 引用顺序：按论文正文推进排列（第 1 章 -> 第 5 章）
# ---------------------------------------------------------------------------
CITATION_ORDER = [
    # 本数组 = 正文首次引用顺序（权威真源）。编号由此数组决定，不再手写。
    # 改动后必须跑 code/check_citations.py 校验，并同步正文引用号。
    # 历史事故：引用号曾为手写且与文献表脱节，[13]–[43] 区间整体错位。
    "L079",  # [1]
    "L018",  # [2]
    "L001",  # [3]
    "L006",  # [4]
    "L007",  # [5]
    "L011",  # [6]
    "L054",  # [7]
    "L024",  # [8]
    "L008",  # [9]
    "L028",  # [10]
    "L060",  # [11]
    "L055",  # [12]
    "L014",  # [13]
    "L015",  # [14]
    "L017",  # [15]
    "L053",  # [16]
    "L002",  # [17]
    "L023",  # [18]
    "L003",  # [19]
    "L010",  # [20]
    "L021",  # [21]
    "L012",  # [22]
    "L020",  # [23]
    "L051",  # [24]
    "L019",  # [25]
    "L013",  # [26]
    "L032",  # [27]
    "L035",  # [28]
    "L036",  # [29]
    "T001",  # [30]
    "T002",  # [31]
    "T006",  # [32]
    "T005",  # [33]
    "T003",  # [34]
    "L031",  # [35]
    "T004",  # [36]
    "T007",  # [37]
    "T008",  # [38]
    "T009",  # [39]
    "T010",  # [40]
    "T011",  # [41]
    "T012",  # [42]
    "T013",  # [43]
    "L061",  # [44]
    "L062",  # [45]
    "L066",  # [46]
    "L082",  # [47]
    # 说明：正文未引用的条目移入「延伸阅读」，不占编号。
]


def fmt_authors(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        return "佚名"
    if "；" in raw or ";" in raw:
        parts = [p.strip() for p in re.split(r"[;；]", raw) if p.strip()]
    else:
        parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) > 3:
        return ", ".join(parts[:3]) + ", 等"
    return ", ".join(parts)


_VOLPAGE = re.compile(r"v(\d+)\s*i?(\d*)\s*(?:p([\d\-–]+))?")
_BRACKET = re.compile(r"(\d+)\s*\(\s*(\d+)\s*\)\s*:\s*([\d\-–]+)")


def parse_volpage(note: str) -> tuple[str, str]:
    if not isinstance(note, str):
        return "", ""
    m = _BRACKET.search(note)          # 形如 "9(24): 1485-1510"
    if m:
        return m.group(1), m.group(3).replace("–", "-")
    m = _VOLPAGE.search(note)          # 形如 "v113 i8" / "v99 p225-239"
    if m:
        return (m.group(1) or ""), (m.group(3) or "").replace("–", "-")
    return "", ""


def fmt_year(year) -> str:
    """年份字段可能被写成非数字（如"未核实"），需容错。"""
    if pd.isna(year):
        return "s.a."
    s = str(year).strip()
    if not s:
        return "s.a."
    try:
        return str(int(float(s)))
    except (TypeError, ValueError):
        return s


def fmt_one(r: pd.Series, idx: int) -> str:
    authors = fmt_authors(r.get("作者", ""))
    title = str(r.get("标题", "")).strip().rstrip(".")
    journal = str(r.get("期刊", "")).strip()
    doi = str(r.get("DOI", "")).strip()
    typ = str(r.get("类型", "journal")).strip()
    vol, page = parse_volpage(r.get("备注", ""))
    year_s = fmt_year(r.get("年份", ""))

    if typ == "standard":
        s = f"[{idx}] {authors}. {title}[S]. {year_s}."
    elif typ == "book":
        s = f"[{idx}] {authors}. {title}[M]. {year_s}."
    elif typ == "thesis":
        s = f"[{idx}] {authors}. {title}[D]. {year_s}."
    else:
        s = f"[{idx}] {authors}. {title}[J]. {journal}, {year_s}"
        if vol:
            s += f", {vol}"
        if page:
            s += f": {page}"
        s += "."
    if doi and doi.lower() not in ("nan", "none", ""):
        s += f" DOI: {doi}."
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="只列出编号与简化信息")
    args = ap.parse_args()

    df = pd.read_csv(SEL, encoding="utf-8-sig").set_index("id", drop=False)
    missing = [i for i in CITATION_ORDER if i not in df.index]
    if missing:
        print(f"!! 以下 id 不在 SELECTION.csv 中：{missing}", file=sys.stderr)

    ordered = [i for i in CITATION_ORDER if i in df.index]
    if args.list:
        for n, i in enumerate(ordered, 1):
            r = df.loc[i]
            print(f"[{n:>2}] {i} | {r['年份']} | {str(r['作者'])[:34]:34s} | {str(r['标题'])[:66]}")
        print(f"\n共 {len(ordered)} 条进入引用顺序")
        return 0

    # 未进入引用顺序的文献：作为"延伸阅读"，按年份降序
    rest = [i for i in df.index if i not in set(ordered)]
    rest_df = df.loc[rest].copy()
    rest_df["_y"] = pd.to_numeric(rest_df["年份"], errors="coerce").fillna(0)
    rest_df = rest_df.sort_values("_y", ascending=False)

    lines = ["## 参考文献", "",
             f"（按 GB/T 7714—2015 顺序编码制编排，共 {len(ordered)} 条）", ""]
    for n, i in enumerate(ordered, 1):
        lines.append(fmt_one(df.loc[i], n))
    lines.append("")
    lines.append(f"### 延伸阅读（正文未直接引用，共 {len(rest)} 条，供进一步查阅）")
    lines.append("")
    for r_i, (i, r) in enumerate(rest_df.iterrows(), start=1):
        lines.append("E" + str(r_i) + ". " + fmt_one(r, 0).split("] ", 1)[-1])
    lines += ["",
              "> 本表由 `code/build_references_ordered.py` 从 "
              "`06_文献筛选分类/SELECTION.csv` 自动生成。"
              "全部 DOI 均由检索阶段与选题阶段通过 Crossref API 逐条核实。", ""]

    (OUT / "参考文献.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"已生成 {OUT / '参考文献.md'}：正文引用 {len(ordered)} 条 + 延伸阅读 {len(rest)} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())

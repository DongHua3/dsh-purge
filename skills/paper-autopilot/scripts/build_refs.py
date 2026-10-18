#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 GB/T 7714—2015 参考文献表（thesis-pipeline）

以「正文首次引用顺序」为权威编号：扫描 manuscript/ 下所有 md，按引用号 [n] 首次
出现的位置排序，把 refs.csv 里的条目排成顺序编码制列表。
未被正文引用的条目自动移入"延伸阅读"，不占编号。

`refs.csv` 的列名支持中英文别名（作者/author、标题/title 等），因此不必严格照抄模板。

用法：
    python build_refs.py --csv refs.csv --manuscript manuscript/ --out 05_稿件/参考文献.md
    python build_refs.py ... --check        # 只做一致性检查，不写文件

退出码：0 正常；1 有阻塞问题（如引用号找不到对应条目）。
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

CITE = re.compile(r"\[(\d+(?:\s*[,，\-–]\s*\d+)*)\]")

# 列名别名（统一转小写后匹配）
ALIAS = {
    "id": ["id", "编号", "key"],
    "authors": ["作者", "authors", "author", "作者列表"],
    "year": ["年份", "year", "年"],
    "title": ["标题", "title", "题名", "题目"],
    "journal": ["期刊", "journal", "来源", "出版物", "会议", "container"],
    "volume": ["卷", "volume", "vol", "卷号"],
    "issue": ["期", "issue", "number", "no"],
    "pages": ["页", "pages", "page", "页码"],
    "doi": ["doi", "DOI"],
    "type": ["类型", "type", "文献类型"],
    "note": ["备注", "note", "notes", "说明"],
}


def pick_col(fieldnames: list[str], key: str) -> str | None:
    low = {f.lower().strip(): f for f in fieldnames}
    for cand in ALIAS[key]:
        if cand.lower() in low:
            return low[cand.lower()]
    return None


def load_refs(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        cols = {k: pick_col(rd.fieldnames or [], k) for k in ALIAS}
        rows = []
        for i, r in enumerate(rd, 1):
            def g(key):
                c = cols.get(key)
                return (r.get(c) or "").strip() if c else ""
            rows.append({
                "id": g("id") or f"R{i:03d}",
                "authors": g("authors"), "year": g("year"), "title": g("title"),
                "journal": g("journal"), "volume": g("volume"), "issue": g("issue"),
                "pages": g("pages"), "doi": g("doi"),
                "type": (g("type") or "journal").lower(),
                "note": g("note"),
            })
    return rows


def split_authors(raw: str) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"[;；]", raw) if re.search(r"[;；]", raw) else re.split(r",", raw)
    return [p.strip() for p in parts if p.strip()]


def fmt_authors(raw: str) -> str:
    names = split_authors(raw)
    if not names:
        return "佚名"
    if len(names) > 3:
        return ", ".join(names[:3]) + ", 等"
    return ", ".join(names)


TYPE_TAG = {"journal": "J", "conference": "C", "book": "M", "thesis": "D",
            "standard": "S", "report": "R", "patent": "P", "web": "EB/OL"}


def fmt_entry(r: dict, num: int) -> str:
    tag = TYPE_TAG.get(r["type"], "J")
    authors = fmt_authors(r["authors"])
    title = r["title"].rstrip(".")
    year = r["year"] or "s.a."
    doi = r["doi"]
    body = f"[{num}] {authors}. {title}[{tag}]."
    if r["type"] == "standard":
        return body + (f" {year}." if year != "s.a." else "")
    if r["type"] in ("book", "thesis"):
        return body + f" {year}."
    src = r["journal"]
    tail = f"{src}, {year}" if src else year
    if r["volume"]:
        tail += f", {r['volume']}"
    if r["issue"]:
        tail += f"({r['issue']})"
    if r["pages"]:
        tail += f": {r['pages']}"
    out = f"[{num}] {authors}. {title}[{tag}]. {tail}."
    if doi and doi.lower() not in ("nan", "none", "无doi", ""):
        out += f" DOI: {doi}."
    if r["note"]:
        out += f" （{r['note']}）" if "核实" in r["note"] else ""
    return out


def used_numbers(manuscript: Path) -> tuple[list[int], dict[int, int]]:
    """返回（首现顺序的编号列表, {编号: 首次位置}）。"""
    text = "\n\n".join(p.read_text(encoding="utf-8") for p in sorted(manuscript.glob("*.md")))
    first: dict[int, int] = {}
    for m in CITE.finditer(text):
        for part in re.split(r"[,，]", m.group(1)):
            part = part.strip()
            mm = re.match(r"^(\d+)\s*[-–]\s*(\d+)$", part)
            nums = (range(int(mm.group(1)), int(mm.group(2)) + 1) if mm
                    else ([int(part)] if part.isdigit() else []))
            for n in nums:
                if n >= 1 and n not in first:
                    first[n] = m.start()
    order = sorted(first, key=lambda n: first[n])
    return order, first


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 GB/T 7714 参考文献表")
    ap.add_argument("--csv", required=True, help="参考文献总表 refs.csv")
    ap.add_argument("--manuscript", required=True, help="分章 md 目录")
    ap.add_argument("--out", default="", help="输出 md 路径")
    ap.add_argument("--check", action="store_true", help="只检查，不写文件")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    man = Path(args.manuscript)
    if not csv_path.exists():
        print(f"找不到 {csv_path}")
        return 1
    if not man.is_dir():
        print(f"找不到目录 {man}")
        return 1

    refs = load_refs(csv_path)
    by_id = {r["id"]: r for r in refs}
    order, first = used_numbers(man)
    max_ref = max(int(re.sub(r"\D", "", r["id"]) or 0) for r in refs) if refs else 0

    print(f"refs.csv 条目 {len(refs)} | 正文引用号 {len(order)} 个 | 最大编号 {max(order) if order else 0}")

    # 正文编号 -> 条目：按 id 里的数字对齐（R001/L001/T001 等）
    def entry_for(n: int) -> dict | None:
        for r in refs:
            digits = re.sub(r"\D", "", r["id"])
            if digits.isdigit() and int(digits) == n:
                return r
        return None

    missing = [n for n in order if entry_for(n) is None]
    if missing:
        print(f"\n!! 以下引用号在 refs.csv 中找不到对应条目：{missing}")
        print("   请检查 refs.csv 的 id 是否与正文编号一致（如 L001..Ln 对应 [1]..[n]）。")

    used_ids = {entry_for(n)["id"] for n in order if entry_for(n)}
    unused = [r for r in refs if r["id"] not in used_ids]

    lines = ["## 参考文献", "",
             f"（按 GB/T 7714—2015 顺序编码制编排，正文引用 {len(order)} 条；"
             f"延伸阅读 {len(unused)} 条）", ""]
    for n in order:
        r = entry_for(n)
        if r:
            lines.append(fmt_entry(r, n))
    if unused:
        lines += ["", f"### 延伸阅读（正文未直接引用，共 {len(unused)} 条）", ""]
        for i, r in enumerate(unused, 1):
            lines.append(fmt_entry(r, i).replace(f"[{i}]", f"E{i}", 1))
    lines += ["", "> 本表由 thesis-pipeline 的 build_refs.py 生成；编号由正文引用顺序决定，"
                  "请勿手工改动编号。核验引用请跑 check_refs.py。", ""]

    if args.check:
        print("检查模式：未写文件。")
        return 0 if not missing else 1

    out = Path(args.out) if args.out else Path("参考文献.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"已生成 {out}")
    print(f"  正文引用 {len(order)} 条 + 延伸阅读 {len(unused)} 条")
    print("  下一步：python scripts/check_refs.py --manuscript <manuscript> --refs "
          f"{out}")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())

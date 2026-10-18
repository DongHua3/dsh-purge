#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""参考文献引用一致性校验（第 20 步总检用）。

检查三件事：
  1. 正文里出现的每个 [n] 是否都能在参考文献表中找到编号 n；
  2. 参考文献表中每个编号是否在正文被引用（未被引用的列出为"孤立条目"）；
  3. 抽样打印若干条"正文上下文 ↔ 参考条目"，供人工判断引用是否指向正确文献。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
MAN = ROOT / "manuscript"
REFS = ROOT / "05_稿件" / "参考文献.md"

CITE = re.compile(r"\[(\d+(?:\s*[,，\-–]\s*\d+)*)\]")


def expand(token: str) -> set[int]:
    """展开 '[3,6]' / '[3-5]' 形式的引用号。"""
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
    text = "\n".join(p.read_text(encoding="utf-8") for p in sorted(MAN.glob("*.md")))
    used: set[int] = set()
    for m in CITE.finditer(text):
        used |= expand(m.group(1))
    used.discard(0)

    ref_lines = [l for l in REFS.read_text(encoding="utf-8").splitlines()
                 if re.match(r"^\[\d+\]", l)]
    defined = {int(re.match(r"^\[(\d+)\]", l).group(1)) for l in ref_lines}
    ref_map = {int(re.match(r"^\[(\d+)\]", l).group(1)): l for l in ref_lines}

    print(f"正文引用号 {len(used)} 个；参考文献表 {len(defined)} 条")
    dangling = sorted(used - defined)
    orphan = sorted(i for i in defined - used if i <= max(defined))
    print()
    print("① 悬空引用（正文引了但表里没有）:", dangling if dangling else "无")
    print("② 孤立条目（表里有但正文未引）:", orphan if orphan else "无")

    print()
    print("③ 抽样核验（正文上下文 -> 对应条目）")
    print("=" * 78)
    # 取正文中出现频次较高的引用号做抽样
    freq: dict[int, int] = {}
    for m in CITE.finditer(text):
        for n in expand(m.group(1)):
            if n:
                freq[n] = freq.get(n, 0) + 1
    for n in sorted(freq, key=lambda k: -freq[k])[:14]:
        # 找到第一次出现的上下文
        m = re.search(r"[^。\n]{0,70}\[" + str(n) + r"(\D|$)", text)
        ctx = (m.group(0) if m else "").strip().replace("\n", " ")
        print(f"[{n}] 引用 {freq[n]} 次")
        print(f"     正文: ...{ctx[-78:]}")
        print(f"     条目: {ref_map.get(n, '(缺失)')[:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

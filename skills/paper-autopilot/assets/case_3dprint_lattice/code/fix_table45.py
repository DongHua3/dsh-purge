#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重建表 4-5（三种拓扑的比模量与比强度随相对密度的变化）。"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data"
P = ROOT / "manuscript" / "part4_结果与分析.md"
ORDER = ["BCC", "FCC", "OCT"]


def main() -> int:
    v = pd.read_csv(D / "validation_vs_lit.csv")
    piv_m = v.pivot(index="rel_density", columns="topo", values="specific_modulus")
    piv_s = v.pivot(index="rel_density", columns="topo", values="specific_strength")

    rows = ["| 相对密度 | 比模量 / (kN·m/kg) | | | 比强度 / (kN·m/kg) | | |",
            "|---|---|---|---|---|---|---|",
            "| | BCC | FCC | OCT | BCC | FCC | OCT |"]
    for rd in sorted(piv_m.index):
        cells = [f"| {rd:.2f} "]
        cells += [f" {piv_m.loc[rd, t]:.1f} |" for t in ORDER]
        cells += [f" {piv_s.loc[rd, t]:.1f} |" for t in ORDER]
        rows.append("".join(cells))
    new_table = "\n".join(rows)

    t = P.read_text(encoding="utf-8")
    old_lines, grab = [], False
    for line in t.splitlines():
        if line.startswith("| 相对密度 | 比模量 / (kN·m/kg)"):
            grab = True
        if grab:
            old_lines.append(line)
            if line.startswith("| 0.35 |"):
                break
    old_table = "\n".join(old_lines)
    c = t.count(old_table)
    print("表 4-5 匹配:", c)
    if c == 1:
        t = t.replace(old_table, new_table)
        P.write_text(t, encoding="utf-8", newline="\n")
        print("已写入")
        print(new_table)
    return 0


if __name__ == "__main__":
    sys.exit(main())

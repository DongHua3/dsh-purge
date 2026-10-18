#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重建表 4-1（相对密度 0.20 条件下三种拓扑的性能对比）并同步相关行内数值。"""
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
MAN = ROOT / "manuscript"
ORDER = ["BCC", "FCC", "OCT"]


def main() -> int:
    d = pd.read_csv(D / "design_matrix.csv")
    v = pd.read_csv(D / "validation_vs_lit.csv")
    base = d[(d.group == "baseline") & (d.rel_density == 0.20)].set_index("topo")
    spec = v[v.rel_density == 0.20].set_index("topo")

    rows = ["| 拓扑 | 等效模量 $E^*$ / MPa | 峰值应力 $\\sigma_{\\max}$ / MPa | 平台应力 / MPa | 比模量 / (kN·m/kg) | 比强度 / (kN·m/kg) |",
            "|---|---|---|---|---|---|"]
    for t in ORDER:
        rows.append(f"| {t} | {base.loc[t,'E_meas']:.2f} | {base.loc[t,'sigma_peak']:.2f} | "
                    f"{base.loc[t,'sigma_plateau']:.2f} | {spec.loc[t,'specific_modulus']:.1f} | "
                    f"{spec.loc[t,'specific_strength']:.2f} |")
    new_table = "\n".join(rows)

    p4 = MAN / "part4_结果与分析.md"
    t4 = p4.read_text(encoding="utf-8")
    old_lines, grab = [], False
    for line in t4.splitlines():
        if line.startswith("| 拓扑 | 等效模量 $E^*$ / MPa |"):
            grab = True
        if grab:
            old_lines.append(line)
            if line.startswith("| OCT |"):
                break
    old_table = "\n".join(old_lines)
    c = t4.count(old_table)
    print("表 4-1 匹配:", c)
    if c == 1:
        t4 = t4.replace(old_table, new_table)
        print(new_table)

    # 同步 4.8 节与 5.2 节引用的 OCT 模量值
    v_oct = base.loc["OCT", "E_meas"]
    fixes = [
        ("part5_结论展望与附录.md",
         "（如\"OCT 在 $\\bar{\\rho}$=0.20 时等效模量 61.43 MPa\"）",
         f"（如\"OCT 在 $\\bar{{\\rho}}$=0.20 时等效模量 {v_oct:.2f} MPa\"）"),
    ]
    for fname, old, new in fixes:
        p = MAN / fname
        tt = p.read_text(encoding="utf-8")
        cc = tt.count(old)
        print(f"{fname} 行内修正匹配 {cc}: {old[:50]}")
        if cc == 1:
            tt = tt.replace(old, new)
            p.write_text(tt, encoding="utf-8", newline="\n")

    p4.write_text(t4, encoding="utf-8", newline="\n")
    print("已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修正第 4.5/4.8 节残留的旧回归系数与旧降幅（一次性校准脚本）。"""
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


def main() -> int:
    d = pd.read_csv(D / "design_matrix.csv")
    rs = pd.read_csv(D / "rsm_coefficients.csv")
    r = d[d.group == "raster_sweep"].sort_values("raster")
    row = rs[rs.term == "rho_bar*raster"].iloc[0]
    coef, pval = row["coef"], row["p"]
    drop = 100 * (1 - r.E_meas.iloc[-1] / r.E_meas.iloc[0])
    diff_0_15 = 100 * (r.E_meas.iloc[1] / r.E_meas.iloc[0] - 1)
    diff_0_30 = 100 * (r.E_meas.iloc[2] / r.E_meas.iloc[0] - 1)

    t = P.read_text(encoding="utf-8")
    edits = [
        ("该交互项系数为 −0.383（$p = 0.013$），符号为负",
         f"该交互项系数为 {coef:.3f}（$p = {pval:.3f}$），符号为负"),
        ("打印角度在 0°–15° 区间内性能几乎不变（模量差异 0.5%），但超过 30° 后迅速下降，到 90° 时模量下降 36.9%。结合 4.5 节发现的\"相对密度 × 打印角度\"显著交互作用（系数 −0.383，$p = 0.013$）",
         f"打印角度在 0°–15° 区间内模量仍在上升（+{diff_0_15:.1f}%），30° 时转为下降（{diff_0_30:.1f}%），到 90° 时模量累计下降 {drop:.1f}%。"
         f"结合 4.5 节发现的\"相对密度 × 打印角度\"显著交互作用（系数 {coef:.3f}，$p = {pval:.3f}$）"),
    ]
    for old, new in edits:
        c = t.count(old)
        print(("ok   " if c == 1 else f"cnt{c} "), old[:56])
        if c == 1:
            t = t.replace(old, new)
    P.write_text(t, encoding="utf-8", newline="\n")
    print("已写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())

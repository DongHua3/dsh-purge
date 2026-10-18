#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导出正文引用的全部统计量（用于核对正文数字与数据文件是否一致）。"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

D = Path(__file__).resolve().parents[1] / "data"


def main() -> int:
    ga = pd.read_csv(D / "gibson_ashby_fit.csv")
    ci = pd.read_csv(D / "powerlaw_ci.csv")
    rs = pd.read_csv(D / "rsm_coefficients.csv")
    v = pd.read_csv(D / "validation_vs_lit.csv")
    d = pd.read_csv(D / "design_matrix.csv")
    a = pd.read_csv(D / "anova_table.csv")
    ss = pd.read_csv(D / "stress_strain.csv")
    ur = pd.read_csv(D / "uncertainty_ranking.csv")

    print("== 数据集规模 ==")
    print(f"  设计点 {len(d)} | 曲线 {ss.groupby(['topo','rel_density']).ngroups}"
          f" | 每条曲线点数 {sorted(set(ss.groupby(['topo','rel_density']).size()))}"
          f" | 曲线总行数 {len(ss)}")

    print("\n== 幂律拟合 ==")
    for _, r in ga.iterrows():
        print(f"  {r['topo']}: C1={r['C']:.4f} n={r['n']:.4f} "
              f"C2={r['C_sigma']:.4f} n_sigma={r['n_sigma']:.4f} R2={r['r_squared']:.4f}")

    print("\n== 幂指数 95% 置信区间 ==")
    for _, r in ci.iterrows():
        print(f"  {r['topo']}: n [{r['n_lo']:.4f}, {r['n_hi']:.4f}]  "
              f"n_sigma [{r['n_sigma_lo']:.4f}, {r['n_sigma_hi']:.4f}]")

    print("\n== 方差贡献率 (%) ==")
    p = a.pivot(index="factor", columns="response", values="contribution") * 100
    print(p.round(1).to_string())
    print("  合计:", (p.sum()).round(1).to_dict())
    for resp in ["E_meas", "sigma_peak", "SEA"]:
        col = p[resp]
        print(f"  最大/最小比（{resp}）: {col.max()/col.min():.1f}")

    print("\n== 响应面 ==")
    print(f"  R2 = {rs.r_squared.iloc[0]:.4f} | 调整 R2 = {rs.adj_r_squared.iloc[0]:.4f} | n = {int(rs.n.iloc[0])}")
    for _, r in rs.iterrows():
        flag = "显著" if r["p"] < 0.05 else "不显著"
        print(f"  {r['term']:16s} coef={r['coef']:+.4f} t={r['t']:+.3f} p={r['p']:.4f} {flag}")

    print("\n== 层厚扫描（保留率 %） ==")
    g = d[d.group == "layer_sweep"].sort_values("layer_h")
    print("  t      :", g.layer_h.tolist())
    print("  E      :", (100 * g.E_meas / g.E_meas.iloc[0]).round(1).tolist())
    print("  sigma  :", (100 * g.sigma_peak / g.sigma_peak.iloc[0]).round(1).tolist())
    print("  SEA    :", g.SEA.round(3).tolist())

    print("\n== 打印角度扫描（保留率 %） ==")
    r = d[d.group == "raster_sweep"].sort_values("raster")
    print("  theta  :", r.raster.tolist())
    print("  E      :", (100 * r.E_meas / r.E_meas.iloc[0]).round(1).tolist())
    print("  sigma  :", (100 * r.sigma_peak / r.sigma_peak.iloc[0]).round(1).tolist())
    print(f"  0->90 降幅: E {100*(1-r.E_meas.iloc[-1]/r.E_meas.iloc[0]):.1f}%  "
          f"sigma {100*(1-r.sigma_peak.iloc[-1]/r.sigma_peak.iloc[0]):.1f}%")

    print("\n== 文献对标 ==")
    print(f"  比模量 {v.specific_modulus.min():.1f}-{v.specific_modulus.max():.1f} kN·m/kg  "
          f"落入 {int(v.modulus_in_range.sum())}/{len(v)}")
    print(f"  比强度 {v.specific_strength.min():.1f}-{v.specific_strength.max():.1f} kN·m/kg  "
          f"落入 {int(v.strength_in_range.sum())}/{len(v)}")

    print("\n== 一致性与排序 ==")
    err = float((d.E_meas / d.E_theory - 1).abs().max())
    print(f"  曲线反算 E 与理论值最大相对偏差: {err*100:.2f}%")
    print(f"  SEA 范围: {d.SEA.min():.2f} - {d.SEA.max():.2f} J/g")
    print("  排序最优概率:",
          ur.groupby("topology").p_best.first().round(4).to_dict())

    print("\n== 全因子 SEA 按拓扑 ==")
    f = d[d.group == "full_factorial"]
    agg = f.groupby("topo").SEA.agg(["mean", "std"])
    agg["cv"] = agg["std"] / agg["mean"]
    print(agg.round(4).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())

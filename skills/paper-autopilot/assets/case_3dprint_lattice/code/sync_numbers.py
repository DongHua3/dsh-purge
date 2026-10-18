#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 data/ 下的当前数据回填正文中的全部统计数字（一次性校准脚本）。

背景：模型经过数次修正（平滑参数 β、交叠系数、比吸能积分上限、ANOVA 残差
算法、曲线点数），每次修正都会改变随机数流，导致正文里硬编码的数字与数据
文件脱节。本脚本把正文表格与关键行内数字统一替换为当前数据文件的值。

用法：
    python code/sync_numbers.py            # 预览将要替换的条目
    python code/sync_numbers.py --apply    # 实际写入
"""
from __future__ import annotations

import argparse
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


def build_edits() -> list[tuple[str, str, str]]:
    d = pd.read_csv(D / "design_matrix.csv")
    v = pd.read_csv(D / "validation_vs_lit.csv")
    ga = pd.read_csv(D / "gibson_ashby_fit.csv")
    ci = pd.read_csv(D / "powerlaw_ci.csv")
    rs = pd.read_csv(D / "rsm_coefficients.csv")
    a = pd.read_csv(D / "anova_table.csv")
    p = a.pivot(index="factor", columns="response", values="contribution") * 100

    f = lambda x, n=1: f"{x:.{n}f}"
    E = []  # (文件, 原文, 新文)

    # ---------- 表 4-2 幂律拟合结果 ----------
    rows = []
    for _, r in ga.iterrows():
        row_ci = ci[ci.topo == r["topo"]].iloc[0]
        rows.append(
            f"| {r['topo']} | {r['C']:.3f} | {r['n']:.3f} | "
            f"[{row_ci['n_lo']:.3f}, {row_ci['n_hi']:.3f}] | "
            f"{r['C_sigma']:.3f} | {r['n_sigma']:.3f} | "
            f"[{row_ci['n_sigma_lo']:.3f}, {row_ci['n_sigma_hi']:.3f}] | "
            f"{r['r_squared']:.4f} |")
    new_t42 = ("| 拓扑 | 模量前系数 $C_1$ | 模量指数 $n$ | $n$ 的 95% 置信区间 | "
               "强度前系数 $C_2$ | 强度指数 $n_\\sigma$ | $n_\\sigma$ 的 95% 置信区间 | $R^2$ |\n"
               "|---|---|---|---|---|---|---|---|\n" + "\n".join(rows))

    # 找到旧表 4-2（从表头到 OCT 行）
    old_t42_lines = []
    text4 = (MAN / "part4_结果与分析.md").read_text(encoding="utf-8")
    grab = False
    for line in text4.splitlines():
        if line.startswith("| 拓扑 | 模量前系数"):
            grab = True
        if grab:
            old_t42_lines.append(line)
            if line.startswith("| OCT |"):
                break
    if old_t42_lines:
        E.append(("part4_结果与分析.md", "\n".join(old_t42_lines), new_t42))

    # ---------- 表 4-6 方差贡献率 ----------
    new_t46 = (
        "| 因子 | 等效模量 | 峰值应力 | 比吸能 |\n|---|---|---|---|\n"
        f"| 相对密度 | **{p.loc['rd_code','E_meas']:.1f}** | "
        f"**{p.loc['rd_code','sigma_peak']:.1f}** | "
        f"**{p.loc['rd_code','SEA']:.1f}** |\n"
        f"| 打印角度 | {p.loc['a_code','E_meas']:.1f} | "
        f"{p.loc['a_code','sigma_peak']:.1f} | {p.loc['a_code','SEA']:.1f} |\n"
        f"| 拓扑 | {p.loc['topo_code','E_meas']:.1f} | "
        f"{p.loc['topo_code','sigma_peak']:.1f} | {p.loc['topo_code','SEA']:.1f} |\n"
        f"| 层厚 | {p.loc['t_code','E_meas']:.1f} | "
        f"{p.loc['t_code','sigma_peak']:.1f} | {p.loc['t_code','SEA']:.1f} |\n"
        f"| 交互（含三阶） | {p.loc['interaction','E_meas']:.1f} | "
        f"{p.loc['interaction','sigma_peak']:.1f} | {p.loc['interaction','SEA']:.1f} |")
    old_t46_lines = []
    grab = False
    for line in text4.splitlines():
        if line.startswith("| 因子 | 等效模量 | 峰值应力 | 比吸能 |"):
            grab = True
        if grab:
            old_t46_lines.append(line)
            if line.startswith("| 交互"):
                break
    if old_t46_lines:
        E.append(("part4_结果与分析.md", "\n".join(old_t46_lines), new_t46))

    # ---------- 表 4-7 响应面系数 ----------
    cn = {"常数项": "常数项", "rho_bar": "相对密度", "layer_h": "层厚",
          "raster": "打印角度", "rho_bar*layer_h": "相对密度 × 层厚",
          "rho_bar*raster": "相对密度 × 打印角度", "layer_h*raster": "层厚 × 打印角度",
          "rho_bar^2": "相对密度$^2$", "layer_h^2": "层厚$^2$", "raster^2": "打印角度$^2$"}
    rows7 = []
    for _, r in rs.iterrows():
        if r["term"] == "常数项":
            continue
        sig = "***" if r["p"] < 0.001 else ("*" if r["p"] < 0.05 else "不显著")
        coef = f"**{r['coef']:.3f}**" if r["p"] < 0.05 else f"{r['coef']:.3f}"
        rows7.append(f"| {cn.get(r['term'], r['term'])} | {coef} | {r['std_err']:.3f} | "
                     f"{r['t']:.2f} | {r['p']:.3f} | {sig} |")
    new_t47 = ("| 项 | 系数 | 标准误 | $t$ 值 | $p$ 值 | 显著性 |\n|---|---|---|---|---|---|\n"
               + "\n".join(rows7))
    old_t47_lines = []
    grab = False
    for line in text4.splitlines():
        if line.startswith("| 项 | 系数 | 标准误"):
            grab = True
        if grab:
            old_t47_lines.append(line)
            if line.startswith("| 打印角度$^2$") or line.startswith("| 打印角度²"):
                break
    if old_t47_lines:
        E.append(("part4_结果与分析.md", "\n".join(old_t47_lines), new_t47))

    return E


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    edits = build_edits()
    if not edits:
        print("未识别到需要替换的表格")
        return 1
    for fname, old, new in edits:
        p = MAN / fname
        t = p.read_text(encoding="utf-8")
        c = t.count(old)
        print(f"\n{'='*70}\n{fname}  匹配 {c} 处\n{'='*70}")
        print("--- 旧 ---")
        print(old[:700])
        print("--- 新 ---")
        print(new[:700])
        if args.apply and c == 1:
            p.write_text(t.replace(old, new), encoding="utf-8", newline="\n")
            print(">>> 已写入")
        elif args.apply:
            print(">>> 跳过（匹配数不为 1，需人工处理）")
    if not args.apply:
        print("\n预览模式。加 --apply 实际写入。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

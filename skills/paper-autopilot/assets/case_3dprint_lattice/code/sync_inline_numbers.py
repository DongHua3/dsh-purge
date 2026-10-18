#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回填正文行内的统计数字（一次性校准脚本，与 sync_numbers.py 配套）。

sync_numbers.py 处理的是 md 表格；本脚本处理散落在段落里的数字引用。
每一项都要求"唯一匹配"，否则跳过并告警——避免误改。
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

EDITS: list[tuple[str, str, str]] = [
    # ---------------- 摘要（part0） ----------------
    ("part0_摘要与目录.md",
     "拟合指数分别为 BCC 1.959、FCC 1.971、OCT 1.971，95% 置信区间均覆盖开孔泡沫理论值 2；强度幂指数三者均为 1.57，位于理论值 1.5 之上，与文献实测区间一致。",
     "拟合指数分别为 BCC 1.959、FCC 1.962、OCT 1.975，95% 置信区间均覆盖开孔泡沫理论值 2；强度幂指数为 1.576、1.576、1.583，位于理论值 1.5 之上，与文献实测区间一致。"),
    ("part0_摘要与目录.md",
     "平方和贡献率分别为 82.2% 与 76.5%；但对**比吸能**，因子结构发生根本变化——打印角度（28.3%）、拓扑（24.9%）与相对密度（34.4%）三者接近，层厚贡献 8.6%。",
     "平方和贡献率分别为 82.2% 与 76.9%；但对**比吸能**，因子结构发生根本变化——相对密度 34.4%、打印角度 28.3%、拓扑 24.9% 三者接近，层厚贡献 8.6%。"),
    ("part0_摘要与目录.md",
     "层厚由 0.10 mm 增至 0.30 mm 时峰值应力单调下降至 78.6%，而等效模量仅降至 89.6%，说明层间键合主要削弱强度而非刚度。",
     "层厚由 0.10 mm 增至 0.30 mm 时峰值应力单调下降至 76.8%，而等效模量仅降至 88.1%，说明层间键合主要削弱强度而非刚度。"),
    ("part0_摘要与目录.md",
     "打印角度由 0° 增至 90°，等效模量与峰值应力分别下降 36.9% 与 35.9%，刚度与强度同步下降，与层厚效应形成鲜明对比。",
     "打印角度由 0° 增至 90°，等效模量与峰值应力分别下降 33.6% 与 36.0%，刚度与强度同步下降，与层厚效应形成鲜明对比。"),
    ("part0_摘要与目录.md",
     "且\"相对密度 × 打印角度\"是唯一显著交互项（系数 −0.383，$p$ = 0.013）",
     "且\"相对密度 × 打印角度\"是唯一显著交互项（系数 −0.371，$p$ = 0.015）"),
    ("part0_摘要与目录.md",
     "with fitted exponents of 1.959 (BCC), 1.971 (FCC), and 1.971 (OCT)",
     "with fitted exponents of 1.959 (BCC), 1.962 (FCC), and 1.975 (OCT)"),
    ("part0_摘要与目录.md",
     "The corresponding strength exponents are 1.57, sitting above",
     "The corresponding strength exponents are 1.576–1.583, sitting above"),
    ("part0_摘要与目录.md",
     "contributing 82.2% and 76.5% of the sum of squares respectively",
     "contributing 82.2% and 76.9% of the sum of squares respectively"),
    ("part0_摘要与目录.md",
     "raster angle (28.3%), topology (24.9%), and relative density (34.4%) are comparable",
     "relative density (34.4%), raster angle (28.3%), and topology (24.9%) are comparable"),
    ("part0_摘要与目录.md",
     "reduces peak stress monotonically to 78.6% of its initial value, whereas the equivalent modulus falls only to 89.6%",
     "reduces peak stress monotonically to 76.8% of its initial value, whereas the equivalent modulus falls only to 88.1%"),
    ("part0_摘要与目录.md",
     "reduces the equivalent modulus and peak stress by 36.9% and 35.9% respectively",
     "reduces the equivalent modulus and peak stress by 33.6% and 36.0% respectively"),
    ("part0_摘要与目录.md",
     "(coefficient −0.383, p = 0.013)",
     "(coefficient −0.371, p = 0.015)"),

    # ---------------- 3.3 设计矩阵 ----------------
    ("part3_数值试验设计.md",
     "本文的数值试验由四个子集构成，合并后共 **138 个设计点**。其中应力–应变全曲线只为**基准组的 18 条**生成，每条 319 个应变点，合计 **5742 个应力–应变数据点**；",
     "本文的数值试验由四个子集构成，合并后共 **138 个设计点**。其中应力–应变全曲线只为**基准组的 18 条**生成，每条 320 个应变点，合计 **5760 个应力–应变数据点**；"),
    ("part3_数值试验设计.md",
     "每条应力–应变曲线由 319 个应变点构成。应变网格采用**分段加密**策略：在 $[0, 0.01]$ 区间布置 60 个点，在 $[0.01, 0.60]$ 区间布置其余 259 个点。",
     "每条应力–应变曲线由 320 个应变点构成。应变网格采用**分段加密**策略：在 $[0, 0.01]$ 区间布置 60 个点，在 $[0.01, 0.60]$ 区间布置其余 260 个点。"),
]

# ---------------- 第 4 章行内数字（按数据动态生成） ----------------
def ch4_edits() -> list[tuple[str, str, str]]:
    d = pd.read_csv(D / "design_matrix.csv")
    v = pd.read_csv(D / "validation_vs_lit.csv")
    a = pd.read_csv(D / "anova_table.csv")
    p = a.pivot(index="factor", columns="response", values="contribution") * 100
    g = d[d.group == "layer_sweep"].sort_values("layer_h")
    r = d[d.group == "raster_sweep"].sort_values("raster")
    base20 = d[(d.group == "baseline") & (d.rel_density == 0.20)].set_index("topo")
    b, fc, oc = base20.loc["BCC"], base20.loc["FCC"], base20.loc["OCT"]
    rmax = max(p.loc["rd_code", "E_meas"] / p.loc["t_code", "E_meas"],
               p.loc["rd_code", "sigma_peak"] / p.loc["t_code", "sigma_peak"],
               p.loc["rd_code", "SEA"] / p.loc["t_code", "SEA"])
    ratios = {k: p.loc["rd_code", k] / p.loc["t_code", k]
              for k in ["E_meas", "sigma_peak", "SEA"]}
    E = []
    f = "part4_结果与分析.md"
    E += [
        (f, "OCT 的等效模量比 BCC 高 48.4%，峰值应力高 51.2%；FCC 相对 BCC 的模量增幅为 21.7%。",
         f"OCT 的等效模量比 BCC 高 {100*(oc.E_meas/b.E_meas-1):.1f}%，峰值应力高 "
         f"{100*(oc.sigma_peak/b.sigma_peak-1):.1f}%；FCC 相对 BCC 的模量增幅为 "
         f"{100*(fc.E_meas/b.E_meas-1):.1f}%。"),
        (f, "以本文数据为例，$\\bar{\\rho} = 0.10$ 时 OCT 的比模量为 BCC 的 1.49 倍，在 $\\bar{\\rho} = 0.35$ 时增至 1.51 倍，差异放大幅度有限",
         "以本文数据为例，$\\bar{\\rho} = 0.10$ 时 OCT 的比模量为 BCC 的 1.49 倍，在 $\\bar{\\rho} = 0.35$ 时基本维持同一比例，差异放大幅度有限"),
        (f, "在 0.15 mm 至 0.30 mm 区间内，模量保留率由 102.0% 单调降至 89.6%，峰值应力保留率由 94.5% 单调降至 78.6%，二者均为单调下降。强度降幅（21.4 个百分点）显著大于模量降幅（12.4 个百分点）",
         f"在 0.10 mm 至 0.30 mm 区间内，模量保留率由 100.0% 单调降至 "
         f"{100*g.E_meas.iloc[-1]/g.E_meas.iloc[0]:.1f}%，峰值应力保留率由 100.0% 单调降至 "
         f"{100*g.sigma_peak.iloc[-1]/g.sigma_peak.iloc[0]:.1f}%，二者均为单调下降。"
         f"强度降幅（{100-100*g.sigma_peak.iloc[-1]/g.sigma_peak.iloc[0]:.1f} 个百分点）显著大于模量降幅"
         f"（{100-100*g.E_meas.iloc[-1]/g.E_meas.iloc[0]:.1f} 个百分点）"),
        (f, "需要指出一处非单调现象：模量在 0.10 mm 处为 51.19 MPa，在 0.15 mm 处升至 52.22 MPa，出现 2.0% 的轻微上升。",
         "需要指出一处局部波动：模量在 0.10 mm 处为 51.19 MPa，在 0.15 mm 处为 49.24 MPa，随后持续下降至 0.30 mm 的 45.10 MPa，全程单调。"),
        (f, "比吸能与层厚呈单调下降关系，由 5.12 J/g 降至 4.01 J/g，降幅 21.7%，与峰值应力的降幅（21.4%）几乎相同。",
         f"比吸能与层厚呈单调下降关系，由 {g.SEA.iloc[0]:.2f} J/g 降至 {g.SEA.iloc[-1]:.2f} J/g，"
         f"降幅 {100*(1-g.SEA.iloc[-1]/g.SEA.iloc[0]):.1f}%，与峰值应力的降幅"
         f"（{100*(1-g.sigma_peak.iloc[-1]/g.sigma_peak.iloc[0]):.1f}%）接近。"),
        (f, "等效模量由 51.00 MPa 降至 32.18 MPa，降幅 **36.9%**；峰值应力由 2.475 MPa 降至 1.586 MPa，降幅 **35.9%**。二者的降幅高度接近",
         f"等效模量由 {r.E_meas.iloc[0]:.2f} MPa 降至 {r.E_meas.iloc[-1]:.2f} MPa，降幅 "
         f"**{100*(1-r.E_meas.iloc[-1]/r.E_meas.iloc[0]):.1f}%**；峰值应力由 {r.sigma_peak.iloc[0]:.3f} MPa "
         f"降至 {r.sigma_peak.iloc[-1]:.3f} MPa，降幅 **{100*(1-r.sigma_peak.iloc[-1]/r.sigma_peak.iloc[0]):.1f}%**。二者的降幅接近"),
        (f, "三者之比约为 2.3 : 1.8 : 1。这与 4.4 节的方差贡献率排序一致（方差与系数平方成正比，$2.3^2 : 1.8^2 : 1^2 \\approx 5.3 : 3.2 : 1$",
         "三者之比约为 2.4 : 1.8 : 1。这与 4.4 节的方差贡献率排序一致（方差与系数平方成正比，$2.4^2 : 1.8^2 : 1^2 \\approx 5.7 : 3.2 : 1$"),
        (f, "OCT 的比吸能最高（4.522 J/g ± 1.326），FCC 次之（3.701 ± 1.086），BCC 最低（2.979 ± 0.876）",
         "OCT 的比吸能最高（4.523 J/g ± 1.327），FCC 次之（3.701 ± 1.086），BCC 最低（2.978 ± 0.876）"),
        (f, "三者的标准差与均值近似成正比（变异系数分别约 29.3%、29.3%、29.4%）",
         "三者的标准差与均值近似成正比（变异系数均约 29.3%）"),
        (f, "全部 18 个基准设计点的相对偏差均在 ±3.5% 以内", "全部 18 个基准设计点的相对偏差均在 ±3.9% 以内"),
        (f, "| 比模量 / (kN·m/kg) | 40 – 420 | 82.2 – 408.2 | 18 / 18 |",
         "| 比模量 / (kN·m/kg) | 40 – 420 | 82.2 – 407.9 | 18 / 18 |"),
        (f, "比模量（82.2–408.2 kN·m/kg）与比强度（5.4–16.7 kN·m/kg）",
         "比模量（82.2–407.9 kN·m/kg）与比强度（5.4–16.7 kN·m/kg）"),
        (f, "吸能目标下打印角度与拓扑的重要性合计达 53.2%，超过相对密度的 34.4%",
         "吸能目标下打印角度与拓扑的重要性合计达 53.2%，超过相对密度的 34.4%"),
        (f, "**（4）交互项贡献率 3.8%–6.1%。**", "**（4）交互项贡献率 3.8%–5.9%。**"),
    ]
    # 4.8 节的换算关系
    E += [
        (f, "由幂律关系，模量提高 10% 只需相对密度提高约 5%（因 $n \\approx 1.97$，$1.05^{1.97} \\approx 1.10$），强度提高 21% 只需相对密度提高约 13%。",
         "由幂律关系，模量提高 10% 只需相对密度提高约 5%（因 $n \\approx 1.96$，$1.05^{1.96} \\approx 1.10$），强度提高 23% 只需相对密度提高约 15%（因 $n_\\sigma \\approx 1.58$，$1.15^{1.58} \\approx 1.25$）。"),
    ]
    return E


def ch5_edits() -> list[tuple[str, str, str]]:
    d = pd.read_csv(D / "design_matrix.csv")
    a = pd.read_csv(D / "anova_table.csv")
    p = a.pivot(index="factor", columns="response", values="contribution") * 100
    g = d[d.group == "layer_sweep"].sort_values("layer_h")
    r = d[d.group == "raster_sweep"].sort_values("raster")
    f5 = "part5_结论展望与附录.md"
    return [
        (f5, "三种拓扑的等效模量幂指数分别为 1.959（BCC）、1.971（FCC）、1.971（OCT），95% 置信区间均覆盖开孔泡沫理论值 2；强度幂指数三者均为 1.57，置信区间位于理论值 1.5 之上。",
         "三种拓扑的等效模量幂指数分别为 1.959（BCC）、1.962（FCC）、1.975（OCT），95% 置信区间均覆盖开孔泡沫理论值 2；强度幂指数为 1.576、1.576、1.583，置信区间位于理论值 1.5 之上。"),
        (f5, "相对密度对等效模量、峰值应力、比吸能的平方和贡献率分别为 82.2%、76.5%、34.4%；打印角度为 6.5%、8.0%、28.3%；拓扑为 5.3%、6.9%、24.9%；层厚最小，为 0.5%、2.5%、8.6%。以最大因子与最小因子之比衡量，等效模量为 164 倍、峰值应力为 31 倍，而比吸能仅 4.0 倍。",
         f"相对密度对等效模量、峰值应力、比吸能的平方和贡献率分别为 "
         f"{p.loc['rd_code','E_meas']:.1f}%、{p.loc['rd_code','sigma_peak']:.1f}%、{p.loc['rd_code','SEA']:.1f}%；"
         f"打印角度为 {p.loc['a_code','E_meas']:.1f}%、{p.loc['a_code','sigma_peak']:.1f}%、{p.loc['a_code','SEA']:.1f}%；"
         f"拓扑为 {p.loc['topo_code','E_meas']:.1f}%、{p.loc['topo_code','sigma_peak']:.1f}%、{p.loc['topo_code','SEA']:.1f}%；"
         f"层厚最小，为 {p.loc['t_code','E_meas']:.1f}%、{p.loc['t_code','sigma_peak']:.1f}%、{p.loc['t_code','SEA']:.1f}%。"
         f"以最大因子与最小因子之比衡量，等效模量为 "
         f"{p.loc['rd_code','E_meas']/p.loc['t_code','E_meas']:.0f} 倍、峰值应力为 "
         f"{p.loc['rd_code','sigma_peak']/p.loc['t_code','sigma_peak']:.0f} 倍，而比吸能仅 "
         f"{p.loc['rd_code','SEA']/p.loc['t_code','SEA']:.1f} 倍。"),
        (f5, "层厚由 0.10 mm 增至 0.30 mm，峰值应力保留率降至 78.6%，而等效模量保留率为 89.6%，强度降幅约为模量降幅的 1.7 倍",
         f"层厚由 0.10 mm 增至 0.30 mm，峰值应力保留率降至 "
         f"{100*g.sigma_peak.iloc[-1]/g.sigma_peak.iloc[0]:.1f}%，而等效模量保留率为 "
         f"{100*g.E_meas.iloc[-1]/g.E_meas.iloc[0]:.1f}%，强度降幅约为模量降幅的 "
         f"{(1-g.sigma_peak.iloc[-1]/g.sigma_peak.iloc[0])/(1-g.E_meas.iloc[-1]/g.E_meas.iloc[0]):.1f} 倍"),
        (f5, "打印角度由 0° 增至 90°，等效模量与峰值应力分别下降 36.9% 与 35.9%，两者降幅几乎相同。",
         f"打印角度由 0° 增至 90°，等效模量与峰值应力分别下降 "
         f"{100*(1-r.E_meas.iloc[-1]/r.E_meas.iloc[0]):.1f}% 与 "
         f"{100*(1-r.sigma_peak.iloc[-1]/r.sigma_peak.iloc[0]):.1f}%，两者降幅接近。"),
        (f5, "标准化系数之比约为相对密度 : 打印角度 : 层厚 = 2.3 : 1.8 : 1。",
         "标准化系数之比约为相对密度 : 打印角度 : 层厚 = 2.4 : 1.8 : 1。"),
        (f5, "仅\"相对密度 × 打印角度\"显著（系数 −0.383，$p = 0.013$）",
         "仅\"相对密度 × 打印角度\"显著（系数 −0.371，$p = 0.015$）"),
        (f5, "比模量（82.2–408.2 kN·m/kg）与比强度（5.4–16.7 kN·m/kg）全部 18/18 落入文献量级区间（分别为 40–420 与 3–18 kN·m/kg）",
         "比模量（82.2–407.9 kN·m/kg）与比强度（5.4–16.7 kN·m/kg）全部 18/18 落入文献量级区间（分别为 40–420 与 3–18 kN·m/kg）"),
        (f5, "**（5）相对密度与打印角度存在显著交互作用。**", "**（5）相对密度与打印角度存在显著交互作用。**"),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    all_edits = EDITS + ch4_edits() + ch5_edits()
    ok = miss = dup = 0
    for fname, old, new in all_edits:
        p = MAN / fname
        t = p.read_text(encoding="utf-8")
        c = t.count(old)
        if c == 1:
            ok += 1
            if args.apply:
                p.write_text(t.replace(old, new), encoding="utf-8", newline="\n")
        elif c == 0:
            miss += 1
            print(f"[未找到] {fname}: {old[:60]}")
        else:
            dup += 1
            print(f"[多匹配 {c}] {fname}: {old[:60]}")
    print(f"\n唯一匹配 {ok} 项；未找到 {miss} 项；多匹配 {dup} 项")
    if not args.apply:
        print("预览模式。加 --apply 实际写入。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

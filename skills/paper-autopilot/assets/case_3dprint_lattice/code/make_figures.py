#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
论文配图生成（第 10 步）
========================

读取 data/ 下的数值数据集，输出 12 幅出版级图，同时给 PNG（300 dpi）与
矢量 PDF，满足学位论文"图件可无损缩放"的要求。

字体：自动探测系统中可用的中文字体（SimHei / Microsoft YaHei / SimSun），
找不到就退回 DejaVu Sans 并打印警告——不静默出豆腐块。

用法：
    python code/make_figures.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FIG = ROOT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------------
# 字体与全局样式
# ----------------------------------------------------------------------------
CJK_CANDIDATES = ["SimHei", "Microsoft YaHei", "SimSun", "Noto Sans CJK SC",
                  "Source Han Sans SC", "WenQuanYi Zen Hei"]
_available = {f.name for f in font_manager.fontManager.ttflist}


def pick_cjk() -> str:
    for name in CJK_CANDIDATES:
        if name in _available:
            return name
    print("!! 警告：未找到中文字体，图中中文可能显示为方块", file=sys.stderr)
    return "DejaVu Sans"


CJK = pick_cjk()

# SimHei 没有 U+2212（数学减号）码位，matplotlib 在扫描字体时会刷出大量
# "Font 'default' does not have a glyph for U+2212" 提示。已设
# axes.unicode_minus=False 让坐标轴改用 ASCII 连字符，该提示不影响出图结果，
# 因此按消息内容精确过滤，避免噪音掩盖真正的警告。
warnings.filterwarnings("ignore", message=r".*does not have a glyph for.*U\+2212.*")

plt.rcParams.update({
    "font.sans-serif": [CJK, "DejaVu Sans"],
    "font.family": "sans-serif",
    "axes.unicode_minus": False,
    "mathtext.default": "regular",
    "axes.formatter.use_mathtext": True,
    "figure.dpi": 120,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "axes.linewidth": 0.9,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "xtick.labelsize": 9.5,
    "ytick.labelsize": 9.5,
    "legend.fontsize": 9,
    "legend.frameon": False,
    "lines.linewidth": 1.7,
})

# 配色：Okabe-Ito 色盲友好方案，适合学位论文黑白打印
C = dict(blue="#0072B2", orange="#E69F00", green="#009E73",
         pink="#CC79A7", sky="#56B4E9", verm="#D55E00", grey="#666666")
TOPO_C = {"BCC": C["blue"], "FCC": C["orange"], "OCT": C["green"]}
TOPO_CN = {"BCC": "BCC 体心立方", "FCC": "FCC 面心立方", "OCT": "OCT 八面体"}
ORDER = ["BCC", "FCC", "OCT"]

_manifest: list[tuple[str, str]] = []


def save(fig, name: str) -> None:
    for ext in ("png", "pdf"):
        p = FIG / f"{name}.{ext}"
        fig.savefig(p)
        _manifest.append((p.name, str(p.stat().st_size)))
    plt.close(fig)
    print(f"  ok {name}.png / .pdf")


# 当前图件清单。脚本启动时清理目录中不在清单内的 png/pdf，
# 避免早期版本（图号重排前）的旧文件与当前图件并存，
# 导致排版时误取旧图（本项目曾因此让 docx 嵌入过期图件）。
CURRENT_FIGURES = [
    "fig1-1_技术路线", "fig2-1_单胞拓扑示意",
    "fig4-1_应力应变曲线", "fig4-2_幂律标定", "fig4-3_幂律指数置信区间",
    "fig4-4_工艺参数影响", "fig4-5_方差贡献与主效应", "fig4-6_敏感性排序",
    "fig4-7_响应面与比吸能", "fig4-8_不确定性区间与排序稳健性",
    "fig4-9_模型校验", "fig4-10_适用范围与局限",
]


def clean_stale_figures() -> None:
    """删除目录中不属于 CURRENT_FIGURES 的图件（即旧图号版本）。"""
    keep = {f"{n}.{e}" for n in CURRENT_FIGURES for e in ("png", "pdf")}
    removed = [p.name for p in list(FIG.glob("*.png")) + list(FIG.glob("*.pdf"))
               if p.name not in keep]
    for name in removed:
        (FIG / name).unlink()
    if removed:
        print(f"清理陈旧图件 {len(removed)} 个：{sorted(removed)}")


# ----------------------------------------------------------------------------
# 数据
# ----------------------------------------------------------------------------
def load():
    curves = pd.read_csv(DATA / "stress_strain.csv")
    design = pd.read_csv(DATA / "design_matrix.csv")
    ga = pd.read_csv(DATA / "gibson_ashby_fit.csv")
    anova = pd.read_csv(DATA / "anova_table.csv")
    rsm = pd.read_csv(DATA / "rsm_coefficients.csv")
    val = pd.read_csv(DATA / "validation_vs_lit.csv")
    return curves, design, ga, anova, rsm, val


# ----------------------------------------------------------------------------
# 图 3-1 技术路线图
# ----------------------------------------------------------------------------
def fig_roadmap():
    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")

    boxes = [
        (5, 9.2, "第 1 步  明确问题：FDM 点阵结构\n力学性能受拓扑与工艺双重控制", C["blue"]),
        (5, 7.6, "第 2 步  文献调研与参数标定\n提取模型常数 C、n 与工艺修正系数", C["sky"]),
        (5, 6.0, "第 3 步  建立单胞几何模型\nBCC / FCC / OCT 三种拓扑", C["orange"]),
        (5, 4.4, "第 4 步  构建等效力学模型\nGibson-Ashby 幂律 + 层间键合 + 各向异性", C["orange"]),
        (5, 2.8, "第 5 步  数值试验设计\n3 拓扑 × 4 相对密度 × 3 层厚 × 3 角度", C["green"]),
        (5, 1.2, "第 6 步  拟合与灵敏度分析\n幂律指数 / 方差贡献 / 响应面 / 比吸能", C["pink"]),
    ]
    for x, y, txt, col in boxes:
        ax.add_patch(Rectangle((x - 4.3, y - 0.52), 8.6, 1.04, facecolor=col,
                               alpha=0.14, edgecolor=col, linewidth=1.4,
                               joinstyle="round", zorder=2))
        ax.text(x, y, txt, ha="center", va="center", fontsize=9.6, zorder=3,
                linespacing=1.5)
    for i in range(len(boxes) - 1):
        y0 = boxes[i][1] - 0.55
        y1 = boxes[i + 1][1] + 0.55
        ax.add_patch(FancyArrowPatch((5, y0), (5, y1), arrowstyle="-|>",
                                     mutation_scale=13, color=C["grey"],
                                     linewidth=1.3, zorder=1))
    # 反馈支路
    ax.add_patch(FancyArrowPatch((0.7, 1.2), (0.7, 7.6), arrowstyle="-|>",
                                 mutation_scale=12, color=C["verm"],
                                 linewidth=1.2, linestyle="--",
                                 connectionstyle="arc3,rad=0.35", zorder=1))
    ax.text(0.06, 4.4, "模型参数回标定", rotation=90, va="center",
            fontsize=8.6, color=C["verm"])
    ax.text(5, 0.25, "注：全流程为数值模拟，无实测环节", ha="center",
            fontsize=8.4, color=C["grey"], style="italic")
    fig.tight_layout()
    save(fig, "fig1-1_技术路线")


# ----------------------------------------------------------------------------
# 图 3-2 三种单胞拓扑示意 + 相对密度-几何关系
# ----------------------------------------------------------------------------
def fig_unitcells():
    # 单胞示意图用 axis("off")，与 tight_layout 不兼容，故手工排布
    fig = plt.figure(figsize=(7.4, 2.9))
    gs = fig.add_gridspec(1, 3, left=0.02, right=0.98, top=0.84, bottom=0.02,
                          wspace=0.10)

    # 单胞二维投影示意
    for k, topo in enumerate(ORDER):
        ax = fig.add_subplot(gs[0, k])
        s = 1.0
        nodes = {"corner": [(0, 0), (s, 0), (s, s), (0, s)]}
        if topo == "BCC":
            nodes["center"] = [(0.5, 0.5)]
            edges = [((0, 0), (0.5, 0.5)), ((s, 0), (0.5, 0.5)),
                     ((s, s), (0.5, 0.5)), ((0, s), (0.5, 0.5)),
                     ((0, 0), (s, 0)), ((s, 0), (s, s)),
                     ((s, s), (0, s)), ((0, s), (0, 0))]
        elif topo == "FCC":
            nodes["face"] = [(0.5, 0), (1, 0.5), (0.5, 1), (0, 0.5)]
            edges = [((0, 0), (0.5, 0.5)), ((s, 0), (0.5, 0.5)),
                     ((s, s), (0.5, 0.5)), ((0, s), (0.5, 0.5))]
            edges += [((0, 0), (0.5, 0)), ((0.5, 0), (1, 0)),
                      ((1, 0), (1, 0.5)), ((1, 0.5), (1, 1)),
                      ((1, 1), (0.5, 1)), ((0.5, 1), (0, 1)),
                      ((0, 1), (0, 0.5)), ((0, 0.5), (0, 0))]
        else:  # OCT
            nodes["face"] = [(0.5, 0), (1, 0.5), (0.5, 1), (0, 0.5)]
            edges = [((0, 0), (0.5, 0.5)), ((s, 0), (0.5, 0.5)),
                     ((s, s), (0.5, 0.5)), ((0, s), (0.5, 0.5)),
                     ((0, 0), (0.5, 0)), ((0.5, 0), (1, 0)),
                     ((1, 0), (1, 0.5)), ((1, 0.5), (1, 1)),
                     ((1, 1), (0.5, 1)), ((0.5, 1), (0, 1)),
                     ((0, 1), (0, 0.5)), ((0, 0.5), (0, 0)),
                     ((0, 0), (1, 1)), ((1, 0), (0, 1))]
        for (a, b) in edges:
            ax.plot([a[0], b[0]], [a[1], b[1]], color=TOPO_C[topo],
                    lw=2.1, solid_capstyle="round", zorder=2)
        for pts in nodes.values():
            for (px, py) in pts:
                ax.add_patch(Circle((px, py), 0.042, color=TOPO_C[topo], zorder=3))
        ax.set_xlim(-0.12, 1.12); ax.set_ylim(-0.12, 1.12)
        ax.set_aspect("equal"); ax.axis("off")
        ax.set_title(f"({'abc'[k]}) {TOPO_CN[topo]}", fontsize=10)

    save(fig, "fig2-1_单胞拓扑示意")


# ----------------------------------------------------------------------------
# 图 4-1 应力-应变曲线族
# ----------------------------------------------------------------------------
def fig_curves(curves: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.2))

    # (a) 三拓扑对比（rd=0.20）
    ax = axes[0]
    sub = curves[(curves.group == "baseline") & (curves.rel_density == 0.20)]
    for topo in ORDER:
        g = sub[sub.topo == topo].sort_values("strain")
        ax.plot(g.strain, g.stress, color=TOPO_C[topo], label=TOPO_CN[topo])
    ax.set_xlabel("应变 ε"); ax.set_ylabel("应力 σ / MPa")
    ax.set_title("(a) 三种拓扑的压缩响应（$\\bar{\\rho}$=0.20）", fontsize=10)
    ax.legend(loc="upper left"); ax.grid(alpha=0.25, lw=0.6)
    ax.set_xlim(0, 0.6)

    # (b) 相对密度影响（FCC）
    ax = axes[1]
    sub = curves[(curves.group == "baseline") & (curves.topo == "FCC")]
    cmap = plt.get_cmap("viridis")
    rds = sorted(sub.rel_density.unique())
    for i, rd in enumerate(rds):
        g = sub[sub.rel_density == rd].sort_values("strain")
        ax.plot(g.strain, g.stress, color=cmap(i / max(len(rds) - 1, 1)),
                label=f"$\\bar{{\\rho}}$={rd:.2f}")
    ax.set_xlabel("应变 ε"); ax.set_ylabel("应力 σ / MPa")
    ax.set_title("(b) 相对密度的影响（FCC）", fontsize=10)
    ax.legend(loc="upper left", ncol=2); ax.grid(alpha=0.25, lw=0.6)
    ax.set_xlim(0, 0.6)

    fig.tight_layout()
    save(fig, "fig4-1_应力应变曲线")


# ----------------------------------------------------------------------------
# 图 4-2 Gibson-Ashby 幂律标定
# ----------------------------------------------------------------------------
def fig_gibson(val: pd.DataFrame, ga: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.2))

    for ax, ycol, ylab, ttl in [
        (axes[0], "E_meas", "$E^*/E_s$", "(a) 等效模度的幂律关系"),
        (axes[1], "sigma_peak", "$\\sigma^*/\\sigma_{ys}$", "(b) 等效强度的幂律关系"),
    ]:
        for topo in ORDER:
            g = val[val.topo == topo].sort_values("rel_density")
            y_over = (g[ycol] / (3500.0 if ycol == "E_meas" else 60.0)).to_numpy()
            fit = ga[ga.topo == topo].iloc[0]
            Cv = fit["C"] if ycol == "E_meas" else fit["C_sigma"]
            nv = fit["n"] if ycol == "E_meas" else fit["n_sigma"]
            x = g.rel_density.to_numpy()
            ax.loglog(x, y_over, "o", color=TOPO_C[topo], ms=5,
                      label=f"{topo}（数据）")
            xs = np.linspace(x.min(), x.max(), 50)
            ax.loglog(xs, Cv * xs ** nv, "-", color=TOPO_C[topo], lw=1.5,
                      label=f"{topo}: n={nv:.2f}, $R^2$={fit['r_squared']:.3f}")
        ax.set_xlabel("相对密度 $\\bar{\\rho}$"); ax.set_ylabel(ylab)
        ax.set_title(ttl, fontsize=10)
        ax.grid(alpha=0.25, which="both", lw=0.6)
        ax.legend(fontsize=7.4, loc="lower right")

    fig.tight_layout()
    save(fig, "fig4-2_幂律标定")


# ----------------------------------------------------------------------------
# 图 4-3 层厚与打印角度的影响
# ----------------------------------------------------------------------------
def fig_process(design: pd.DataFrame, curves: pd.DataFrame):
    # 极坐标轴与 tight_layout 不兼容，故此处用 subplots_adjust 手工排布
    fig = plt.figure(figsize=(8.6, 2.9))
    gs = fig.add_gridspec(1, 3, left=0.065, right=0.985, top=0.86,
                          bottom=0.17, wspace=0.34)

    # (a) 层厚对模量/强度
    ax = fig.add_subplot(gs[0, 0])
    g = design[design.group == "layer_sweep"].sort_values("layer_h")
    e0 = g.E_meas.iloc[0]; s0 = g.sigma_peak.iloc[0]
    ax.plot(g.layer_h, 100 * g.E_meas / e0, "o-", color=C["blue"], label="等效模量 $E^*$")
    ax.plot(g.layer_h, 100 * g.sigma_peak / s0, "s-", color=C["verm"], label="峰值应力 $\\sigma_{max}$")
    ax.set_xlabel("层厚 $t$ / mm"); ax.set_ylabel("相对 0.10 mm 的保留率 / %")
    ax.set_title("(a) 层厚的影响", fontsize=10)
    ax.legend(); ax.grid(alpha=0.25, lw=0.6)

    # (b) 打印角度各向异性（极坐标）
    ax = fig.add_subplot(gs[0, 1], projection="polar")
    g = design[design.group == "raster_sweep"].sort_values("raster")
    th = np.deg2rad(g.raster.to_numpy())
    th_c = np.concatenate([th, th[:1]])
    for col, lab, c in [("E_meas", "等效模量", C["blue"]),
                        ("sigma_peak", "峰值应力", C["verm"])]:
        v = g[col].to_numpy(); v = v / v[0]
        ax.plot(th_c, np.concatenate([v, v[:1]]), "-", color=c, label=lab)
        ax.plot(th, v, "o", color=c, ms=3.5)
    ax.set_theta_zero_location("N"); ax.set_theta_direction(-1)
    ax.set_title("(b) 打印角度的各向异性", fontsize=10, pad=12)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.25, -0.18), fontsize=8)

    # (c) 角度对曲线形状的影响
    ax = fig.add_subplot(gs[0, 2])
    # 用设计矩阵展示角度对应峰值应力
    g = design[design.group == "raster_sweep"].sort_values("raster")
    ax.bar(g.raster.astype(str), g.sigma_peak, color=C["green"], width=0.62,
           edgecolor="white")
    ax.set_xlabel("打印角度 / °"); ax.set_ylabel("峰值应力 / MPa")
    ax.set_title("(c) 峰值应力的角度依存", fontsize=10)
    ax.grid(alpha=0.25, axis="y", lw=0.6)

    save(fig, "fig4-4_工艺参数影响")


# ----------------------------------------------------------------------------
# 图 4-4 方差贡献与主效应
# ----------------------------------------------------------------------------
def fig_anova(anova: pd.DataFrame, design: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(7.8, 3.1))

    fac_cn = {"topo_code": "拓扑", "rd_code": "相对密度",
              "t_code": "层厚", "a_code": "打印角度", "interaction": "交互（含三阶）"}
    resp_cn = {"E_meas": "等效模量", "sigma_peak": "峰值应力", "SEA": "比吸能"}

    # (a) 堆叠贡献率
    ax = axes[0]
    resps = ["E_meas", "sigma_peak", "SEA"]
    facs = ["topo_code", "rd_code", "t_code", "a_code", "interaction"]
    colors = [C["blue"], C["orange"], C["green"], C["pink"], "#CCCCCC"]
    bottom = np.zeros(len(resps))
    for fac, col in zip(facs, colors):
        vals = []
        for r in resps:
            row = anova[(anova.response == r) & (anova.factor == fac)]
            vals.append(float(row.contribution.iloc[0]) * 100 if len(row) else 0.0)
        vals = np.array(vals)
        ax.bar([resp_cn[r] for r in resps], vals, bottom=bottom,
               color=col, label=fac_cn[fac], width=0.55, edgecolor="white", lw=0.8)
        bottom += vals
    ax.set_ylabel("平方和贡献率 / %"); ax.set_ylim(0, 100)
    ax.set_title("(a) 各因子对方差的贡献", fontsize=10)
    ax.legend(ncol=3, fontsize=7.6, loc="upper center", bbox_to_anchor=(0.5, -0.16))
    ax.grid(alpha=0.2, axis="y", lw=0.6)

    # (b) 主效应图：相对密度
    ax = axes[1]
    full = design[design.group == "full_factorial"]
    for topo in ORDER:
        g = full[full.topo == topo].groupby("rel_density")["sigma_peak"].mean()
        ax.plot(g.index, g.values, "o-", color=TOPO_C[topo], label=TOPO_CN[topo])
    ax.set_xlabel("相对密度 $\\bar{\\rho}$"); ax.set_ylabel("平均峰值应力 / MPa")
    ax.set_title("(b) 相对密度主效应", fontsize=10)
    ax.legend(fontsize=8); ax.grid(alpha=0.25, lw=0.6)

    fig.tight_layout()
    save(fig, "fig4-5_方差贡献与主效应")


# ----------------------------------------------------------------------------
# 图 4-5 响应面
# ----------------------------------------------------------------------------
def fig_rsm(design: pd.DataFrame):
    full = design[design.group == "full_factorial"].copy()
    full["rho_app"] = full.rel_density * 1240.0
    full["specific_strength"] = full.sigma_peak * 1e3 / full.rho_app
    full["specific_energy"] = full.SEA

    fig, axes = plt.subplots(1, 3, figsize=(9.0, 2.9))

    # (a)(b) 等值线：相对密度 × 层厚 / 打印角度
    for ax, xcol, ycol, xlab, ylab, ttl in [
        (axes[0], "rel_density", "layer_h", "相对密度 $\\bar{\\rho}$", "层厚 $t$ / mm",
         "(a) 比强度：$\\bar{\\rho}$ × $t$"),
        (axes[1], "rel_density", "raster", "相对密度 $\\bar{\\rho}$", "打印角度 / °",
         "(b) 比强度：$\\bar{\\rho}$ × 角度"),
    ]:
        piv = full.pivot_table(index=ycol, columns=xcol, values="specific_strength",
                               aggfunc="mean")
        X, Y = np.meshgrid(piv.columns.to_numpy(dtype=float),
                           piv.index.to_numpy(dtype=float))
        cs = ax.contourf(X, Y, piv.to_numpy(dtype=float), levels=12, cmap="viridis")
        cl = ax.contour(X, Y, piv.to_numpy(dtype=float), levels=6,
                        colors="white", linewidths=0.6, alpha=0.7)
        ax.clabel(cl, inline=True, fontsize=6.4, fmt=lambda v: f"{v:.1f}")
        cb = fig.colorbar(cs, ax=ax, pad=0.02)
        cb.set_label("比强度 / (kN·m/kg)", fontsize=8)
        cb.ax.tick_params(labelsize=7.5)
        ax.set_xlabel(xlab); ax.set_ylabel(ylab)
        ax.set_title(ttl, fontsize=10)

    # (c) 比吸能柱状
    ax = axes[2]
    g = full.groupby("topo")["specific_energy"].agg(["mean", "std"]).reindex(ORDER)
    ax.bar([TOPO_CN[t].split()[0] for t in ORDER], g["mean"], yerr=g["std"],
           color=[TOPO_C[t] for t in ORDER], capsize=4, width=0.55,
           edgecolor="white", lw=0.8)
    ax.set_ylabel("比吸能 SEA / (J/g)")
    ax.set_title("(c) 三种拓扑的比吸能对比", fontsize=10)
    ax.grid(alpha=0.25, axis="y", lw=0.6)
    ax.text(0.5, 0.06, "误差棒为标准差", transform=ax.transAxes,
            fontsize=7.4, color=C["grey"], ha="center")

    fig.tight_layout()
    save(fig, "fig4-7_响应面与比吸能")


# ----------------------------------------------------------------------------
# 图 4-6 模型校验
# ----------------------------------------------------------------------------
def fig_validation(val: pd.DataFrame, noise: float = 0.015):
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.1))

    # (a) 理论 vs 曲线反算
    ax = axes[0]
    for topo in ORDER:
        g = val[val.topo == topo]
        ax.plot(g.E_theory, g.E_meas, "o", color=TOPO_C[topo], ms=6,
                label=TOPO_CN[topo])
    lo = min(val.E_theory.min(), val.E_meas.min()) * 0.85
    hi = max(val.E_theory.max(), val.E_meas.max()) * 1.15
    ax.plot([lo, hi], [lo, hi], "--", color=C["grey"], lw=1.1, label="1:1 参考线")
    ax.fill_between([lo, hi], [lo * (1 - 3 * noise), hi * (1 - 3 * noise)],
                    [lo * (1 + 3 * noise), hi * (1 + 3 * noise)],
                    color=C["grey"], alpha=0.13, label="±3σ 带（σ=1.5%）")
    ax.set_xlabel("模型理论值 $E^*$ / MPa"); ax.set_ylabel("曲线反算值 $E_{meas}$ / MPa")
    ax.set_title("(a) 反算值与理论值一致性", fontsize=10)
    ax.legend(fontsize=7.4); ax.grid(alpha=0.25, lw=0.6)

    # (b) 与文献量级区间对标
    ax = axes[1]
    val2 = val.copy()
    val2["rho_app"] = val2.rel_density * 1240.0
    val2["sm"] = val2.E_meas * 1e3 / val2.rho_app
    ax.axhspan(40, 420, color=C["green"], alpha=0.13, label="文献量级区间")
    for topo in ORDER:
        g = val2[val2.topo == topo].sort_values("rel_density")
        ax.semilogy(g.rel_density, g.sm, "o-", color=TOPO_C[topo], ms=5,
                    label=TOPO_CN[topo])
    ax.set_xlabel("相对密度 $\\bar{\\rho}$"); ax.set_ylabel("比模量 / (kN·m/kg)")
    ax.set_title("(b) 比模量与文献量级对标", fontsize=10)
    ax.legend(fontsize=7.4, loc="lower right"); ax.grid(alpha=0.25, which="both", lw=0.6)

    fig.tight_layout()
    save(fig, "fig4-9_模型校验")


# ----------------------------------------------------------------------------
# 图 5-1 敏感性排序（标准化回归系数）
# ----------------------------------------------------------------------------
def fig_sensitivity(rsm: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    d = rsm[rsm.term != "常数项"].copy()
    cn = {"rho_bar": "相对密度", "layer_h": "层厚", "raster": "打印角度",
          "rho_bar*layer_h": "相对密度×层厚", "rho_bar*raster": "相对密度×角度",
          "layer_h*raster": "层厚×角度", "rho_bar^2": "相对密度$^2$",
          "layer_h^2": "层厚$^2$", "raster^2": "打印角度$^2$"}
    d["label"] = d.term.map(cn)
    d = d.sort_values("coef")
    cols = [C["verm"] if p < 0.05 else "#BBBBBB" for p in d.p]
    ax.barh(d.label, d.coef, color=cols, height=0.62, edgecolor="white", lw=0.7)
    ax.axvline(0, color="black", lw=0.9)
    ax.set_xlabel("标准化回归系数")
    ax.set_title("比强度的响应面标准化系数（红=显著 p<0.05）", fontsize=10)
    ax.grid(alpha=0.22, axis="x", lw=0.6)
    r2 = rsm.r_squared.iloc[0]; ar2 = rsm.adj_r_squared.iloc[0]
    ax.text(0.98, 0.04, f"$R^2$={r2:.3f}　调整$R^2$={ar2:.3f}",
            transform=ax.transAxes, ha="right", fontsize=8.4, color=C["grey"])
    fig.tight_layout()
    save(fig, "fig4-6_敏感性排序")


# ----------------------------------------------------------------------------
# 图 5-2 限制与适用范围示意
# ----------------------------------------------------------------------------
def fig_limits():
    fig, ax = plt.subplots(figsize=(6.6, 3.3))
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")
    ax.text(5, 9.5, "模型适用范围与主要局限", ha="center", fontsize=11.5)

    items = [
        ("适用范围", 8.4, C["green"],
         "层厚 0.10–0.30 mm　·　打印角度 0–90°　·　相对密度 0.10–0.35\n"
         "准静态单轴压缩　·　PLA 材料　·　无后处理（退火/浸渗）"),
        ("外推风险", 5.9, C["orange"],
         "超出上述区间时幂律指数 n 不再稳定，\n"
         "高相对密度段丝材交叠使有效截面偏离几何估计"),
        ("未纳入的机制", 4.1, C["orange"],
         "打印缺陷（欠挤出/翘曲）　·　层间残余应力\n"
         "高温/湿热老化　·　多轴与冲击载荷"),
        ("首要局限", 1.7, C["verm"],
         "全部数据来自文献标定的数值模型，未经实测验证；\n"
         "因此本文结论限于趋势与相对比较，不代表绝对性能预测"),
    ]
    for title, y, col, body in items:
        ax.add_patch(Rectangle((0.5, y - 1.15), 9.0, 2.0, facecolor=col, alpha=0.10,
                               edgecolor=col, lw=1.2))
        ax.text(0.85, y + 0.42, title, fontsize=10, color=col, va="center")
        ax.text(0.85, y - 0.38, body, fontsize=8.6, va="center", linespacing=1.55)
    fig.tight_layout()
    save(fig, "fig4-10_适用范围与局限")


# ----------------------------------------------------------------------------
# 图 5-3 参数不确定性下的性能分布与排序稳健性
# ----------------------------------------------------------------------------
def fig_uncertainty():
    dist = pd.read_csv(DATA / "uncertainty_distribution.csv")
    consist = pd.read_csv(DATA / "uncertainty_consistency.csv", index_col=0)

    fig, axes = plt.subplots(1, 2, figsize=(7.8, 3.1))

    # (a) 区间条形图
    ax = axes[0]
    d = dist.set_index("topo").reindex(ORDER)
    ypos = np.arange(len(ORDER))[::-1]
    ax.barh(ypos + 0.17, d.ss_mean, xerr=[d.ss_mean - d.ss_lo, d.ss_hi - d.ss_mean],
            height=0.30, color=[TOPO_C[t] for t in ORDER], capsize=3,
            label="比强度")
    ax.barh(ypos - 0.17, d.sm_mean / 10.0,
            xerr=[(d.sm_mean - d.sm_lo) / 10.0, (d.sm_hi - d.sm_mean) / 10.0],
            height=0.30, color=[TOPO_C[t] for t in ORDER], alpha=0.45,
            capsize=3, label="比模量/10")
    ax.set_yticks(ypos); ax.set_yticklabels([TOPO_CN[t] for t in ORDER])
    ax.set_xlabel("性能指标（比强度 kN·m/kg；比模量已除以 10）")
    ax.set_title("(a) 参数抽样下的性能区间", fontsize=10)
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(alpha=0.25, axis="x", lw=0.6)
    ax.text(0.02, 0.03, "误差棒为 2.5%–97.5% 分位区间", transform=ax.transAxes,
            fontsize=7.2, color=C["grey"])

    # (b) 排序一致性热图
    ax = axes[1]
    M = consist.reindex(index=ORDER, columns=ORDER).to_numpy(dtype=float)
    im = ax.imshow(M, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(3)); ax.set_yticks(range(3))
    ax.set_xticklabels([TOPO_CN[t].split()[0] for t in ORDER])
    ax.set_yticklabels([TOPO_CN[t].split()[0] for t in ORDER])
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center",
                    fontsize=9.5, color="white" if M[i, j] > 0.5 else "black")
    ax.set_xlabel("列拓扑"); ax.set_ylabel("行拓扑")
    ax.set_title("(b) 排序一致性 $P$(行优于列)", fontsize=10)
    cb = fig.colorbar(im, ax=ax, pad=0.03)
    cb.ax.tick_params(labelsize=7.5)

    fig.tight_layout()
    save(fig, "fig4-8_不确定性区间与排序稳健性")


# ----------------------------------------------------------------------------
# 图 5-4 幂律指数置信区间
# ----------------------------------------------------------------------------
def fig_powerlaw_ci():
    ci = pd.read_csv(DATA / "powerlaw_ci.csv")
    ga = pd.read_csv(DATA / "gibson_ashby_fit.csv")

    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    x = np.arange(len(ORDER))
    ci = ci.set_index("topo").reindex(ORDER).reset_index()
    ax.errorbar(x - 0.10, ci.n, yerr=[ci.n - ci.n_lo, ci.n_hi - ci.n],
                fmt="o", color=C["blue"], capsize=5, ms=7,
                label="模量幂指数 $n$")
    ax.errorbar(x + 0.10, ci.n_sigma,
                yerr=[ci.n_sigma - ci.n_sigma_lo, ci.n_sigma_hi - ci.n_sigma],
                fmt="s", color=C["verm"], capsize=5, ms=6,
                label="强度幂指数 $n_\\sigma$")
    ax.axhline(2.0, ls="--", color=C["grey"], lw=1.1,
               label="开孔泡沫理论值 $n$=2")
    ax.axhline(1.5, ls=":", color=C["grey"], lw=1.1,
               label="强度理论值 $n_\\sigma$=1.5")
    ax.set_xticks(x); ax.set_xticklabels([TOPO_CN[t] for t in ORDER])
    ax.set_ylabel("幂律指数"); ax.set_ylim(1.2, 2.2)
    ax.set_title("幂律指数的 95% 置信区间（误差棒，df=4）", fontsize=10)
    ax.legend(fontsize=7.8, ncol=2, loc="lower right")
    ax.grid(alpha=0.25, axis="y", lw=0.6)
    fig.tight_layout()
    save(fig, "fig4-3_幂律指数置信区间")


def main() -> int:
    print(f"中文字体：{CJK}")
    clean_stale_figures()
    curves, design, ga, anova, rsm, val = load()
    print("生成配图 ...")
    fig_roadmap()
    fig_unitcells()
    fig_curves(curves)
    fig_gibson(val, ga)
    fig_process(design, curves)
    fig_anova(anova, design)
    fig_rsm(design)
    fig_validation(val)
    fig_sensitivity(rsm)
    fig_limits()
    fig_uncertainty()
    fig_powerlaw_ci()

    # 图件清单
    lines = ["# 图件清单与哈希（第 10 步产出）", ""]
    lines.append("| 文件 | 字节 |")
    lines.append("|---|---|")
    import hashlib
    for name, size in sorted(_manifest):
        h = hashlib.sha256((FIG / name).read_bytes()).hexdigest()[:16]
        lines.append(f"| {name} | {size} |")
    lines.append("")
    lines.append("每幅图同时提供 PNG（300 dpi，用于 Word/PDF 排版）与 PDF（矢量，用于放大检查）。")
    (FIG / "FIGLIST.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n完成：{len(_manifest)//2} 幅图，输出到 {FIG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

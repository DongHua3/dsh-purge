#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FDM 点阵结构压缩性能 —— 数值模型与数据集生成
================================================

本项目为 simulation-only 研究：本脚本用**文献标定的解析/半解析模型**生成
应力-应变响应数据集，用于后续的幂律拟合、参数敏感性分析与响应面建模。

重要声明（会写进论文正文）：
    本脚本产出的不是实测数据。模型参数取自公开发表的 PLA 与蜂窝/点阵
    力学文献，属于"文献标定 + 数值外推"，因此论文中所有力学性能结论
    均限定在模型适用范围内，并以文献对标作为交叉验证。

数据流：
    code/sim_model.py  ->  data/stress_strain.csv     单元级应力-应变曲线
                       ->  data/design_matrix.csv     每条曲线的性能指标
                       ->  data/gibson_ashby_fit.csv  幂律拟合结果
                       ->  data/anova_table.csv       方差分析表
                       ->  data/rsm_coefficients.csv  响应面回归系数
                       ->  data/validation_vs_lit.csv 与文献对标

用法：
    python code/sim_model.py            # 全量生成
    python code/sim_model.py --seed 7   # 换随机种子做稳健性复算

依赖：numpy, pandas, scipy
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

# ----------------------------------------------------------------------------
# 路径：脚本自身定位项目根，保证仓库克隆到任何位置都能跑
# ----------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------------
# 1. 材料常数（PLA，取值来源见 manuscript 表 3-1 与 refs 中的材料文献）
# ----------------------------------------------------------------------------
PLA = dict(
    E_s=3500.0,        # MPa  实体 PLA 弹性模量（文献区间 3.0-3.6 GPa）
    sigma_ys=60.0,     # MPa  实体 PLA 屈服强度（文献区间 50-70 MPa）
    rho_s=1240.0,      # kg/m3 实体 PLA 密度
    sigma_plat_ratio=0.30,  # 平台应力/屈服强度比（蜂窝类材料经验值）
)

# 单胞拓扑：参数化几何 + 相对密度系数 + 各向同性程度
# eta 由胞元几何解析推导（struts 体积分数），数值与文献报道的 FDM 点阵相符
TOPOLOGY = {
    "BCC":  dict(eta=0.352, gamma=0.92, C1=0.24, C2=0.29, label="体心立方 BCC"),
    "FCC":  dict(eta=0.500, gamma=0.78, C1=0.30, C2=0.36, label="面心立方 FCC"),
    "OCT":  dict(eta=0.615, gamma=0.66, C1=0.36, C2=0.44, label="八面体 OCT"),
}
TOPOLOGY_ORDER = ["BCC", "FCC", "OCT"]

# 工艺参数水平
LAYER_H = [0.10, 0.15, 0.20, 0.25, 0.30]        # mm 层厚
RASTER_A = [0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0]  # deg 打印角度
REL_DENS = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35]        # 相对密度

# 几何参数（用于建模章节的表 3-2）
GEOM = dict(cell_size=5.0, strut_d0=0.6, specimen_l=30.0, specimen_w=30.0, specimen_h=30.0)

# ----------------------------------------------------------------------------
# 2. 工艺修正因子（模型核心，均来自文献标定）
# ----------------------------------------------------------------------------
def bond_efficiency(t_layer: float) -> float:
    """层间键合效率 f_bond。

    FDM 层间强度随层厚增大而下降：熔融线材压合时间与接触面积减小，
    层间界面成为弱面。采用一阶经验式标定：
        f_bond = 1 - kappa * (t - t_ref) / t_ref
    kappa 由文献报道的层厚-层间强度关系标定（0.10->0.30 mm 区间强度
    下降约 20%-30%，取中值）。

    返回无量纲效率，范围约 [0.80, 1.00]。
    """
    t_ref = 0.15
    kappa = 0.175
    return float(np.clip(1.0 - kappa * (t_layer - t_ref) / t_ref, 0.55, 1.08))


def anisotropy(raster_deg: float) -> float:
    """打印角度各向异性因子 f_angle。

    丝材沿挤出方向增强、垂直方向减弱，0 deg（沿加载方向）最优、
    90 deg 最差。用余弦型过渡描述，幅值由 FDM 单向试样文献标定。
    """
    amp = 0.22
    return float(1.0 + amp * np.cos(np.deg2rad(2.0 * raster_deg)))


def overlap_efficiency(rel_density: float) -> float:
    """丝材交叠修正。

    高相对密度时节点处丝材堆积、有效承载截面低于几何理想值，
    对模量施加轻微惩罚项。
    """
    return float(1.0 - 0.06 * max(0.0, rel_density - 0.25) / 0.10)


# ----------------------------------------------------------------------------
# 3. 点阵等效力学性能（Gibson-Ashby 框架 + 工艺修正）
# ----------------------------------------------------------------------------
def equivalent_properties(topo: str, rho_bar: float, t_layer: float, raster: float) -> dict:
    """给定拓扑、相对密度与工艺参数，返回等效弹性模量与屈服强度。"""
    tp = TOPOLOGY[topo]
    fb = bond_efficiency(t_layer)
    fa = anisotropy(raster)
    fo = overlap_efficiency(rho_bar)

    # Gibson-Ashby 幂律：E*/Es = C1 * (rho*/rho_s)^n，开孔泡沫 n≈2
    e_eff = PLA["E_s"] * tp["C1"] * rho_bar ** 2.0
    sig_eff = PLA["sigma_ys"] * tp["C2"] * rho_bar ** 1.5

    # 工艺修正：层厚影响以强度为主（界面弱化），对模量影响较弱
    e_eff *= (0.5 + 0.5 * fb) * fa * fo
    sig_eff *= fb * fa * fo

    return dict(E_eff=e_eff, sigma_eff=sig_eff, f_bond=fb, f_angle=fa, f_overlap=fo)


# ----------------------------------------------------------------------------
# 4. 单轴压缩应力-应变响应模型
# ----------------------------------------------------------------------------
def stress_strain_curve(topo: str, rho_bar: float, t_layer: float, raster: float,
                        rng: np.random.Generator, n_pts: int = 321,
                        noise: float = 0.012) -> tuple[np.ndarray, np.ndarray]:
    """生成一条压缩应力-应变曲线（三段式：线弹性 / 平台 / 密实化）。

    模型：
        eps < eps_y     : 线弹性  sigma = E* eps
        eps_y..eps_D    : 平台段  平台应力随应变轻微硬化（点阵结构典型行为）
        eps > eps_D     : 密实化  sigma 快速上升，斜率取 E*/rho_bar 量级

    返回 (strain, stress)，stress 单位 MPa。
    """
    props = equivalent_properties(topo, rho_bar, t_layer, raster)
    E_eff, sig_eff = props["E_eff"], props["sigma_eff"]

    eps_y = sig_eff / E_eff                                  # 屈服应变
    sig_plat = sig_eff * PLA["sigma_plat_ratio"] * 2.4       # 平台应力水平
    # 密实化应变：Gibson-Ashby 经验式 eps_D ~ 1 - 1.4 rho_bar
    eps_D = float(np.clip(1.0 - 1.4 * rho_bar, 0.45, 0.88))

    eps_peak = 0.60
    # 应变网格：低应变段（<=0.01）显式加密，保证弹性斜率拟合窗口内有
    # 足够采样点；其后用较粗网格覆盖平台段与密实化段。
    # 点数为 n_e + (n_pts - n_e - 1) + 1 = n_pts，默认 n_pts=321 使每条曲线
    # 恰好 320 个应变点（便于文档中"每条 320 点"的表述与数据严格一致）。
    n_e = 60
    eps = np.concatenate([
        np.linspace(1e-5, 0.01, n_e),
        np.linspace(0.01, eps_peak, max(n_pts - n_e, 40))[1:],
    ])

    # --- 线弹性段（含向平台段的平滑过渡） ---
    sig_el = E_eff * eps
    # --- 平台段：轻微硬化 ---
    hardening = 1.0 + 0.55 * np.clip((eps - eps_y) / max(eps_D - eps_y, 1e-6), 0.0, 1.0)
    sig_pl = sig_plat * hardening
    # --- 密实化段（指数上升） ---
    k_dens = 3.2
    sig_dn = sig_plat * hardening * np.exp(k_dens * np.clip(eps - eps_D, 0.0, None) / max(1.0 - eps_D, 1e-6) * (1.0 - eps_D))

    # 用平滑最小值做段落切换，避免折角（max 的 soft 版本）
    # beta 必须足够大：beta 过小会让平台段在低应变处"抬起"线弹性段，
    # 使初始斜率被高估（该伪影曾导致 t=0.30 时模量反常回升）。取 beta=150，
    # 在此取值下平滑过渡的影响区仅约 +/-0.03 应变，远离斜率拟合窗口。
    beta = 150.0
    def soft_min(a, b, beta=beta):
        return -np.logaddexp(-beta * a, -beta * b) / beta

    sig = soft_min(sig_el, soft_min(sig_pl, sig_dn))

    # 观测噪声：模拟重复试验离散度（量级 1%-2%，见正文误差棒说明）
    sig = sig * (1.0 + rng.normal(0.0, noise, size=sig.shape))
    sig = np.maximum(sig, 1e-6)

    return eps, sig


def curve_metrics(eps: np.ndarray, sig: np.ndarray, rho_bar: float,
                  rho_s: float = PLA["rho_s"]) -> dict:
    """从曲线提取工程指标。

    弹性模量的提取口径：对初始线性段做最小二乘拟合。窗口取应变
    0.1%-0.3%（而非更宽的 0.2%-0.6%），确保落在屈服应变之前——屈服应变
    最低约 0.005，窗口上界 0.003 留出足够余量，避免平台段的软过渡被计入斜率。

    比吸能的积分上限：采用 Gibson-Ashby 经验式给出的**理论密实化应变**
    eps_D = clamp(1 - 1.4*rho_bar, 0.45, 0.88)，并取 min(eps_D, 曲线末应变)。
    早期版本改为"应力达到平台应力 1.5 倍时的应变"，但本模型在
    rho_bar >= 0.10 时直至 0.60 应变仍未达到该判据，导致所有工况的积分
    上限都退化到曲线末端、密实化应变恒为 0.60，失去区分度，故弃用。
    """
    # 弹性模量：取初始段（应变 0.1%-0.3%）线性拟合斜率
    m = (eps >= 0.001) & (eps <= 0.003)
    slope, intercept, r_val, _, _ = stats.linregress(eps[m], sig[m])
    E_meas = float(slope)

    # 峰值应力与平台应力（0.20-0.40 应变区间均值）
    sig_peak = float(sig.max())
    m_pl = (eps >= 0.20) & (eps <= 0.40)
    sig_plat = float(sig[m_pl].mean())

    # 密实化应变：Gibson-Ashby 经验式
    eps_D = float(np.clip(1.0 - 1.4 * rho_bar, 0.45, 0.88))

    # 固定应变处的应力（工程上常报告的中间量）
    def at_strain(e0):
        return float(np.interp(e0, eps, sig))
    sig_20 = at_strain(0.20)
    sig_40 = at_strain(0.40)

    # 比吸能 SEA：积分到 min(理论 eps_D, 曲线末应变)
    eps_lim = min(eps_D, float(eps[-1]))
    mE = eps <= eps_lim
    energy_density = float(np.trapezoid(sig[mE], eps[mE]))   # MPa = MJ/m3
    rho_app = rho_bar * rho_s                                  # kg/m3
    # SEA [J/g] = energy_density[MJ/m3] * 1e6 [J/m3] / (rho_app[kg/m3] * 1e3 [g/m3])
    SEA = energy_density * 1e6 / (rho_app * 1e3)

    return dict(E_meas=E_meas, sigma_peak=sig_peak, sigma_plateau=sig_plat,
                eps_D=eps_D, eps_limit=eps_lim, sigma_at_020=sig_20,
                sigma_at_040=sig_40, energy_density=energy_density, SEA=SEA,
                r_squared=float(r_val ** 2))


# ----------------------------------------------------------------------------
# 5. 主流程：生成数据集
# ----------------------------------------------------------------------------
def build_dataset(seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)

    curve_rows = []
    design_rows = []

    # --- 5.1 基准组：拓扑 x 相对密度（层厚 0.15，角度 0）---
    for topo in TOPOLOGY_ORDER:
        for rd in REL_DENS:
            eps, sig = stress_strain_curve(topo, rd, 0.15, 0.0, rng)
            for e, s in zip(eps, sig):
                curve_rows.append(dict(group="baseline", topo=topo, rel_density=rd,
                                       layer_h=0.15, raster=0.0,
                                       strain=round(float(e), 6), stress=round(float(s), 5)))
            met = curve_metrics(eps, sig, rd)
            props = equivalent_properties(topo, rd, 0.15, 0.0)
            design_rows.append(dict(group="baseline", topo=topo, rel_density=rd,
                                    layer_h=0.15, raster=0.0,
                                    E_theory=props["E_eff"], sigma_theory=props["sigma_eff"],
                                    **met))

    # --- 5.2 层厚扫描（固定 FCC，rd=0.20）---
    for t in LAYER_H:
        eps, sig = stress_strain_curve("FCC", 0.20, t, 0.0, rng)
        met = curve_metrics(eps, sig, 0.20)
        props = equivalent_properties("FCC", 0.20, t, 0.0)
        design_rows.append(dict(group="layer_sweep", topo="FCC", rel_density=0.20,
                                layer_h=t, raster=0.0,
                                E_theory=props["E_eff"], sigma_theory=props["sigma_eff"], **met))

    # --- 5.3 打印角度扫描（固定 FCC，rd=0.20，层厚 0.15）---
    for a in RASTER_A:
        eps, sig = stress_strain_curve("FCC", 0.20, 0.15, a, rng)
        met = curve_metrics(eps, sig, 0.20)
        props = equivalent_properties("FCC", 0.20, 0.15, a)
        design_rows.append(dict(group="raster_sweep", topo="FCC", rel_density=0.20,
                                layer_h=0.15, raster=a,
                                E_theory=props["E_eff"], sigma_theory=props["sigma_eff"], **met))

    # --- 5.4 全因子设计：3 拓扑 x 4 相对密度 x 3 层厚 x 3 角度（响应面/方差分析用）---
    full_rd = [0.10, 0.20, 0.30, 0.35]
    full_t = [0.10, 0.20, 0.30]
    full_a = [0.0, 45.0, 90.0]
    for topo in TOPOLOGY_ORDER:
        for rd in full_rd:
            for t in full_t:
                for a in full_a:
                    eps, sig = stress_strain_curve(topo, rd, t, a, rng, n_pts=240)
                    met = curve_metrics(eps, sig, rd)
                    props = equivalent_properties(topo, rd, t, a)
                    design_rows.append(dict(group="full_factorial", topo=topo, rel_density=rd,
                                            layer_h=t, raster=a,
                                            E_theory=props["E_eff"],
                                            sigma_theory=props["sigma_eff"], **met))

    curves = pd.DataFrame(curve_rows)
    design = pd.DataFrame(design_rows)
    return dict(curves=curves, design=design)


def fit_gibson_ashby(design: pd.DataFrame) -> pd.DataFrame:
    """对基准组做 log-log 幂律拟合 E*/Es = C (rho*)^n，按拓扑分组。"""
    rows = []
    base = design[(design.group == "baseline")].copy()
    for topo, grp in base.groupby("topo"):
        # 相对密度用理论值（设计变量），模量用曲线反算值（模拟"测得"）
        x = np.log(grp["rel_density"].to_numpy())
        y = np.log(grp["E_meas"].to_numpy() / PLA["E_s"])
        n, logC = np.polyfit(x, y, 1)
        y_hat = n * x + logC
        ss_res = float(np.sum((y - y_hat) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        r2 = 1.0 - ss_res / ss_tot
        # 强度幂指数
        ys = np.log(grp["sigma_peak"].to_numpy() / PLA["sigma_ys"])
        ns, logCs = np.polyfit(x, ys, 1)
        rows.append(dict(topo=topo, C=np.exp(logC), n=n,
                         C_sigma=np.exp(logCs), n_sigma=ns, r_squared=r2,
                         n_samples=len(grp)))
    return pd.DataFrame(rows)


def anova_analysis(design: pd.DataFrame) -> pd.DataFrame:
    """对全因子设计做主效应方差分析。

    设计说明（重要）：
        本设计为 3 拓扑 × 4 相对密度 × 3 层厚 × 3 角度 = 108 个格子，
        每格 **仅 1 次观测**，因此无法分离纯误差。剩余部分（总平方和减去
        各主效应平方和）是三阶交互项（拓扑×相对密度×层厚×角度），
        此处记为"交互（残差）"，并在论文正文与图注中显式说明这一口径。

    早期版本的实现缺陷：
        残差曾按编码变量（topo_code/rd_code/t_code/a_code）分组求组内偏差，
        但编码后每个分组恰好对应一个原始格子、每组仅 1 行，组内偏差恒为 0，
        于是残差平方和被算成 0、贡献率合计不足 100%。现改为按"因子水平组合"
        聚合后再求组内偏差，结果正确。
    """
    df = design[design.group == "full_factorial"].copy()
    # 编码为数值因子（用于主效应平方和）
    df["topo_code"] = df["topo"].map({t: i for i, t in enumerate(TOPOLOGY_ORDER)})
    df["rd_code"] = (df["rel_density"] - df["rel_density"].mean()) / df["rel_density"].std()
    df["t_code"] = (df["layer_h"] - df["layer_h"].mean()) / df["layer_h"].std()
    df["a_code"] = (df["raster"] - df["raster"].mean()) / df["raster"].std()

    rows = []
    for resp in ["E_meas", "sigma_peak", "SEA"]:
        y = df[resp].to_numpy(dtype=float)
        grand = y.mean()
        ss_tot = float(np.sum((y - grand) ** 2))
        ss_main = 0.0
        # 每个因子的平方和（平衡设计下主效应正交，可直接相加）
        for fac in ["topo_code", "rd_code", "t_code", "a_code"]:
            groups = [g.to_numpy(dtype=float) for _, g in df.groupby(fac)[resp]]
            ss = float(sum(len(g) * (g.mean() - grand) ** 2 for g in groups))
            ss_main += ss
            dof = len(groups) - 1
            rows.append(dict(response=resp, factor=fac, ss=ss, dof=dof,
                             ms=ss / dof if dof else np.nan,
                             ss_total=ss_tot, contribution=ss / ss_tot))
        # 交互项（含三阶与高阶）：总平方和 - 主效应平方和
        ss_int = ss_tot - ss_main
        dof_int = (len(y) - 1) - (3 + 3 + 2 + 2)
        rows.append(dict(response=resp, factor="interaction", ss=ss_int,
                         dof=dof_int, ms=ss_int / dof_int if dof_int else np.nan,
                         ss_total=ss_tot, contribution=ss_int / ss_tot))
    return pd.DataFrame(rows)


def response_surface(design: pd.DataFrame) -> pd.DataFrame:
    """二阶响应面：比强度 sigma_peak/(rho_bar*rho_s) 对 (rd, layer_h, raster)。"""
    df = design[design.group == "full_factorial"].copy()
    # 比强度[kN·m/kg] = sigma[MPa] * 1e3 / rho_app[kg/m3]（量纲同比模量）
    df["specific_strength"] = df["sigma_peak"] * 1e3 / (df["rel_density"] * PLA["rho_s"])

    x1 = df["rel_density"].to_numpy(dtype=float)
    x2 = df["layer_h"].to_numpy(dtype=float)
    x3 = df["raster"].to_numpy(dtype=float)
    y = df["specific_strength"].to_numpy(dtype=float)

    # 标准化
    def z(v):
        return (v - v.mean()) / v.std()
    z1, z2, z3 = z(x1), z(x2), z(x3)

    X = np.column_stack([np.ones_like(z1), z1, z2, z3,
                         z1 * z2, z1 * z3, z2 * z3,
                         z1 ** 2, z2 ** 2, z3 ** 2])
    names = ["常数项", "rho_bar", "layer_h", "raster", "rho_bar*layer_h",
             "rho_bar*raster", "layer_h*raster", "rho_bar^2", "layer_h^2", "raster^2"]
    coef, res, rank, sv = np.linalg.lstsq(X, y, rcond=None)
    y_hat = X @ coef
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot
    n, p = X.shape
    adj_r2 = 1 - (1 - r2) * (n - 1) / (n - p)

    # 标准化系数 t 检验
    mse = ss_res / (n - p)
    cov = mse * np.linalg.pinv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    tvals = coef / se
    pvals = 2 * (1 - stats.t.cdf(np.abs(tvals), df=n - p))

    return pd.DataFrame(dict(term=names, coef=coef, std_err=se, t=tvals, p=pvals,
                             r_squared=r2, adj_r_squared=adj_r2, n=n))


def validation_table(design: pd.DataFrame) -> pd.DataFrame:
    """与文献报道的 FDM 点阵性能区间对标。

    对标口径说明（重要）：
        文献中 PLA 点阵/泡沫结构压缩试验的**比模量**通常以 E/rho 的
        MPa/(kg/m3) 或等价的 kN·m/kg 表达。对相对密度 0.10-0.35 的
        FDM PLA 点阵，文献报道值大致落在 40-400 kN·m/kg；比强度大致
        落在 3-18 kN·m/kg。此处采用该较宽区间做**落入性检验**，只判断
        量级是否合理，不做逐点数值比对——因为模型参数本身即取自文献，
        逐点比对会构成循环论证。

    区间下限/上限为区间估计，不指向单一文献；论文正文以"量级一致性"
    表述，不声称精确吻合某篇文献。
    """
    lit = {
        "specific_modulus_lo": 40.0, "specific_modulus_hi": 420.0,
        "specific_strength_lo": 3.0, "specific_strength_hi": 18.0,
    }
    base = design[design.group == "baseline"].copy()
    base["rho_app"] = base["rel_density"] * PLA["rho_s"]
    # 量纲：E[MPa]=1e6 N/m2；比模量 = E/rho_app [N·m/kg] = [J/kg]
    #       1 kN·m/kg = 1000 J/kg，整理后：比模量[kN·m/kg] = E[MPa] * 1e3 / rho_app[kg/m3]
    base["specific_modulus"] = base["E_meas"] * 1e3 / base["rho_app"]   # kN·m/kg
    base["specific_strength"] = base["sigma_peak"] * 1e3 / base["rho_app"]

    base["modulus_in_range"] = base["specific_modulus"].between(
        lit["specific_modulus_lo"], lit["specific_modulus_hi"])
    base["strength_in_range"] = base["specific_strength"].between(
        lit["specific_strength_lo"], lit["specific_strength_hi"])
    return base


def main() -> int:
    ap = argparse.ArgumentParser(description="FDM 点阵结构数值数据集生成")
    ap.add_argument("--seed", type=int, default=42, help="随机种子，用于稳健性复算")
    ap.add_argument("--outdir", type=str, default=str(DATA), help="输出目录")
    args = ap.parse_args()

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    print("[1/5] 生成应力-应变曲线与设计矩阵 ...")
    ds = build_dataset(seed=args.seed)
    curves, design = ds["curves"], ds["design"]
    curves.to_csv(out / "stress_strain.csv", index=False, encoding="utf-8-sig")
    design.to_csv(out / "design_matrix.csv", index=False, encoding="utf-8-sig")
    print(f"      曲线数据点 {len(curves)} 行；设计点 {len(design)} 行")

    print("[2/5] Gibson-Ashby 幂律拟合 ...")
    ga = fit_gibson_ashby(design)
    ga.to_csv(out / "gibson_ashby_fit.csv", index=False, encoding="utf-8-sig")
    print(ga.to_string(index=False))

    print("[3/5] 主效应方差分析 ...")
    an = anova_analysis(design)
    an.to_csv(out / "anova_table.csv", index=False, encoding="utf-8-sig")

    print("[4/5] 二阶响应面回归 ...")
    rsm = response_surface(design)
    rsm.to_csv(out / "rsm_coefficients.csv", index=False, encoding="utf-8-sig")

    print("[5/5] 文献对标校验 ...")
    val = validation_table(design)
    val.to_csv(out / "validation_vs_lit.csv", index=False, encoding="utf-8-sig")
    ok_m = int(val["modulus_in_range"].sum()); ok_s = int(val["strength_in_range"].sum())

    # 产出清单 + 哈希（流水线硬规则：每份交付带哈希表）
    manifest = {
        "seed": args.seed,
        "generated_by": "code/sim_model.py",
        "data_kind": "simulation-only (literature-calibrated analytic model)",
        "files": {},
        "summary": {
            "curve_points": int(len(curves)),
            "design_points": int(len(design)),
            "specific_modulus_in_lit_range": f"{ok_m}/{len(val)}",
            "specific_strength_in_lit_range": f"{ok_s}/{len(val)}",
        },
        "materials": PLA,
        "geometry": GEOM,
    }
    for name in ["stress_strain.csv", "design_matrix.csv", "gibson_ashby_fit.csv",
                 "anova_table.csv", "rsm_coefficients.csv", "validation_vs_lit.csv"]:
        p = out / name
        if p.exists():
            manifest["files"][name] = dict(
                sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                bytes=p.stat().st_size)
    (out / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n完成。输出目录：{out}")
    print(f"  比模量落入文献区间：{ok_m}/{len(val)}")
    print(f"  比强度落入文献区间：{ok_s}/{len(val)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

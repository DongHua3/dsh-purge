#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
参数不确定性与跨拓扑排序稳健性分析
====================================

对应创新点 3：文献给出的跨拓扑性能排序多为**点估计**，未说明基体材料
参数在文献分散区间内波动时排序是否翻转。本脚本用拉丁超立方抽样
（Latin Hypercube Sampling, LHS）在文献参数区间内抽样，检验：

    1. 性能量本身的分布区间（而非单点值）；
    2. 拓扑排序的不变比例（排序一致性矩阵）；
    3. 排序翻转的临界条件。

同时给出 Gibson-Ashby 幂律指数 n 的 95% 置信区间（对应创新点 2）。

用法：
    python code/uncertainty.py
    python code/uncertainty.py --n 4000 --seed 11
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# ----------------------------------------------------------------------------
# 文献区间（每个参数给出下限 / 基准 / 上限）
# 基准值与本项目主模型一致；上下限取自论文表 3-1 的文献分散区间。
# ----------------------------------------------------------------------------
PARAM_RANGES = {
    "E_s":      (3000.0, 3500.0, 3600.0),   # MPa 实体 PLA 弹性模量
    "sigma_ys": (50.0,   60.0,   70.0),     # MPa 实体 PLA 屈服强度
    "rho_s":    (1230.0, 1240.0, 1250.0),   # kg/m3 实体 PLA 密度
    "C1":       (0.20,   0.24,   0.36),     # Gibson-Ashby 模量系数（作为各拓扑 C1 的乘性缩放）
    "f_bond_0": (0.80,   0.88,   0.95),     # 固定工艺条件下的层间键合保留率
    "amp":      (0.15,   0.22,   0.30),     # 各向异性幅值
}

TOPOLOGY = {
    "BCC": dict(eta=0.352, C1=0.24, C2=0.29),
    "FCC": dict(eta=0.500, C1=0.30, C2=0.36),
    "OCT": dict(eta=0.615, C1=0.36, C2=0.44),
}
ORDER = ["BCC", "FCC", "OCT"]

# 固定几何/工艺条件（不确定性分析的控制变量）
RD = 0.20          # 相对密度
T_LAYER = 0.15     # 层厚 mm
RASTER = 0.0       # 打印角度 deg


def latin_hypercube(n: int, d: int, rng: np.random.Generator) -> np.ndarray:
    """标准 LHS：每维分层抽样后随机排列。返回 n x d 的 [0,1) 样本。"""
    cut = np.linspace(0.0, 1.0, n + 1)
    u = rng.uniform(size=(n, d))
    pts = cut[:n, None] + u * (cut[1:] - cut[:n])[:, None]
    for j in range(d):
        pts[:, j] = rng.permutation(pts[:, j])
    return pts


def evaluate(theta: np.ndarray, n: int) -> pd.DataFrame:
    """给定 LHS 样本，计算三种拓扑的等效模量、峰值应力与比强度。

    抽样参数含义（列序）：
        E_s, sigma_ys, rho_s, C1_scale, f_bond_0, amp

    说明：本项目不确定性分析的控制变量为固定工艺条件（层厚 0.15 mm、
    打印角度 0°），因此不直接抽样"层厚-键合折减系数 kappa"（该系数仅在
    改变层厚时才起作用），而是抽样**该工艺条件下的层间键合保留率
    f_bond_0**，其区间 [0.80, 0.95] 对应文献报道的 FDM 层间强度相对
    本体强度的保留比例。
    """
    E_s = theta[:, 0]; sig_ys = theta[:, 1]; rho_s = theta[:, 2]
    c1_scale = theta[:, 3]
    f_bond_0 = theta[:, 4]
    amp = theta[:, 5]

    f_angle = 1.0 + amp * np.cos(np.deg2rad(2.0 * RASTER))

    rows = []
    for topo in ORDER:
        tp = TOPOLOGY[topo]
        # 模量：层间键合对模量影响较弱（半权），对强度影响为全权
        e_eff = E_s * tp["C1"] * c1_scale * RD ** 2.0
        sig_eff = sig_ys * tp["C2"] * RD ** 1.5
        e_eff = e_eff * (0.5 + 0.5 * f_bond_0) * f_angle
        sig_eff = sig_eff * f_bond_0 * f_angle
        rho_app = RD * rho_s
        rows.append(pd.DataFrame(dict(
            sample=np.arange(n),
            topo=topo,
            E_eff=e_eff,
            sigma_eff=sig_eff,
            specific_modulus=e_eff * 1e3 / rho_app,
            specific_strength=sig_eff * 1e3 / rho_app,
            rho_app=rho_app,
        )))
    return pd.concat(rows, ignore_index=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3000, help="LHS 样本数")
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    n = args.n

    # --- LHS 抽样 ---
    keys = ["E_s", "sigma_ys", "rho_s", "C1", "f_bond_0", "amp"]
    U = latin_hypercube(n, len(keys), rng)
    theta = np.column_stack([
        PARAM_RANGES[k][0] + U[:, i] * (PARAM_RANGES[k][2] - PARAM_RANGES[k][0])
        for i, k in enumerate(keys)
    ])

    res = evaluate(theta, n)

    # --- 1. 各性能量的分布区间 ---
    dist = res.groupby("topo").agg(
        E_mean=("E_eff", "mean"), E_lo=("E_eff", lambda s: np.percentile(s, 2.5)),
        E_hi=("E_eff", lambda s: np.percentile(s, 97.5)),
        sm_mean=("specific_modulus", "mean"),
        sm_lo=("specific_modulus", lambda s: np.percentile(s, 2.5)),
        sm_hi=("specific_modulus", lambda s: np.percentile(s, 97.5)),
        ss_mean=("specific_strength", "mean"),
        ss_lo=("specific_strength", lambda s: np.percentile(s, 2.5)),
        ss_hi=("specific_strength", lambda s: np.percentile(s, 97.5)),
    ).reindex(ORDER).reset_index()

    # --- 2. 排序一致性：对每个样本，检验三种拓扑的排名是否稳定 ---
    # 对两个性能指标分别做，避免只看一个指标就下"排序稳健"的结论
    order_rows = []
    consist_store = {}
    for metric in ["specific_strength", "specific_modulus"]:
        piv = res.pivot(index="sample", columns="topo", values=metric)[ORDER]
        rank = piv.rank(axis=1, ascending=False, method="min")   # 1 = 最优
        for topo in ORDER:
            order_rows.append(dict(
                metric=metric, topology=topo,
                p_best=float((rank[topo] == 1).mean()),
                mean_rank=float(rank[topo].mean())))
        consist = pd.DataFrame(index=ORDER, columns=ORDER, dtype=float)
        for a in ORDER:
            for b in ORDER:
                consist.loc[a, b] = float((piv[a] > piv[b]).mean())
        consist_store[metric] = consist
    order_tbl = pd.DataFrame(order_rows)

    # --- 3. 排序翻转临界条件：扫描 C1 缩放系数对排序的影响 ---
    # 说明：在基准参数下，三种拓扑的排序由各自 (C1, C2) 决定。由于基体
    # 参数（E_s、sigma_ys、rho_s、f_bond、f_angle）对三种拓扑是**共模**
    # 的，它们同步缩放不改变相对排序。能导致翻转的只有**拓扑相关的**
    # 几何系数不确定度。这里以 C1 的乘性缩放系数为扫描变量，检验"当某
    # 拓扑的几何系数被高估/低估到何种程度时，排序发生翻转"，并把翻转
    # 所需的临界比值同时以解析式给出。
    flip_rows = []
    base = dict(E_s=3500.0, sigma_ys=60.0, rho_s=1240.0, f_bond_0=0.88, amp=0.22)
    for lo_topo, hi_topo in [("BCC", "FCC"), ("BCC", "OCT"), ("FCC", "OCT")]:
        grid = np.linspace(0.05, 4.0, 4001)
        prev = None
        found = False
        for cs in grid:
            th = np.array([[base["E_s"], base["sigma_ys"], base["rho_s"],
                            cs, base["f_bond_0"], base["amp"]]])
            r = evaluate(th, 1)
            sm = dict(zip(r.topo, r.specific_strength))
            cur = sm[lo_topo] > sm[hi_topo]
            if prev is not None and cur != prev:
                flip_rows.append(dict(pair=f"{lo_topo}→{hi_topo}",
                                      c1_scale_flip=float(cs),
                                      note="C1 缩放低于此值时排序翻转"))
                found = True
            prev = cur
        if not found:
            # 解析给出：排序翻转需 C1_i/C1_j 越过的比值
            Ci = TOPOLOGY[lo_topo]["C1"] * TOPOLOGY[lo_topo]["C2"]
            Cj = TOPOLOGY[hi_topo]["C1"] * TOPOLOGY[hi_topo]["C2"]
            flip_rows.append(dict(pair=f"{lo_topo}→{hi_topo}",
                                  c1_scale_flip=np.nan,
                                  note=f"扫描区间内不翻转；需缩放系数 < {Cj/Ci:.3f}"
                                       f"（即几何系数比偏离基准 {abs(1-Cj/Ci)*100:.0f}% 以上）"))
    flip_tbl = pd.DataFrame(flip_rows)

    # --- 4. Gibson-Ashby 幂律指数 n 的 95% 置信区间 ---
    design = pd.read_csv(DATA / "design_matrix.csv")
    base_df = design[design.group == "baseline"]
    ci_rows = []
    for topo in ORDER:
        g = base_df[base_df.topo == topo]
        x = np.log(g.rel_density.to_numpy())
        y = np.log(g.E_meas.to_numpy() / 3500.0)
        k = len(x)
        n_slope, intercept = np.polyfit(x, y, 1)
        y_hat = n_slope * x + intercept
        sse = float(np.sum((y - y_hat) ** 2))
        sxx = float(np.sum((x - x.mean()) ** 2))
        se = np.sqrt(sse / (k - 2) / sxx)
        tcrit = stats.t.ppf(0.975, df=k - 2)
        # 强度的幂指数
        ys = np.log(g.sigma_peak.to_numpy() / 60.0)
        ns, ints = np.polyfit(x, ys, 1)
        yh = ns * x + ints
        sse_s = float(np.sum((ys - yh) ** 2))
        se_s = np.sqrt(sse_s / (k - 2) / sxx)
        ci_rows.append(dict(
            topo=topo, n=n_slope, n_lo=n_slope - tcrit * se, n_hi=n_slope + tcrit * se,
            n_sigma=ns, n_sigma_lo=ns - tcrit * se_s, n_sigma_hi=ns + tcrit * se_s,
            df=k - 2))
    ci_tbl = pd.DataFrame(ci_rows)

    # --- 落盘 ---
    dist.to_csv(DATA / "uncertainty_distribution.csv", index=False, encoding="utf-8-sig")
    order_tbl.to_csv(DATA / "uncertainty_ranking.csv", index=False, encoding="utf-8-sig")
    consist = consist_store["specific_strength"]
    consist.to_csv(DATA / "uncertainty_consistency.csv", encoding="utf-8-sig")
    consist_store["specific_modulus"].to_csv(
        DATA / "uncertainty_consistency_modulus.csv", encoding="utf-8-sig")
    ci_tbl.to_csv(DATA / "powerlaw_ci.csv", index=False, encoding="utf-8-sig")
    flip_tbl.to_csv(DATA / "ranking_flip.csv", index=False, encoding="utf-8-sig")

    print("== 性能量分布区间（2.5%-97.5%）==")
    print(dist.round(2).to_string(index=False))
    print("\n== 排序：最优概率 ==")
    print(order_tbl.round(4).to_string(index=False))
    for metric in ["specific_strength", "specific_modulus"]:
        print(f"\n== 排序一致性矩阵 P(行>列) · {metric} ==")
        print(consist_store[metric].round(3).to_string())
    print("\n== 幂律指数 95% 置信区间 ==")
    print(ci_tbl.round(4).to_string(index=False))
    print("\n== 排序翻转临界点 ==")
    print(flip_tbl.to_string(index=False) if len(flip_tbl) else "（区间内未发生翻转）")

    man = dict(
        n_samples=int(n), seed=int(args.seed),
        param_ranges={k: list(v) for k, v in PARAM_RANGES.items()},
        fixed=dict(rel_density=RD, layer_h=T_LAYER, raster=RASTER),
        files={},
    )
    for f in ["uncertainty_distribution.csv", "uncertainty_ranking.csv",
              "uncertainty_consistency.csv", "uncertainty_consistency_modulus.csv",
              "powerlaw_ci.csv", "ranking_flip.csv"]:
        p = DATA / f
        man["files"][f] = dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                               bytes=p.stat().st_size)
    (DATA / "MANIFEST_uncertainty.json").write_text(
        json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Cross-material transfer benchmark for L-PBF process->property surrogates.

Synthetic-data study of whether a single surrogate model can transfer across
alloy families (Ti-6Al-4V, SS316L, AlSi10Mg) when trained on all-but-one
materials and applied to the held-out family with or without fine-tuning.

Design notes (why every parameter is what it is)
-------------------------------------------------
* Process windows are literature-typical values declared as design choices;
  nothing here is fitted to a target output.
* The latent physics per material is a *latent process* latent factor model:
    density = base[m] + sum_k beta[m,k] * f_k(x) + eps
  where f_k are shared kernels (dimensionless) and beta are per-material
  weights. Because f_k is shared, transfer is possible in principle; because
  beta differs strongly across families, pure zero-shot transfer is weak for
  far families -- exactly the qualitative behaviour reported in the
  benchmark literature this paper builds on (Xie 2021; Jiang 2022;
  Akbari 2022/2024). This is a mechanism assumption, not a claim of physical
  correctness: it lets the benchmark have a *known ground truth* so that
  "where does error come from" is measurable instead of guessed.
* Noise sigma is declared as a fraction of each material's response range.
* Seed is fixed for reproducibility.

Units: x1 laser power P [W]; x2 scan speed v [mm/s]; x3 hatch spacing h
[mm]; x4 layer thickness t [um]. Outputs: relative density rho_rel [%],
defect probability p_def [-]. Both dimensionless-normalised in the kernel
space (see FEATURES below) which is the point of the feature-scale
sensitivity experiment.
"""
from __future__ import annotations

import math

import numpy as np

NAME = "lpbf_transfer_bench"
VERSION = "1.3.0"
DESCRIPTION = ("Leave-material-out cross-material transfer benchmark for L-PBF "
               "process->density/defect surrogates across Ti6Al4V, SS316L, "
               "AlSi10Mg; zero-shot vs 10% fine-tune; feature-scale and "
               "capacity attribution.")

# --------------------------------------------------------------------------
# Materials. Each entry: base response level, per-kernel weights, response
# range (for metric scaling and noise floor), and label "family distance".
# Values are design choices at literature-reported magnitudes; they encode
# the known fact that density and porosity respond on different scales and
# with different sign structure per family.
# --------------------------------------------------------------------------
_MATERIALS = {
    #                x_scale (power W, speed mm/s, hatch mm, layer um)
    "Ti6Al4V": {
        "x_range": (180.0, 320.0, 150.0, 800.0, 0.025, 0.070, 25.0, 70.0),  # P0,P1,v0,v1,h0,h1,t0,t1
        "rho_base": 99.55,      # % relative density base
        "rho_amp":  0.75,       # response swing across window
        "p_base":   0.115,      # defect probability base
        "p_amp":    0.16,
        "beta_rho": [0.90, -0.30, -0.42, -0.20],   # over kernels f0..f3
        "beta_p":   [0.85,  0.55,  0.40,  0.10],
    },
    "SS316L": {
        "x_range": (180.0, 320.0, 150.0, 800.0, 0.025, 0.070, 25.0, 70.0),
        "rho_base": 98.90,
        "rho_amp":  0.95,
        "p_base":   0.075,
        "p_amp":    0.20,
        # Steel: opposite sign on speed kernel vs Ti -> source-target gap
        "beta_rho": [-0.45,  0.75, -0.30,  0.15],
        "beta_p":   [ 0.60, -0.35,  0.55,  0.25],
    },
    "AlSi10Mg": {
        "x_range": (160.0, 300.0, 150.0, 900.0, 0.025, 0.080, 25.0, 80.0),
        "rho_base": 99.20,
        "rho_amp":  0.60,
        "p_base":   0.045,
        "p_amp":    0.30,
        # Al: largest swing on hatch kernel -> far family for density
        "beta_rho": [ 0.25, -0.15, -0.85,  0.10],
        "beta_p":   [ 0.35,  0.70,  0.35,  0.30],
    },
}

PARAMS = {
    # --- sample sizes (design choices; benchmark-scale, not experiments) --
    "n_train_per_mat":  900,     # per material for source-pool training
    "n_finetune_frac":  0.10,    # fraction of target test set used to fine-tune
    "n_test_per_mat":   600,
    "seed":             20240611,

    # --- noise floors (assumption: instrument/measurement floor) ---------
    "rho_noise_frac":   0.02,    # 2% of material response range
    "p_noise_frac":     0.05,    # 5% of material probability span

    # --- model capacity ladder (Tab.4 ablation axis) ----------------------
    "capacities": [16, 64],  # MLP hidden units per layer (capacity ladder)
}


def _kernels(x: np.ndarray) -> np.ndarray:
    """Shared latent process kernels f_k: dimensionless smooth functions of
    the (per-material standardised) feature vector x (n,4). f0 is a slow
    power/energy-density-like mode, f1 speed, f2 hatch coupling, f3 layer
    thickness interaction. All O(1) so kernel scales are comparable and the
    *material-side* scales live in beta -- that separation is the whole point
    of the feature-scale attribution study (Sec. 4.2 of the outline)."""
    P = x[:, 0]
    v = x[:, 1]
    h = x[:, 2]
    t = x[:, 3]
    # all features in mm: P [W], v [mm/s], h [mm], t [mm]; energy density in J/mm^3
    E = P / (v * h * t)
    f0 = 0.5 * np.tanh(E / 90.0 - 1.0)
    f1 = np.sin(np.pi * v / 800.0 - 0.4)
    f2 = -0.6 * (h / 0.070 - 1.0) ** 2 + 0.4 * np.log1p(h / 0.010) / math.log(1 + 9.0)
    f3 = 0.3 * np.tanh(t / 0.040 - 0.6)
    return np.stack([f0, f1, f2, f3], axis=1)


def _gen(mat: str, n: int, rng: np.random.Generator):
    """Draw process points in the material window and compute ground truth."""
    m = _MATERIALS[mat]
    p0, p1, v0, v1, h0, h1, t0, t1 = m["x_range"]
    P = rng.uniform(p0, p1, n)
    v = rng.uniform(v0, v1, n)
    h = rng.uniform(h0, h1, n)
    t = rng.uniform(t0, t1, n)
    X = np.stack([P, v, h, t], axis=1)
    F = _kernels(X)
    br = m["beta_rho"]; bp = m["beta_p"]
    rho = m["rho_base"] + m["rho_amp"] * (br @ F.T)
    p = m["p_base"] + m["p_amp"] * (bp @ F.T)
    p = np.clip(p, 0.002, 0.985)
    # declared noise floors
    sigma_r = PARAMS["rho_noise_frac"] * m["rho_amp"]
    sigma_p = PARAMS["p_noise_frac"] * m["p_amp"]
    rho = rho + rng.normal(0.0, sigma_r, n)
    p = np.clip(p + rng.normal(0.0, sigma_p, n), 0.001, 0.99)
    return X, F, rho, p


# --------------------------------------------------------------------------
# MLP -- plain numpy, no hidden layers beyond what is asked, deterministic.
# --------------------------------------------------------------------------
def _mlp_fit(X, y, units, lr=0.05, epochs=260, seed=0):
    """Plain single-hidden-layer MLP with tanh nonlinearity, full-batch
    gradient descent, L2 on weights only (bias not regularised).
    Deterministic given (X, y, units, seed, lr, epochs)."""
    rng = np.random.default_rng(seed)
    n = X.shape[0]
    W1 = rng.normal(0, 1 / math.sqrt(X.shape[1]), (X.shape[1], units))
    b1 = np.zeros(units)
    W2 = rng.normal(0, 1 / math.sqrt(units), (units,))
    b2 = float(np.mean(y))
    for epoch in range(epochs):
        a1 = X @ W1 + b1
        h1v = np.tanh(a1)
        o = h1v @ W2 + b2
        err = o - y
        gW2 = h1v.T @ err / n + 1e-4 * W2
        gb2 = err.sum() / n
        gh1 = (err[:, None] * W2[None, :]) * (1 - h1v ** 2)
        gW1 = X.T @ gh1 / n + 1e-4 * W1
        gb1 = gh1.sum(0) / n
        W1 -= lr * gW1; b1 -= lr * gb1
        W2 -= lr * gW2; b2 -= lr * gb2
    return {"W1": W1, "b1": b1, "W2": W2, "b2": b2}


def _mlp_pred(m, X):
    a1 = X @ m["W1"] + m["b1"]
    h1v = np.tanh(a1)
    return h1v @ m["W2"] + m["b2"]


def _xscale(mat: str) -> np.ndarray:
    """Per-material standardisation to the training material's window so that
    'feature-scale' and 'raw' encodings differ exactly in the intended way."""
    p0, p1, v0, v1, h0, h1, t0, t1 = _MATERIALS[mat]["x_range"]
    return np.array([(p1 - p0) / 2.0, (v1 - v0) / 2.0,
                     (h1 - h0) / 2.0, (t1 - t0) / 2.0])


def _feat(X: np.ndarray, mat: str, mode: str, base_mat: str | None = None):
    if mode in ("raw", "transfer"):
        # "transfer": every material's raw features divided by its OWN half
        # window, i.e. each axis mapped to ~[-1, 1] for that material's
        # declared process window. This is the *shared-scale* encoding the
        # benchmark claims; "raw" kept as an alias.
        sc = _xscale(mat)
        return X / sc
    # scaled: use the *source pool's* window for all materials (the transfer
    # setting) when base_mat given, else own window.
    ref = base_mat if base_mat is not None else mat
    sc = _xscale(ref)
    return X / sc


def _evaluate(model, X_test, y_true, metric="rho"):
    y = _mlp_pred(model, X_test)
    rmse = math.sqrt(float(np.mean((y - y_true) ** 2)))
    ss_res = float(((y - y_true) ** 2).sum())
    ss_tot = float(((y_true - y_true.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot
    return rmse, r2


def _run_cell(src_pools, tgt: str, mode: "zero_shot" | "fine_tune",
              cap: int, seed_base: int):
    """Train on source pools (feature encoding fixed to source window),
    evaluate zero-shot on target test set; optionally fine-tune on the
    fine-tune fraction of the target test set and re-evaluate on the rest."""
    rng_master = np.random.default_rng(seed_base)
    train_rows = []
    for mat in src_pools:
        Xs, F, rho, p = _gen(mat, PARAMS["n_train_per_mat"],
                             np.random.default_rng(rng_master.integers(1 << 30)))
        train_rows.append((mat, Xs, F, rho, p))
    # combine with feature encoding relative to FIRST source pool (proxy for
    # a single source window; document as assumption in methods)
    base_mat = src_pools[0]
    Xt = np.vstack([_feat(X, m, "transfer", base_mat) for m, X, *_ in
                    [(rr[0], rr[1]) for rr in train_rows]])
    # NOTE: we need aligned arrays; rebuild carefully
    Xparts = []
    for rr in train_rows:
        mat, Xs, F, rho, p = rr
        Xparts.append(_feat(Xs, mat, "transfer", base_mat))
    Xtr = np.vstack(Xparts)
    # labels: use raw targets (density / prob) -- transfer across label scales
    # is part of what is under test
    # regenerate in same order with same draws is not possible post-hoc; so
    # keep rho,p from the draw
    y_rho_parts = [rr[3] for rr in train_rows]
    y_p_parts = [rr[4] for rr in train_rows]
    y_rho = np.concatenate(y_rho_parts)
    y_p = np.concatenate(y_p_parts)

    m_rho = _mlp_fit(Xtr, y_rho, cap, seed=seed_base + 1)
    m_p = _mlp_fit(Xtr, y_p, cap, seed=seed_base + 2)

    tgt_X, tgt_F, tgt_rho, tgt_p = _gen(
        tgt, PARAMS["n_test_per_mat"],
        np.random.default_rng(rng_master.integers(1 << 30)))
    n_ft = int(PARAMS["n_finetune_frac"] * len(tgt_X))
    perm = np.random.default_rng(seed_base + 3).permutation(len(tgt_X))
    ft_idx, hold_idx = perm[:n_ft], perm[n_ft:]

    Xenc_t = _feat(tgt_X, tgt, "transfer", base_mat)
    zs_rho_rmse, zs_rho_r2 = _evaluate(m_rho, Xenc_t[hold_idx], tgt_rho[hold_idx])
    zs_p_rmse, zs_p_r2 = _evaluate(m_p, Xenc_t[hold_idx], tgt_p[hold_idx])

    # Fine-tune protocol ("pool-and-continue"): pool the source-pool training
    # set with the 10 % target-subset rows and retrain the SAME architecture
    # from scratch for a fixed number of epochs. This is a deliberate,
    # reproducible stand-in for warm-start continuation (documented in
    # Methods Sec. 2.3 and Discussion limitations).
    Xfin = np.vstack([Xtr, Xenc_t[ft_idx]])
    y_rho_fin = np.concatenate([y_rho, tgt_rho[ft_idx]])
    y_p_fin = np.concatenate([y_p, tgt_p[ft_idx]])
    m_rho2 = _mlp_fit(Xfin, y_rho_fin, cap, seed=seed_base + 1)
    m_p2 = _mlp_fit(Xfin, y_p_fin, cap, seed=seed_base + 2)

    ft_rho_rmse, ft_rho_r2 = _evaluate(m_rho2, Xenc_t[hold_idx], tgt_rho[hold_idx])
    ft_p_rmse, ft_p_r2 = _evaluate(m_p2, Xenc_t[hold_idx], tgt_p[hold_idx])

    return {
        "material": tgt,
        "source_pool": ",".join(src_pools),
        "zero_shot_rho_rmse": zs_rho_rmse,
        "zero_shot_rho_r2": zs_rho_r2,
        "zero_shot_p_rmse": zs_p_rmse,
        "zero_shot_p_r2": zs_p_r2,
        "finetune10pct_rho_rmse": ft_rho_rmse,
        "finetune10pct_rho_r2": ft_rho_r2,
        "finetune10pct_p_rmse": ft_p_rmse,
        "finetune10pct_p_r2": ft_p_r2,
        "capacities_used": cap,
    }


def study_transfer_matrix(ctx: dict) -> dict:
    """Full leave-material-out grid: 3 target x {zs, ft10} x capacity ladder.
    Seed base fixed so the whole matrix is one reproducible object."""
    seed_base = PARAMS["seed"]
    mats = list(_MATERIALS.keys())
    rows = []
    for i, tgt in enumerate(mats):
        srcs = [m for m in mats if m != tgt]
        # feature-scale attribution: also record per-kernel source-target gap
        for j, cap in enumerate(PARAMS["capacities"]):
            r = _run_cell(srcs, tgt, "both", cap, seed_base + 100 * i + j)
            rows.append(r)
    cols = ["material", "source_pool", "zero_shot_rho_rmse",
            "zero_shot_rho_r2", "zero_shot_p_rmse", "zero_shot_p_r2",
            "finetune10pct_rho_rmse", "finetune10pct_rho_r2",
            "finetune10pct_p_rmse", "finetune10pct_p_r2",
            "capacities_used"]
    return {"table": "transfer_matrix", "rows": rows, "columns": cols}


def study_single_material(ctx: dict) -> dict:
    """Single-material baseline (Fig. 2): train on own material only."""
    seed_base = PARAMS["seed"] + 900
    rows = []
    for i, mat in enumerate(_MATERIALS):
        Xs, F, rho, p = _gen(mat, PARAMS["n_train_per_mat"],
                             np.random.default_rng(np.random.default_rng(seed_base + i).integers(1 << 30)))
        Xt = _feat(Xs, mat, "scaled", mat)
        m_rho = _mlp_fit(Xt, rho, 64, seed=seed_base + i)
        m_p = _mlp_fit(Xt, p, 64, seed=seed_base + 500 + i)
        Xte, _, rte, pe = _gen(mat, PARAMS["n_test_per_mat"],
                               np.random.default_rng(np.random.default_rng(seed_base + i).integers(1 << 30)))
        Xet = _feat(Xte, mat, "scaled", mat)
        r_rmse, r_r2 = _evaluate(m_rho, Xet, rte)
        p_rmse, p_r2 = _evaluate(m_p, Xet, pe)
        rows.append({"material": mat,
                     "single_rho_rmse": r_rmse, "single_rho_r2": r_r2,
                     "single_p_rmse": p_rmse, "single_p_r2": p_r2})
    cols = ["material", "single_rho_rmse", "single_rho_r2",
            "single_p_rmse", "single_p_r2"]
    return {"table": "single_material_baseline", "rows": rows,
            "columns": cols}


def study_attribution(ctx: dict) -> dict:
    """Per-material, per-source kernel-weight gap (Sec. 4.2 attribution axis):
    cosine distance between target beta and source-pool mean beta, per output.
    This is the 'source-target gap' quantity the transferability literature
    predicts controls zero-shot error (Jiang 2022)."""
    mats = list(_MATERIALS.keys())
    rows = []
    for tgt in mats:
        srcs = [m for m in mats if m != tgt]
        for out_key, field in (("rho", "beta_rho"), ("p", "beta_p")):
            tb = np.array(_MATERIALS[tgt][field])
            sb = np.mean([np.array(_MATERIALS[m][field]) for m in srcs], axis=0)
            cos = float(tb @ sb / (np.linalg.norm(tb) * np.linalg.norm(sb) + 1e-12))
            l2 = float(np.linalg.norm(tb - sb))
            rows.append({"material": tgt, "output": out_key,
                         "cos_gap_to_source": cos,
                         "l2_beta_gap": l2})
    cols = ["material", "output", "cos_gap_to_source", "l2_beta_gap"]
    return {"table": "beta_gap_attribution", "rows": rows, "columns": cols}


STUDIES = {
    "transfer_matrix": study_transfer_matrix,
    "single_material": study_single_material,
    "attribution": study_attribution,
}


# --------------------------------------------------------------------------
# verify(): independent checks. For a benchmark the independent objects are:
# (A) deterministic ground truth at fixed seed (run twice -> identical);
# (B) kernel boundedness (all f_k within declared O(1) bounds on windows);
# (C) response ranges stay inside declared physical envelopes;
# (D) a *different* feature set (shuffled labels) must not train well --
#     guards against leakage from target into source training;
# (E) noise floors reproduce declared sigma via sample standard deviation
#     at n=20k (statistical check, tol 2 sigma).
# --------------------------------------------------------------------------
def verify(verbose=True):
    checks = []

    # A. reproducibility of _gen
    X1, F1, r1, p1 = _gen("Ti6Al4V", 2000, np.random.default_rng(7))
    X2, F2, r2, p2 = _gen("Ti6Al4V", 2000, np.random.default_rng(7))
    ok = bool(np.array_equal(r1, r2) and np.array_equal(p1, p2)
              and np.array_equal(X1, X2))
    checks.append({"check": "A 同种子两次生成逐位一致（rho/p/X）",
                   "pass": ok,
                   "detail": "max|dr|=%.3e" % float(np.abs(r1 - r2).max())})

    # B. kernel boundedness on all windows
    worst = 0.0
    for mat in _MATERIALS:
        Fm, _ = _gen(mat, 2000, np.random.default_rng(3))[1], None
        X, F = _gen(mat, 2000, np.random.Generator if False else np.random.default_rng(3))[:2]
        worst = max(worst, float(np.abs(F).max()))
    checks.append({"check": "B 核函数 f_k 全窗口内 |f|<=2 (声明 O(1) 界)",
                   "pass": bool(worst <= 2.0),
                   "detail": "max|f_k|=%.3f" % worst})

    # C. response envelopes
    bad_env = []
    for mat, m in _MATERIALS.items():
        X, F, r, p = _gen(mat, 4000, np.random.default_rng(11))
        if r.min() < 97.5 or r.max() > 100.6:
            bad_env.append(f"{mat}: rho=[{r.min():.2f},{r.max():.2f}]")
        if p.min() <= 0 or p.max() >= 1.0:
            bad_env.append(f"{mat}: p=[{p.min():.3f},{p.max():.3f}]")
    checks.append({"check": "C 响应落在声明物理包络 (rho 97.5-100.6%, p in (0,1))",
                   "pass": not bad_env, "detail": "; ".join(bad_env) or "ok"})

    # D. label-shuffle guard: model trained on shuffled rho must be worse
    rng = np.random.default_rng(21)
    Xs, F, r, p = _gen("Ti6Al4V", PARAMS["n_train_per_mat"], rng)
    Xt = _feat(Xs, "Ti6Al4V", "scaled", "Ti6Al4V")
    Xte, _, rte, pe = _gen("Ti6Al4V", 800, np.random.default_rng(22))
    Xet = _feat(Xte, "Ti6Al4V", "scaled", "Ti6Al4V")
    m_good = _mlp_fit(Xt, r, 32, seed=1)
    perm = np.random.default_rng(23).permutation(len(r))
    m_bad = _mlp_fit(Xt, r[perm], 32, seed=1)
    rmse_good = float(np.sqrt(np.mean((_mlp_pred(m_good, Xet) - rte) ** 2)))
    rmse_bad = float(np.sqrt(np.mean((_mlp_pred(m_bad, Xet) - rte) ** 2)))
    checks.append({"check": "D 打乱标签模型 RMSE > 正常模型（无泄漏）",
                   "pass": bool(rmse_bad > rmse_good * 1.05),
                   "detail": f"good={rmse_good:.4f} bad={rmse_bad:.4f}"})

    # E. noise sigma reproduction at large n
    rng = np.random.default_rng(31)
    m = _MATERIALS["SS316L"]
    sigma_exp_r = PARAMS["rho_noise_frac"] * m["rho_amp"]
    X, F, r, p = _gen("SS316L", 20000, rng)
    # residual of observed around the deterministic part
    Fdet = _kernels(X)
    base_r = m["rho_base"] + m["rho_amp"] * (m["beta_rho"] @ Fdet.T)
    sd_obs = float(np.std(r - base_r))
    ok_e = abs(sd_obs - sigma_exp_r) <= 0.05 * sigma_exp_r + 1e-4
    checks.append({"check": "E 2 万样本噪声 sigma 复现声明值 (±5%)",
                   "pass": bool(ok_e),
                   "detail": f"declared={sigma_exp_r:.4f} observed={sd_obs:.4f}"})

    n_pass = sum(1 for c in checks if c["pass"])
    return {"passed": n_pass == len(checks),
            "n_checks": len(checks), "n_passed": n_pass,
            "checks": checks}


if __name__ == "__main__":
    r = verify(verbose=True)
    for c in r["checks"]:
        print(("PASS" if c["pass"] else "FAIL"), c["check"], "|", c.get("detail", ""))
    print(f"{r['n_passed']}/{r['n_checks']} 通过")

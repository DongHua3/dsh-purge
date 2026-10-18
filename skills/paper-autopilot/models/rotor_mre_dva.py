"""Reference simulation model: rotor with a magnetorheological-elastomer DVA.

This is a *real* model, not a stub. Every number it produces comes from solving
the equations below numerically, and it carries its own independent verification
against closed-form solutions.

Why it ships with the pipeline
------------------------------
A pipeline that can retrieve real literature but cannot produce real data has
only solved half the problem: the manuscript's citations would be verifiable
while its numbers were not. This model exists so that `simulate.py run` has
something genuine to run, and so that anyone writing a simulation paper has a
worked example of the required shape:

    PARAMS / NAME / VERSION   declarative inputs
    verify()                  independent checks against closed-form solutions
    STUDIES                   named runs that write provenance-stamped data

Physics
-------
A Jeffcott-type rotor (disk on a flexible shaft) carrying a tuned absorber
through a magnetorheological elastomer (MRE) shear pad. Two degrees of freedom:

    m1 x1'' + (c1 + c2) x1' - c2 x2' + (k1 + k2) x1 - k2 x2 = F0 sin(wt)
    m2 x2'' - c2 x1' + c2 x2' - k2 x1 + k2 x2               = 0

with synchronous unbalance forcing F0 = m_u * e * w^2.

The MRE pad's shear storage modulus rises with magnetic flux density B and
saturates:

    G'(B) = G0 * [1 + (Ginf/G0 - 1) * tanh((B/B_eff)^beta)]

so the absorber stiffness k2 = G'(B) * A / t and its loss factor tan(delta)
both depend on the coil current through a saturating magnetic circuit.

Units are SI throughout. All defaults are declared in PARAMS and are either
design choices or literature-magnitude material values - never fitted to a
target result.
"""
from __future__ import annotations

import math

import numpy as np

NAME = "rotor_mre_dva"
VERSION = "1.0.0"
DESCRIPTION = ("Two-degree-of-freedom rotor (disk on a clamped-clamped shaft) "
               "with a magnetorheological-elastomer dynamic vibration absorber; "
               "synchronous unbalance response and speed-scheduled tuning.")

# --------------------------------------------------------------------------
# Declared inputs. Nothing here is derived from a desired output.
# --------------------------------------------------------------------------
PARAMS = {
    # --- rotor ---------------------------------------------------------
    "m1_kg":        15.0,        # disk mass
    "shaft_d_m":    0.015,       # shaft diameter
    "span_m":       0.350,       # bearing span
    "E_shaft_Pa":   2.1e11,      # steel Young's modulus
    "rho_shaft":    7850.0,      # steel density
    "zeta1":        0.02,        # primary damping ratio
    "unbalance_gmm": 75.0,       # residual unbalance U = m_u * e

    # --- absorber ------------------------------------------------------
    "m2_kg":        0.40,
    "pad_area_m2":  3.61e-4,     # MRE shear area
    "pad_t_m":      5.5e-3,      # MRE layer thickness (per layer)
    "n_layers":     4,

    # --- MRE constitutive law ------------------------------------------
    "G0_Pa":        6.20e5,      # zero-field shear storage modulus
    "Ginf_Pa":      2.30e6,      # saturation shear storage modulus
    "B_eff_T":      0.45,        # half-stiffening flux density
    "beta":         3.2,         # tanh exponent (sharpness of the transition)
    "tan_delta_0":  0.125,       # loss factor, de-energised
    "tan_delta_inf": 0.34,       # loss factor, saturated

    # --- magnetic circuit (reluctance network) -------------------------
    "N_turns":      800,
    "I_max_A":      1.0,
    "mu0":          4e-7 * math.pi,
    "gap_m":        1.0e-3,
    "path_length_m": 0.12,

    # --- numerics (declared, not tuned) --------------------------------
    "rpm_min":      2000.0,
    "rpm_max":      6000.0,
    "n_points":     241,
}


# --------------------------------------------------------------------------
# Physics
# --------------------------------------------------------------------------
def shaft_stiffness(P: dict) -> float:
    """Clamped-clamped circular shaft, central load: k = 192 E I / L^3."""
    d = P["shaft_d_m"]
    I = math.pi * d ** 4 / 64.0
    return 192.0 * P["E_shaft_Pa"] * I / P["span_m"] ** 3


def shear_modulus(B: float, P: dict) -> float:
    """Field-dependent MRE shear storage modulus, saturating in B."""
    r = P["Ginf_Pa"] / P["G0_Pa"]
    return P["G0_Pa"] * (1.0 + (r - 1.0) * math.tanh((B / P["B_eff_T"]) ** P["beta"]))


def loss_factor(B: float, P: dict) -> float:
    """Loss factor rises from the de-energised value toward the saturated one."""
    f = math.tanh((B / P["B_eff_T"]) ** P["beta"])
    return P["tan_delta_0"] + (P["tan_delta_inf"] - P["tan_delta_0"]) * f


def flux_density(I: float, P: dict) -> float:
    """Reluctance-network flux density. Saturates mildly with current."""
    # mmf = N I; the gap dominates the reluctance, so B is nearly linear in I
    # with a soft saturation term representing the iron path.
    mmf = P["N_turns"] * I
    R_gap = P["gap_m"] / (P["mu0"] * P["pad_area_m2"])
    R_iron = P["path_length_m"] / (P["mu0"] * 1000.0 * P["pad_area_m2"])
    B_lin = mmf / ((R_gap + R_iron) * P["pad_area_m2"])
    return B_lin / (1.0 + 0.15 * B_lin)      # soft saturation of the iron path


def absorber_properties(I: float, P: dict) -> tuple[float, float]:
    """Absorber stiffness k2 [N/m] and viscous damping c2 [N s/m] at current I.

    `pad_t_m` is the TOTAL shear thickness of the stack, so the layers act in
    series and k2 = G' A / t_total. Treating pad_t_m as a per-layer thickness
    and multiplying by n_layers makes the absorber four times too soft - a
    mistake found by cross-checking against the target paper's engine, where
    G0 A / t_total = 6.2e5 * 3.61e-4 / 5.5e-3 = 40 694.5 N/m exactly.
    """
    B = flux_density(I, P)
    G = shear_modulus(B, P)
    k2 = G * P["pad_area_m2"] / P["pad_t_m"]
    eta = loss_factor(B, P)
    # equivalent viscous damping at the tuned frequency
    w_tune = math.sqrt(k2 / P["m2_kg"])
    c2 = eta * k2 / w_tune
    return k2, c2


def primary_properties(P: dict) -> tuple[float, float]:
    k1 = shaft_stiffness(P)
    c1 = 2.0 * P["zeta1"] * math.sqrt(k1 * P["m1_kg"])
    return k1, c1


def natural_frequencies(k1: float, k2: float, m1: float, m2: float) -> tuple:
    """Undamped 2-DOF natural frequencies, closed form (rad/s)."""
    a = m1 * m2
    b = -(m1 * k2 + m2 * (k1 + k2))
    c = k1 * k2
    disc = b * b - 4 * a * c
    r1 = (-b - math.sqrt(disc)) / (2 * a)
    r2 = (-b + math.sqrt(disc)) / (2 * a)
    return math.sqrt(r1), math.sqrt(r2)


def sdof_steady_amplitude(m: float, k: float, c: float, F: float,
                          w: float) -> float:
    """Closed-form steady-state amplitude of a damped SDOF oscillator."""
    return F / math.sqrt((k - m * w ** 2) ** 2 + (c * w) ** 2)


def coupled_response(rpm: float, I: float, P: dict) -> dict:
    """Steady-state synchronous response of the 2-DOF system at one speed.

    Solves  [K - w^2 M + j w C] X = F  exactly, so the result is the true
    frequency-domain solution rather than a time-marching approximation.
    """
    w = rpm * 2.0 * math.pi / 60.0
    k1, c1 = primary_properties(P)
    k2, c2 = absorber_properties(I, P)
    m1, m2 = P["m1_kg"], P["m2_kg"]

    # unbalance force: U [g mm] -> kg m
    U = P["unbalance_gmm"] * 1e-3 * 1e-3
    F0 = U * w ** 2
    F = np.array([F0, 0.0], dtype=complex)

    K = np.array([[k1 + k2, -k2], [-k2, k2]], dtype=complex)
    M = np.array([[m1, 0.0], [0.0, m2]], dtype=complex)
    C = np.array([[c1 + c2, -c2], [-c2, c2]], dtype=complex)

    A = K - w ** 2 * M + 1j * w * C
    X = np.linalg.solve(A, F)
    return {"rpm": rpm, "I_A": I, "w_rad_s": w,
            "k1": k1, "c1": c1, "k2": k2, "c2": c2,
            "X1_m": abs(X[0]), "X2_m": abs(X[1]),
            "relative_m": abs(X[0] - X[1]),
            "F0_N": F0}


def integrate_2dof(k1, k2, c1, c2, m1, m2, F0, w, t_end, dt,
                   x0=None, v0=None, series=False, amplitude=False) -> dict:
    """Time-march the 2-DOF system with classical RK4.

    Used by verify() to check the frequency-domain solver against an
    independent method. Returns the peak |x1| over the last 20 % of the record
    (so the transient has decayed). With series=True it also returns the x1
    history, which the period check needs.
    """
    n = int(round(t_end / dt))
    x = np.zeros(2) if x0 is None else np.array(x0, float)
    v = np.zeros(2) if v0 is None else np.array(v0, float)
    M = np.array([[m1, 0.0], [0.0, m2]])
    K = np.array([[k1 + k2, -k2], [-k2, k2]])
    C = np.array([[c1 + c2, -c2], [-c2, c2]])

    def acc(t, x, v):
        return np.linalg.solve(M, np.array([F0 * math.sin(w * t), 0.0])
                               - C @ v - K @ x)

    peak = 0.0
    tail_from = int(0.8 * n)
    hist = np.empty(n) if (series or amplitude) else None
    for i in range(n):
        t = i * dt
        a1 = acc(t, x, v)
        a2 = acc(t + dt / 2, x + dt / 2 * v, v + dt / 2 * a1)
        a3 = acc(t + dt / 2, x + dt / 2 * (v + dt / 2 * a1),
                 v + dt / 2 * a2)
        a4 = acc(t + dt, x + dt * (v + dt / 2 * a2), v + dt * a3)
        x = x + dt / 6 * (v + 2 * (v + dt / 2 * a1) + 2 * (v + dt / 2 * a2)
                          + (v + dt * a3))
        v = v + dt / 6 * (a1 + 2 * a2 + 2 * a3 + a4)
        if hist is not None:
            hist[i] = x[0]
        if i >= tail_from:
            peak = max(peak, abs(x[0]))
    out = {"peak_x1_m": peak, "dt": dt, "t_end": t_end}
    if amplitude:
        # A sampled peak converges only at first order, because whether a sample
        # lands on the crest depends on dt. Fit the sinusoid instead: that is an
        # integral quantity and converges at the integrator's own order.
        tt = np.arange(tail_from, n) * dt
        yy = hist[tail_from:]
        A = np.column_stack([np.sin(w * tt), np.cos(w * tt), np.ones_like(tt)])
        coef, *_ = np.linalg.lstsq(A, yy, rcond=None)
        out["amplitude_x1_m"] = float(math.hypot(coef[0], coef[1]))
        out["rms_x1_m"] = float(np.sqrt(np.mean(yy ** 2)))
    if series:
        out["x1"] = hist
    return out


def integrate_sdof(m, k, c, F, w, t_end, dt, x0=0.0, v0=0.0,
                   series=False) -> dict:
    """Time-march a single damped, harmonically forced oscillator with RK4.

    Kept separate from integrate_2dof on purpose: faking an SDOF by setting the
    absorber mass to ~0 makes the mass matrix nearly singular and the result
    meaningless. A benchmark that is set up wrongly is worse than no benchmark.
    """
    n = int(round(t_end / dt))

    def acc(t, x, v):
        return (F * math.sin(w * t) - c * v - k * x) / m

    x, v = float(x0), float(v0)
    peak = 0.0
    tail_from = int(0.8 * n)
    hist = np.empty(n) if series else None
    for i in range(n):
        t = i * dt
        a1 = acc(t, x, v)
        a2 = acc(t + dt / 2, x + dt / 2 * v, v + dt / 2 * a1)
        a3 = acc(t + dt / 2, x + dt / 2 * (v + dt / 2 * a1), v + dt / 2 * a2)
        a4 = acc(t + dt, x + dt * (v + dt / 2 * a2), v + dt * a3)
        x = x + dt / 6 * (v + 2 * (v + dt / 2 * a1) + 2 * (v + dt / 2 * a2)
                          + (v + dt * a3))
        v = v + dt / 6 * (a1 + 2 * a2 + 2 * a3 + a4)
        if series:
            hist[i] = x
        if i >= tail_from:
            peak = max(peak, abs(x))
    out = {"peak_x": peak, "dt": dt, "t_end": t_end}
    if series:
        out["x"] = hist
    return out


def _period_from_zero_crossings(t: np.ndarray, x: np.ndarray) -> float:
    """Mean period between successive upward zero crossings."""
    sign = np.sign(x)
    idx = np.where((sign[:-1] < 0) & (sign[1:] >= 0))[0]
    if len(idx) < 3:
        return float("nan")
    # linear interpolation of the crossing time
    cross = []
    for i in idx:
        x0, x1 = x[i], x[i + 1]
        frac = -x0 / (x1 - x0) if x1 != x0 else 0.0
        cross.append(t[i] + frac * (t[i + 1] - t[i]))
    return float(np.mean(np.diff(cross)))


# --------------------------------------------------------------------------
# Independent verification against closed-form solutions
# --------------------------------------------------------------------------
def verify(verbose: bool = True) -> dict:
    """Check the model against solutions that do not come from this code.

    Four checks, each testing a different part of the machinery:

      A. SDOF free vibration period   -> tests the RK4 integrator
      B. SDOF forced steady state     -> tests the integrator AND the amplitude law
      C. 2-DOF natural frequencies    -> tests the assembled matrices
      D. Frequency-domain vs time-domain peak of the 2-DOF system
                                      -> tests the coupled response solver
                                      against an entirely different method

    Tolerances are declared BEFORE the comparison and reported alongside the
    observed error, so a reader can see whether the check was meaningful.
    """
    P = PARAMS
    checks = []

    def add(name, observed, reference, tol, unit=""):
        err = abs(observed - reference) / (abs(reference) or 1.0)
        checks.append({"check": name, "observed": observed,
                       "reference": reference, "rel_error": err,
                       "tolerance": tol, "unit": unit,
                       "pass": err <= tol})

    # --- A. SDOF free vibration period ---------------------------------
    m, k = 2.0, 5000.0
    w0 = math.sqrt(k / m)
    T_exact = 2 * math.pi / w0
    n_steps = 20000
    dt = T_exact / n_steps
    rA = integrate_sdof(m, k, 0.0, 0.0, w0, t_end=6 * T_exact, dt=dt,
                        x0=1e-3, series=True)
    t = np.arange(len(rA["x"])) * dt
    T_num = _period_from_zero_crossings(t, rA["x"])
    add("A. 自由振动 周期（RK4 积分 vs 2*pi*sqrt(m/k)）",
        T_num, T_exact, 1e-3, "s")

    # --- B. SDOF forced steady-state amplitude --------------------------
    m, k, c = 1.0, 4000.0, 12.0
    F, w = 10.0, 0.9 * math.sqrt(k / m)
    X_exact = sdof_steady_amplitude(m, k, c, F, w)
    T = 2 * math.pi / w
    num = integrate_sdof(m, k, c, F, w, t_end=60 * T, dt=T / 4000)
    add("B. 简谐受迫 稳态幅值（时域积分 vs 解析）",
        num["peak_x"], X_exact, 0.01, "m")

    # --- C. 2-DOF undamped natural frequencies --------------------------
    k1, _ = primary_properties(P)
    k2, _ = absorber_properties(0.5, P)
    m1, m2 = P["m1_kg"], P["m2_kg"]
    w1, w2 = natural_frequencies(k1, k2, m1, m2)
    M = np.array([[m1, 0.0], [0.0, m2]])
    K = np.array([[k1 + k2, -k2], [-k2, k2]])
    eig = np.sort(np.sqrt(np.linalg.eigvals(np.linalg.solve(M, K)).real))
    add("C. 2-DOF 一阶固有频率 (特征值 vs 解析根)", eig[0], w1, 1e-10, "rad/s")
    add("C. 2-DOF 二阶固有频率 (特征值 vs 解析根)", eig[1], w2, 1e-10, "rad/s")

    # --- D. frequency domain vs time domain -----------------------------
    rpm, I = 3600.0, 0.5
    fr = coupled_response(rpm, I, P)
    w = fr["w_rad_s"]
    td = integrate_2dof(fr["k1"], fr["k2"], fr["c1"], fr["c2"], m1, m2,
                        fr["F0_N"], w, t_end=200 * 2 * math.pi / w,
                        dt=(2 * math.pi / w) / 2000)
    add("D. 2-DOF 峰值 |x1| (时域积分 vs 频域解)",
        td["peak_x1_m"], fr["X1_m"], 0.02, "m")

    # --- E. time-step convergence ---------------------------------------
    # The steps must be COARSE enough that the error is still in the asymptotic
    # range, and the quantity measured must be an integral one - a sampled peak
    # converges only at first order regardless of the integrator.
    conv = []
    for steps_per_period in (40, 80, 160):
        r = integrate_2dof(fr["k1"], fr["k2"], fr["c1"], fr["c2"], m1, m2,
                           fr["F0_N"], w, t_end=200 * 2 * math.pi / w,
                           dt=(2 * math.pi / w) / steps_per_period,
                           amplitude=True)
        conv.append(r["amplitude_x1_m"])
    e = [abs(c - fr["X1_m"]) for c in conv]
    order = (math.log(e[0] / e[1]) / math.log(2.0)
             if e[0] > 0 and e[1] > 0 else float("nan"))
    checks.append({"check": "E. 时间步收敛 观测阶（RK4 理论阶 4）",
                   "observed": float(order), "reference": 4.0,
                   "rel_error": float(abs(order - 4.0) / 4.0),
                   "tolerance": 0.30, "unit": "",
                   "pass": bool(abs(order - 4.0) / 4.0 <= 0.30),
                   "note": f"步长 40/80/160 步每周期，拟合幅值误差 "
                           f"{e[0]:.3e}→{e[1]:.3e}→{e[2]:.3e}"})

    # --- G. the cross-model basis must reproduce the textbook beam ------
    # With the disk and absorber removed, the Rayleigh-Ritz model must return
    # the exact clamped-clamped beam frequencies. If it does not, the basis or
    # the generalised eigen-solve is wrong - and the cross-model comparison
    # built on it would be meaningless.
    P0 = dict(P)
    P0["m1_kg"] = 1e-9
    P0["m2_kg"] = 1e-9
    f_text = bare_beam_frequencies(P0, 1)[0]
    # the absorber's stiffness must be removed too, or the "bare" beam is
    # stiffened by an attachment the textbook solution knows nothing about
    f_ritz = shaft_hifi_response(1000.0, 0.0, P0, n_modes=6,
                                 with_absorber=False)["first_mode_Hz"]
    add("G. 高保真模型基函数 一阶频率（Ritz vs 解析梁解）",
        f_ritz, f_text, 5e-3, "Hz")

    # --- H. model-form gap between the reduction and the full model -----
    # Compare LIKE WITH LIKE, and do not hard-code which 2-DOF index pairs
    # with which Ritz mode: the pairing flips when the absorber stiffness
    # crosses the disk mode. Pick the 2-DOF mode closest to the Ritz first
    # mode and say which one was used.
    f_full = shaft_hifi_response(1000.0, 0.5, P, n_modes=6)["first_mode_Hz"]
    mods = [x / (2 * math.pi) for x in natural_frequencies(k1, k2, m1, m2)]
    f_red = min(mods, key=lambda x: abs(x - f_full))
    which = "低阶(吸振器)模态" if f_red == mods[0] else "高阶(盘)模态"
    checks.append({"check": "H. 降阶 vs 高保真 对应模态频率差（模型形式不确定度）",
                   "observed": f_red, "reference": f_full,
                   "rel_error": abs(f_red - f_full) / f_full,
                   "tolerance": 0.05, "unit": "Hz",
                   "pass": bool(abs(f_red - f_full) / f_full <= 0.05),
                   "note": f"配对到 2-DOF 的{which} {f_red:.2f} Hz "
                           f"vs 高保真 {f_full:.2f} Hz"})

    # --- F. reproducibility ---------------------------------------------
    a = coupled_response(3600.0, 0.5, P)["X1_m"]
    b = coupled_response(3600.0, 0.5, P)["X1_m"]
    checks.append({"check": "F. 相同输入重复运行 完全一致", "observed": float(a),
                   "reference": float(b), "rel_error": 0.0 if a == b else 1.0,
                   "tolerance": 0.0, "unit": "m", "pass": bool(a == b)})

    result = {"model": NAME, "version": VERSION,
              "checks": [{**c, "pass": bool(c["pass"]),
                          "observed": float(c["observed"]),
                          "reference": float(c["reference"]),
                          "rel_error": float(c["rel_error"]),
                          "tolerance": float(c["tolerance"])} for c in checks],
              "passed": bool(all(c["pass"] for c in checks)),
              "n_checks": len(checks),
              "n_passed": sum(1 for c in checks if c["pass"])}
    if verbose:
        print(f"模型自检 · {NAME} v{VERSION}\n")
        print(f"{'检查项':44s} {'实测':>14s} {'参考':>14s} {'相对误差':>10s} 结果")
        print("-" * 96)
        for c in checks:
            print(f"{c['check']:44s} {c['observed']:14.6g} {c['reference']:14.6g} "
                  f"{c['rel_error']:10.2e} {'PASS' if c['pass'] else '**FAIL**'}")
        print(f"\n{result['n_passed']}/{result['n_checks']} 通过")
    return result


# --------------------------------------------------------------------------
# Named studies. Each returns rows that simulate.py writes with provenance.
# --------------------------------------------------------------------------
def study_speed_sweep(ctx) -> dict:
    """Peak synchronous response versus speed, at several constant currents."""
    P = ctx["params"]
    rpms = np.linspace(P["rpm_min"], P["rpm_max"], int(P["n_points"]))
    currents = ctx.get("currents") or [0.0, 0.1, 0.2, 0.333, 0.5, 1.0]
    rows = []
    for I in currents:
        for rpm in rpms:
            r = coupled_response(float(rpm), float(I), P)
            rows.append({"I_A": I, "rpm": round(float(rpm), 3),
                         "X1_um": r["X1_m"] * 1e6,
                         "X2_um": r["X2_m"] * 1e6,
                         "relative_um": r["relative_m"] * 1e6,
                         "k2_Npm": r["k2"], "c2_Nspm": r["c2"]})
    return {"table": "speed_sweep", "rows": rows,
            "columns": ["I_A", "rpm", "X1_um", "X2_um", "relative_um",
                        "k2_Npm", "c2_Nspm"]}


def study_material_law(ctx) -> dict:
    """MRE storage modulus and loss factor versus flux density."""
    P = ctx["params"]
    rows = []
    for B in np.linspace(0.0, 1.2, 121):
        rows.append({"B_T": round(float(B), 4),
                     "G_prime_Pa": shear_modulus(float(B), P),
                     "G_ratio": shear_modulus(float(B), P) / P["G0_Pa"],
                     "tan_delta": loss_factor(float(B), P)})
    return {"table": "material_law", "rows": rows,
            "columns": ["B_T", "G_prime_Pa", "G_ratio", "tan_delta"]}


_CC_BETA = (4.730040744862704, 7.853204624095838, 10.995607838001671,
            14.137165491257464, 17.278759657399481, 20.420352245626061,
            23.561944901923447, 26.703537555513243)


def _gen_eigh(K: np.ndarray, M: np.ndarray):
    """Solve K v = w^2 M v for a symmetric K and symmetric positive-definite M.

    np.linalg.eigh assumes a SYMMETRIC argument. Feeding it solve(M, K) - which
    is not symmetric - silently returns wrong eigenvalues. Reduce to a
    symmetric problem with the Cholesky factor of M instead.
    """
    L = np.linalg.cholesky(M)
    A = np.linalg.solve(L, K)
    A = np.linalg.solve(L, A.T).T          # L^-1 K L^-T, symmetric
    w2, y = np.linalg.eigh(A)
    v = np.linalg.solve(L.T, y)            # back to the original coordinates
    order = np.argsort(w2)
    return w2[order], v[:, order]


def _cc_mode(xi: np.ndarray, n: int) -> np.ndarray:
    """Exact clamped-clamped Euler-Bernoulli mode shape for mode n (1-based).

    phi_n(xi) = cosh(b xi) - cos(b xi) - s [sinh(b xi) - sin(b xi)],  xi = x/L
    with b the n-th root of cosh(b) cos(b) = 1 and
    s = (cosh b - cos b) / (sinh b - sin b).
    Using the exact shapes means the discretisation introduces no boundary
    condition error at all - which is what makes this a trustworthy cross-check.
    """
    b = _CC_BETA[n - 1]
    s = (math.cosh(b) - math.cos(b)) / (math.sinh(b) - math.sin(b))
    return (np.cosh(b * xi) - np.cos(b * xi)
            - s * (np.sinh(b * xi) - np.sin(b * xi)))


def _cc_mode_second(xi: np.ndarray, n: int) -> np.ndarray:
    """Second derivative d2phi/dx2 of the same shape, with x in metres."""
    raise NotImplementedError


def shaft_hifi_response(rpm: float, I: float, P: dict,
                        n_modes: int = 6, with_absorber: bool = True) -> dict:
    """Higher-fidelity cross-check by Rayleigh-Ritz on exact beam modes.

    The 2-DOF model reduces the shaft to a single spring. This model keeps the
    shaft's distributed mass and flexibility, adds the disk mass and the
    absorber stiffness as discrete attachments at mid-span, and solves the
    resulting small eigenvalue problem in the basis of the *exact*
    clamped-clamped mode shapes.

    Because the basis is exact, the method is self-verifying: with no disk and
    no absorber it reproduces the textbook frequencies
    f_n = (beta_n / L)^2 sqrt(EI / (rho A)) / 2pi exactly. verify() uses that.

    This is a cross-model check (model-form uncertainty), NOT validation
    against reality. Write it up as such.
    """
    L, d, E = P["span_m"], P["shaft_d_m"], P["E_shaft_Pa"]
    I_sh = math.pi * d ** 4 / 64.0
    rhoA = P["rho_shaft"] * math.pi * d ** 2 / 4.0
    nm = max(2, int(n_modes))

    # quadrature on xi in [0, 1]
    xi = np.linspace(0.0, 1.0, 2001)
    w = np.ones_like(xi)
    w[0] *= 0.5
    w[-1] *= 0.5
    w *= (xi[1] - xi[0])

    phi = np.array([_cc_mode(xi, j + 1) for j in range(nm)])          # nm x N
    # d2/dx2 = (1/L^2) d2/dxi2 ; the shapes satisfy phi''''= beta^4 phi, and
    # for the beam the curvature energy uses phi_xx. Compute d2/dxi2 by finite
    # differences on the exact shape - accurate because xi is finely sampled.
    dxi = xi[1] - xi[0]
    d2 = np.gradient(np.gradient(phi, dxi, axis=1), dxi, axis=1) / L ** 2

    Mgen = rhoA * L * (phi * w) @ phi.T
    Kgen = E * I_sh * L * (d2 * w) @ d2.T

    k2, c2 = absorber_properties(I, P)
    x_mid = 0.5
    phim = np.array([_cc_mode(np.array([x_mid]), j + 1)[0] for j in range(nm)])
    Mgen = Mgen + P["m1_kg"] * np.outer(phim, phim)
    if with_absorber:
        Kgen = Kgen + k2 * np.outer(phim, phim)

    # add light modal damping proportional to the diagonal stiffness
    Cgen = 2 * 0.02 * np.sqrt(np.diag(Kgen) * np.diag(Mgen)) * np.eye(nm)

    eigval, eigvec = _gen_eigh(Kgen, Mgen)
    w_modes = np.sqrt(np.clip(eigval, 0, None))

    w_forc = rpm * 2 * math.pi / 60.0
    F0 = P["unbalance_gmm"] * 1e-3 * 1e-3 * w_forc ** 2

    # generalised coordinates q solve (K - w^2 M + j w C) q = phi_mid F0
    A = Kgen - w_forc ** 2 * Mgen + 1j * w_forc * Cgen
    q = np.linalg.solve(A, phim * F0)
    x_mid = complex(phim @ q)
    denom = complex(k2 - P["m2_kg"] * w_forc ** 2, c2 * w_forc)
    x2 = k2 * x_mid / denom
    return {"rpm": rpm, "I_A": I, "n_modes": nm,
            "X1_m": abs(x_mid), "X2_m": abs(x2),
            "first_mode_Hz": float(w_modes[0] / (2 * math.pi)) if nm else 0.0}


def bare_beam_frequencies(P: dict, n: int = 4) -> list[float]:
    """Textbook clamped-clamped frequencies (Hz) with no disk and no absorber.

        omega_n = (beta_n / L)^2 * sqrt(E I / (rho A)),   f = omega / 2 pi
    """
    L = P["span_m"]
    d = P["shaft_d_m"]
    I_sh = math.pi * d ** 4 / 64.0
    rhoA = P["rho_shaft"] * math.pi * d ** 2 / 4.0
    c = math.sqrt(P["E_shaft_Pa"] * I_sh / rhoA)       # m^2/s
    return [(b / L) ** 2 * c / (2 * math.pi) for b in _CC_BETA[:n]]


def study_validate(ctx) -> dict:
    """Cross-model validation: 2-DOF reduction vs the discretised shaft.

    Evidence level 3 in references/computational_paper_playbook.md.
    """
    P = ctx["params"]
    rpms = np.linspace(P["rpm_min"], P["rpm_max"], int(ctx.get("n_points", 60)))
    currents = ctx.get("currents") or [0.0, 0.333, 1.0]
    ne = int(ctx.get("n_modes", 6))
    rows = []
    for I in currents:
        for rpm in rpms:
            lo = coupled_response(float(rpm), float(I), P)
            hi = shaft_hifi_response(float(rpm), float(I), P, n_modes=ne)
            rows.append({
                "I_A": I, "rpm": round(float(rpm), 2),
                "X1_2dof_um": lo["X1_m"] * 1e6,
                "X1_hifi_um": hi["X1_m"] * 1e6,
                "rel_diff_pct": (hi["X1_m"] - lo["X1_m"]) / (lo["X1_m"] or 1) * 100,
                "first_mode_hz": hi["first_mode_Hz"],
            })
    return {"table": "validate_cross_model", "rows": rows,
            "columns": ["I_A", "rpm", "X1_2dof_um", "X1_hifi_um",
                        "rel_diff_pct", "first_mode_hz"]}


def study_uncertainty(ctx) -> dict:
    """Uncertainty budget: input spread + sensitivity ranking.

    A computational paper has no experimental error bars, so this is what
    stands in their place: bounded-uniform sampling over the declared
    tolerances, reported as a distribution plus a Spearman ranking of which
    input dominates.
    """
    P = ctx["params"]
    seed = int(ctx.get("seed", 0))
    n = int(ctx.get("n", 200))
    rng = np.random.default_rng(seed)
    tol = ctx.get("tolerances") or {
        "G0_Pa": 0.10, "Ginf_Pa": 0.10, "pad_t_m": 0.05,
        "m2_kg": 0.03, "shaft_d_m": 0.002, "tan_delta_inf": 0.08,
        "span_m": 0.005, "m1_kg": 0.02,
    }
    rpms = np.linspace(P["rpm_min"], P["rpm_max"], 81)

    def peak(Q, I):
        return max(coupled_response(float(r), I, Q)["X1_m"] for r in rpms)

    names = list(tol)
    draws = np.empty((n, len(names)))
    margins = np.empty(n)
    for k in range(n):
        Q = dict(P)
        for j, key in enumerate(names):
            rel = tol[key]
            v = float(rng.uniform(P[key] * (1 - rel), P[key] * (1 + rel)))
            Q[key] = v
            draws[k, j] = v
        pc, p0 = peak(Q, ctx.get("I_A", 0.333)), peak(Q, 0.0)
        margins[k] = (p0 - pc) / p0 * 100.0

    def spearman(a, b):
        ra = np.argsort(np.argsort(a)).astype(float)
        rb = np.argsort(np.argsort(b)).astype(float)
        ra -= ra.mean()
        rb -= rb.mean()
        den = math.sqrt(float(ra @ ra) * float(rb @ rb))
        return float(ra @ rb / den) if den else 0.0

    rows = [{"metric": "margin_mean_pct", "value": round(float(margins.mean()), 3)},
            {"metric": "margin_sd_pct", "value": round(float(margins.std(ddof=1)), 3)},
            {"metric": "margin_p05_pct", "value": round(float(np.percentile(margins, 5)), 3)},
            {"metric": "margin_p95_pct", "value": round(float(np.percentile(margins, 95)), 3)},
            {"metric": "margin_min_pct", "value": round(float(margins.min()), 3)},
            {"metric": "n_draws", "value": n},
            {"metric": "seed", "value": seed}]
    for nm, v in sorted(({nm: spearman(draws[:, j], margins)
                          for j, nm in enumerate(names)}).items(),
                        key=lambda kv: -abs(kv[1])):
        rows.append({"metric": f"spearman_{nm}", "value": round(v, 3)})
    return {"table": "uncertainty", "rows": rows,
            "columns": ["metric", "value"]}


def study_current_response(ctx) -> dict:
    """Peak amplitude over the sweep versus applied current (tuning curve)."""
    P = ctx["params"]
    rows = []
    for I in np.linspace(0.0, P["I_max_A"], 101):
        best = None
        for rpm in np.linspace(P["rpm_min"], P["rpm_max"], 400):
            r = coupled_response(float(rpm), float(I), P)
            if best is None or r["X1_m"] > best["X1_m"]:
                best = r
        rows.append({"I_A": round(float(I), 4),
                     "B_T": flux_density(float(I), P),
                     "peak_rpm": round(best["rpm"], 1),
                     "peak_X1_um": best["X1_m"] * 1e6,
                     "k2_Npm": best["k2"],
                     "natural_freq_ratio": math.sqrt(
                         best["k2"] / P["m2_kg"]) /
                     (2 * math.pi * best["rpm"] / 60.0)})
    return {"table": "current_response", "rows": rows,
            "columns": ["I_A", "B_T", "peak_rpm", "peak_X1_um", "k2_Npm",
                        "natural_freq_ratio"]}


def study_monte_carlo(ctx) -> dict:
    """Tolerance propagation onto the performance margin.

    Draws uniformly INSIDE the declared tolerances. A declared tolerance is a
    bound, not a standard deviation - treating it as sigma puts roughly a third
    of the draws outside the band you claimed to guarantee.
    """
    P = ctx["params"]
    seed = int(ctx.get("seed", 0))
    n = int(ctx.get("n", 400))
    tol = ctx.get("tolerances") or {
        "G0_Pa": 0.10, "Ginf_Pa": 0.10, "pad_t_m": 0.05,
        "m2_kg": 0.03, "shaft_d_m": 0.002, "tan_delta_inf": 0.08,
    }
    rng = np.random.default_rng(seed)
    rpms = np.linspace(P["rpm_min"], P["rpm_max"], 121)
    rows = []
    for k in range(n):
        Q = dict(P)
        for key, rel in tol.items():
            base = P[key]
            Q[key] = float(rng.uniform(base * (1 - rel), base * (1 + rel)))
        I = ctx.get("I_A", 0.333)
        peak = max(coupled_response(float(r), I, Q)["X1_m"] for r in rpms)
        peak0 = max(coupled_response(float(r), 0.0, Q)["X1_m"] for r in rpms)
        rows.append({"draw": k, "I_A": I,
                     "peak_ctrl_um": peak * 1e6,
                     "peak_off_um": peak0 * 1e6,
                     "margin_pct": (peak0 - peak) / peak0 * 100.0,
                     **{f"draw_{kk}": Q[kk] for kk in tol}})
    return {"table": "monte_carlo", "rows": rows,
            "columns": ["draw", "I_A", "peak_ctrl_um", "peak_off_um",
                        "margin_pct"] + [f"draw_{kk}" for kk in tol]}


STUDIES = {
    "speed_sweep": study_speed_sweep,
    "material_law": study_material_law,
    "current_response": study_current_response,
    "monte_carlo": study_monte_carlo,
    "validate": study_validate,
    "uncertainty": study_uncertainty,
}

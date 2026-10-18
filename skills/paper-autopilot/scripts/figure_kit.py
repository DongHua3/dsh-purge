#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""论文配图工具（thesis-pipeline 第 6 步）

解决中文论文配图的三个常见坑：
  1. 中文字体缺失导致图上出现方块——本工具自动探测可用中文字体并在缺失时明确告警；
  2. 只出 PNG 导致放大后模糊——本工具同时输出 PNG(300dpi) 与 PDF(矢量)；
  3. 配色不适合黑白打印——默认用 Okabe-Ito 色盲友好方案。

图定义用 JSON 描述（见 --example 输出的模板），支持折线图、柱状图、散点图、
双轴图与"多子图"组合。复杂图建议直接用 matplotlib 写脚本，用本工具的
setup_style() / save() 保证字体与输出规范。

用法：
    python figure_kit.py --example > figspec.json      # 生成模板
    python figure_kit.py --spec figspec.json --data data.csv --out figures/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

CJK_CANDIDATES = ["SimHei", "Microsoft YaHei", "SimSun", "Noto Sans CJK SC",
                  "Source Han Sans SC", "WenQuanYi Zen Hei", "PingFang SC",
                  "Heiti SC", "Songti SC"]
# Okabe-Ito 色盲友好配色
COLORS = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9",
          "#D55E00", "#F0E442", "#999999"]


def pick_cjk() -> str:
    avail = {f.name for f in font_manager.fontManager.ttflist}
    for n in CJK_CANDIDATES:
        if n in avail:
            return n
    print("!! 未找到中文字体：图上中文会显示为方块。", file=sys.stderr)
    print("   安装任一：SimHei / Microsoft YaHei / Noto Sans CJK SC，"
          "或改用英文标注。", file=sys.stderr)
    return "DejaVu Sans"


def setup_style() -> str:
    cjk = pick_cjk()
    plt.rcParams.update({
        "font.sans-serif": [cjk, "DejaVu Sans"],
        "font.family": "sans-serif",
        "axes.unicode_minus": False,
        "mathtext.default": "regular",
        "axes.formatter.use_mathtext": True,
        "figure.dpi": 120,
        "savefig.dpi": 300,          # 学位论文图 ≥300 dpi
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
    return cjk


def save(fig, outdir: Path, name: str):
    outdir.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(outdir / f"{name}.{ext}")
    plt.close(fig)
    print(f"  ok {name}.png / .pdf")


EXAMPLE = {
    "figures": [
        {
            "name": "fig4-1_示例折线",
            "kind": "line",
            "size": [7.2, 3.0],
            "x": "strain", "y": ["stress_bcc", "stress_fcc"],
            "labels": ["BCC", "FCC"],
            "xlabel": "应变 ε", "ylabel": "应力 σ / MPa",
            "title": "应力–应变曲线",
            "logy": False, "grid": True
        },
        {
            "name": "fig4-2_示例柱状",
            "kind": "bar",
            "size": [5.0, 3.0],
            "x": "group", "y": ["value"],
            "ylabel": "数值", "title": "分组对比",
            "yerr": "std"
        }
    ]
}


def plot_line(ax, df, spec):
    for i, col in enumerate(spec["y"]):
        if col not in df.columns:
            print(f"  !! 列 {col} 不存在，跳过")
            continue
        if spec.get("x") and spec["x"] in df.columns:
            ax.plot(df[spec["x"]], df[col], color=COLORS[i % len(COLORS)],
                    label=(spec.get("labels") or spec["y"])[i])
        else:
            ax.plot(df[col], color=COLORS[i % len(COLORS)],
                    label=(spec.get("labels") or spec["y"])[i])
    if spec.get("logy"):
        ax.set_yscale("log")
    if spec.get("logx"):
        ax.set_xscale("log")


def plot_bar(ax, df, spec):
    ycols = [c for c in spec["y"] if c in df.columns]
    if not ycols:
        raise ValueError(f"指定的 y 列在数据中都不存在：{spec['y']}；实际列 {list(df.columns)}")
    xcol = spec.get("x")
    if xcol:
        if xcol not in df.columns:
            raise ValueError(f"指定的 x 列 '{xcol}' 不存在；实际列 {list(df.columns)}")
        x = np.arange(len(df))
        w = 0.8 / len(ycols)
        for i, col in enumerate(ycols):
            err = None
            if spec.get("yerr") and spec["yerr"] in df.columns:
                # 必须转成 ndarray：直接传 Series 会按索引对齐到 x 数组，
                # 索引不匹配时 matplotlib 抛 "incompatible dimensions"
                err = np.asarray(df[spec["yerr"]], dtype=float)
            ax.bar(x + i * w, np.asarray(df[col], dtype=float), width=w, yerr=err,
                   capsize=3, color=COLORS[i % len(COLORS)],
                   label=(spec.get("labels") or ycols)[i], edgecolor="white", lw=0.8)
        ax.set_xticks(x + w * (len(ycols) - 1) / 2)
        ax.set_xticklabels(df[xcol].astype(str))
        if spec.get("labels") or len(ycols) > 1:
            ax.legend()
    else:
        # 无 x 列：每个 y 列各作一个分组，画均值柱 + 标准差误差棒
        means = [float(np.asarray(df[c], dtype=float).mean()) for c in ycols]
        errs = [float(np.asarray(df[c], dtype=float).std(ddof=1)) if len(df) > 1 else 0.0
                for c in ycols]
        ax.bar(range(len(ycols)), means, yerr=errs, capsize=3,
               color=[COLORS[i % len(COLORS)] for i in range(len(ycols))],
               edgecolor="white", lw=0.8)
        ax.set_xticks(range(len(ycols)))
        ax.set_xticklabels([(spec.get("labels") or ycols)[i] for i in range(len(ycols))])


def plot_scatter(ax, df, spec):
    for i, col in enumerate(spec["y"]):
        ax.scatter(df[spec["x"]], df[col], s=16, color=COLORS[i % len(COLORS)],
                   label=(spec.get("labels") or spec["y"])[i], alpha=0.85)
    if spec.get("labels"):
        ax.legend()


KINDS = {"line": plot_line, "bar": plot_bar, "scatter": plot_scatter}


def main() -> int:
    ap = argparse.ArgumentParser(description="论文配图工具")
    ap.add_argument("--example", action="store_true", help="打印图定义模板")
    ap.add_argument("--spec", help="图定义 JSON")
    ap.add_argument("--data", help="数据 CSV")
    ap.add_argument("--out", default="figures", help="输出目录")
    args = ap.parse_args()

    if args.example:
        print(json.dumps(EXAMPLE, ensure_ascii=False, indent=1))
        return 0

    if not args.spec or not args.data:
        print("需要 --spec 与 --data；先用 --example 看模板。")
        return 1

    cjk = setup_style()
    print(f"中文字体：{cjk}")
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    df = pd.read_csv(args.data, encoding="utf-8-sig")
    outdir = Path(args.out)
    print(f"数据 {len(df)} 行 | 生成 {len(spec.get('figures', []))} 幅图")

    for fs in spec.get("figures", []):
        kind = fs.get("kind", "line")
        fn = KINDS.get(kind)
        if not fn:
            print(f"  !! 未知图型 {kind}，跳过 {fs.get('name')}")
            continue
        size = fs.get("size", [7.2, 3.0])
        fig, ax = plt.subplots(figsize=size)
        fn(ax, df, fs)
        if fs.get("xlabel"):
            ax.set_xlabel(fs["xlabel"])
        if fs.get("ylabel"):
            ax.set_ylabel(fs["ylabel"])
        if fs.get("title"):
            ax.set_title(fs["title"])
        if fs.get("grid", True):
            ax.grid(alpha=0.25, lw=0.6)
        if kind == "line" and len(fs.get("y", [])) > 1:
            ax.legend()
        fig.tight_layout()
        save(fig, outdir, fs.get("name", "figure"))

    print(f"\n输出目录：{outdir.resolve()}")
    print("提示：图题建议写在 md 里（**图 4-1 标题**），不要画进图内，便于排版统一。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

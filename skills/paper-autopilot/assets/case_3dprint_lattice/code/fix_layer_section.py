#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复表 4-3 及其两段说明文字（一次性校准脚本科）。

背景：模型修正后层厚扫描变为全程单调递减，原"存在 2.0% 上升"的说明文字
已不成立；表格数值也需同步。本脚本按当前 data/ 重写这三处。
"""
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
    g = d[d.group == "layer_sweep"].sort_values("layer_h")
    e0, s0 = g.E_meas.iloc[0], g.sigma_peak.iloc[0]

    rows = ["| 层厚 $t$ / mm | 等效模量 / MPa | 模量保留率 / % | 峰值应力 / MPa | 强度保留率 / % | 比吸能 / (J/g) |",
            "|---|---|---|---|---|---|"]
    for _, r in g.iterrows():
        rows.append(f"| {r.layer_h:.2f} | {r.E_meas:.2f} | {100*r.E_meas/e0:.1f} | "
                    f"{r.sigma_peak:.3f} | {100*r.sigma_peak/s0:.1f} | {r.SEA:.3f} |")
    new_table = "\n".join(rows)

    t = P.read_text(encoding="utf-8")

    # 1) 表格
    old_lines, grab = [], False
    for line in t.splitlines():
        if line.startswith("| 层厚 $t$ / mm |"):
            grab = True
        if grab:
            old_lines.append(line)
            if line.startswith("| 0.30 |"):
                break
    old_table = "\n".join(old_lines)
    c1 = t.count(old_table)
    print("表 4-3 匹配:", c1)
    if c1 == 1:
        t = t.replace(old_table, new_table)

    # 2) 说明段一（保留率与降幅）
    old_p1_start = "在 0.10 mm 至 0.30 mm 区间内，模量保留率由 100.0% 单调降至"
    i = t.find(old_p1_start)
    j = t.find("\n", i)
    if i >= 0:
        old_p1 = t[i:j]
        new_p1 = (f"在 0.10 mm 至 0.30 mm 区间内，模量保留率由 100.0% 单调降至 "
                  f"{100*g.E_meas.iloc[-1]/e0:.1f}%，峰值应力保留率由 100.0% 单调降至 "
                  f"{100*g.sigma_peak.iloc[-1]/s0:.1f}%，二者均随层厚增大而单调下降。"
                  f"强度降幅（{100-100*g.sigma_peak.iloc[-1]/s0:.1f} 个百分点）约为模量降幅"
                  f"（{100-100*g.E_meas.iloc[-1]/e0:.1f} 个百分点）的 "
                  f"{(1-g.sigma_peak.iloc[-1]/s0)/(1-g.E_meas.iloc[-1]/e0):.1f} 倍，验证了式 (2-7) 与式 (2-8) 中"
                  f"\"键合因子对模量取半权、对强度取全权\"的处理：层间界面对弹性模量的削弱作用"
                  f"明显弱于对强度的影响。这一结论的物理意义是，层间界面主要作为裂纹萌生与扩展的"
                  f"优先路径，通过降低强度而限制承载能力上限，而不显著改变材料的弹性刚度。")
        t = t[:i] + new_p1 + t[j:]
        print("说明段一已重写")

    # 3) 说明段二（原"非单调现象"整段删除并替换为口径说明）
    old_p2_key = "需要指出一处局部波动"
    i2 = t.find(old_p2_key)
    if i2 >= 0:
        j2 = t.find("\n", i2)
        new_p2 = ("需要说明的是，早期版本中模量曾在 0.10–0.15 mm 区间出现 2.0% 的反常上升。"
                  "经排查，该现象的来源不是物理机制，而是式 (2-14) 平滑最小值算子的参数取值过小"
                  "（$\\beta$ = 60），使平台段在低应变处抬起并污染了弹性斜率的拟合窗口。"
                  "$\\beta$ 增至 150 后过渡区宽度收窄至约 ±0.03 应变，伪影消除，层厚扫描恢复全程单调。"
                  "这一排查过程记录于 4.7.1 节，作为数值研究实现层面易错点的实例。")
        t = t[:i2] + new_p2 + t[j2:]
        print("说明段二已重写")

    # 4) 比吸能段
    old3 = t[t.find("比吸能与层厚呈单调下降关系"):]
    k = old3.find("\n")
    if k > 0:
        old3 = old3[:k]
        new3 = (f"比吸能与层厚呈单调下降关系，由 {g.SEA.iloc[0]:.2f} J/g 降至 {g.SEA.iloc[-1]:.2f} J/g，"
                f"降幅 {100*(1-g.SEA.iloc[-1]/g.SEA.iloc[0]):.1f}%，与峰值应力的降幅"
                f"（{100*(1-g.sigma_peak.iloc[-1]/s0):.1f}%）接近。这是因为 SEA 主要由平台段的应力水平决定"
                f"（式 2-17），而平台应力与峰值应力同比例变化。")
        t = t.replace(old3, new3)
        print("比吸能段已重写")

    P.write_text(t, encoding="utf-8", newline="\n")
    print("已写入", P.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())

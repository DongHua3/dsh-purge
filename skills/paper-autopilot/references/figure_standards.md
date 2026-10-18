# 图件与表格规范（第 10 步作业指导）

> 本文件的数字全部来自出版商官方页面的原文，已在文末列出出处。
> **投稿前务必再查一次目标刊当日的作者指南**——规格会变。
> 拿不准时的通用安全做法在最后一节。

---

## 一、先分清"主图"和"扩展数据图"

Nature 系对这两类的要求完全不同，别的刊也大致是这个思路：

| | 主图（Main figure） | 扩展数据图（Extended Data / Supplementary） |
|---|---|---|
| 格式 | **矢量 + 可编辑图层**：`.ai` / `.eps` / `.pdf` | `.jpeg`（首选）/ `.tiff` / `.eps` |
| 分辨率 | 矢量不限；照片类图像最低 300 dpi、建议 ≥450 dpi | **最高 300 dpi**（不是越高越好） |
| 色彩空间 | **RGB**（不是 CMYK；印刷时出版方自动转） | RGB |
| 文件大小 | ≤50 MB，所有组件**嵌入**而非链接 | ≤10 MB |
| 排版 | 单栏宽 89 mm，双栏宽 183 mm，**最大高 170 mm** | 单页放得下；单栏 8.9 cm / 双栏 18 cm |
| 命名 | 按刊要求 | `通讯作者姓_EDfig1.jpg` |

**⚠️ Nature 主图明确不接受 `.jpeg / .tiff / .png`。**
这是一个很多人第一次投稿就栽的地方——用 Python 出 PNG 直接交，会被退回重做。

---

## 二、尺寸

- Nature：**单栏 89 mm，双栏 183 mm，最大高 170 mm**（给图注留位置）。
- 其他刊常见：单栏 85–90 mm，1.5 栏 114–140 mm，双栏 170–190 mm。
- **投稿时按最终尺寸出图，不要出大了让出版方缩。**
  缩图会把 6 pt 的字缩成 4 pt，直接不达标。
- 字体在最终尺寸下必须落在 **5–7 pt** 之间。低于 5 pt 不可读，高于 7 pt 显得业余。

**matplotlib 出图时这么设**（以双栏 183 mm 为例）：

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

mm = 1 / 25.4
fig, axes = plt.subplots(1, 2, figsize=(183 * mm, 70 * mm))

for ax in axes:
    ax.tick_params(labelsize=6, width=0.6, length=2.5)   # 刻度字号落在 5-7 pt
    for s in ax.spines.values():
        s.set_linewidth(0.6)
    ax.set_xlabel("Rotational speed (rpm)", fontsize=7)
    ax.set_ylabel("Amplitude ($\\mu$m)", fontsize=7)
    ax.grid(False)                                        # Nature 明确不要网格线

matplotlib.rcParams["pdf.fonttype"] = 42                  # 嵌入 TrueType，不转曲
matplotlib.rcParams["ps.fonttype"] = 42
fig.savefig("fig1.pdf", bbox_inches="tight", pad_inches=0.02)
```

---

## 三、字体与文字

| 要求 | 说明 |
|---|---|
| 字族 | **无衬线**，优先 Helvetica 或 Arial |
| 字号 | 最小 **5 pt**，最大 **7 pt** |
| 子图编号 | **8 pt 粗体**、正体（非斜体）、小写 `a, b, c…` |
| 希腊字母 | 用 Symbol 字体的字形，不要用别的字体硬凑 |
| 公式变量 | 斜体（*k*, *ω*, *m*）；单位和数字正体 |
| 转曲 | **不要转曲**。转曲后出版方无法改字号，会被退回 |
| 字体嵌入 | TrueType 2 或 42；**不要 TrueType 3** |
| 字色 | 不要给文字上色；改用黑字 + 引线/色块 |
| 对比度 | 文字与背景对比度 > 4.5:1 |

**Python 用户最容易踩的两个坑**：

1. `pdf.fonttype` 默认是 3（TrueType 3），Nature 不接受。
   必须设 `matplotlib.rcParams['pdf.fonttype'] = 42`。
2. 用 MATLAB 在 Linux 下导出会因为 freetype 而非 truetype 出问题；
   读者若用 MATLAB，需在 Windows/macOS 上导出。

---

## 四、坐标轴与数据呈现

**必须有**：

- 轴线（axis lines）与**刻度线（tick marks）**——两者都要，缺刻度线是常见退稿点
- 每个轴都标单位，**单位放在括号里**：`Amplitude (µm)`、`Speed (rpm)`
- 误差棒必须在图注里**说明代表什么**（SD / SEM / 95% CI / 范围），并给出 n

**不要有**：

- 背景网格线
- 阴影、立体效果、装饰性图标
- 图案填充（用纯色区分）
- 文字压在复杂图像上
- 文字互相重叠
- 彩色文字

**关于柱状图**：越来越多的刊要求展示数据点分布而不是只给均值+误差棒。
如果你的数据点不多（n < 20），直接画散点或箱线图 + 散点。

---

## 五、配色（可直接抄）

Nature 官方给出的色盲友好调色板（来自 Wong, *Points of view: Colour blindness*,
Nature Methods **8**, 441 (2011)），十六进制值如下：

| 名称 | Hex | RGB |
|---|---|---|
| Black | `#000000` | 0, 0, 0 |
| Orange | `#e69f00` | 230, 159, 0 |
| Sky blue | `#56b4e9` | 86, 180, 233 |
| Bluish green | `#009e73` | 0, 158, 115 |
| Yellow | `#f0e442` | 240, 228, 66 |
| Blue | `#0072b2` | 0, 114, 178 |
| Vermillion | `#d55e00` | 213, 94, 0 |
| Reddish purple | `#cc79a7` | 204, 121, 167 |

```python
WONG = ["#000000", "#e69f00", "#56b4e9", "#009e73",
        "#f0e442", "#0072b2", "#d55e00", "#cc79a7"]
```

**避开**：红/绿搭配（色盲最常见的盲区）、彩虹/jet 色图（`plt.cm.jet`）、
只有靠颜色才能区分的多条曲线。连续量用 `viridis` / `cividis` / `magma`。

**检查方法**：出图后用色盲模拟看一眼，或者干脆再导一版灰度图看能不能区分。

---

## 六、图注（Figure legend）

一条合格的图注要让人**不看正文也能看懂这张图**。包含：

1. **一句话标题**——这张图画的是什么（不是结论）
2. **子图说明**：`(a) … (b) …`
3. **数据来源**：实验/仿真、n 是多少、重复几次
4. **误差棒含义**：SD / SEM / 95% CI
5. **统计方法**：用了什么检验、显著性标记代表什么（`*p<0.05` 之类要写全）
6. **符号与缩写**：图里出现的所有符号都要有定义
7. **比例尺说明**（有图像时）

**图注不要重复正文。** 图注说"这张图是什么"，正文说"这张图说明什么"。

**常见错误**：图注里写"如图 3 所示，结果显著优于基线"——这是结论，属于正文。
图注该写"图 3 三种控制策略的峰值振幅随转速变化。数据来自表 2 的 241 点扫描，n=3 次重复，误差棒为 ±1 SD。"

---

## 七、表格

- 表格**不是**图的替代品：需要精确数值、需要逐项对照时用表；看趋势、看形状时用图。
- 表格要能编辑（Word/LaTeX 表格，或投稿系统接受的格式），**不要贴图片**。
- 表题在表**上方**；图注在图**下方**。
- 三线表是工程刊的主流：顶线、表头下线、底线；不要竖线和单元格边框。
- 单位写在列头：`Peak amplitude (µm)`，不要在每个格子里重复写单位。
- 同一列的小数位数要一致（不要一列里既有 `24.8` 又有 `24.8135`）。
- 表注（footnote）用上标字母 `a, b, c`，按顺序引用。

---

## 八、可复现性

- **保留出图脚本**。期刊越来越常要求提供绘图代码或源数据。
- Nature 系要求提供 **Source Data**（图背后的原始数据文件），
  并在图注或数据可得性声明中指向它。
- 出图用的数据文件、脚本、以及脚本里的随机种子，一起归档。
- 数据与代码建议存 Zenodo/figshare 并拿一个 DOI，写进 Data/Code Availability。

---

## 九、通用安全做法（不确定时按这个来）

如果目标刊的规格一时查不到，按这组参数出图基本不会被退：

| 项 | 安全值 |
|---|---|
| 宽度 | 单栏 90 mm，双栏 180 mm |
| 字体 | Arial / Helvetica，6–7 pt |
| 刻度线 | 有，朝内，0.6 pt 粗，2.5 mm 长 |
| 轴线 | 四边或左下两边，0.6–0.75 pt |
| 网格线 | 无 |
| 配色 | 上面的 Wong 八色 |
| 输出 | **PDF（矢量）为主**，另存 600 dpi TIFF/PNG 备用 |
| 字体嵌入 | TrueType 42 |
| 子图编号 | 8 pt 粗体小写字母 |

**永远主交矢量 PDF**。矢量格式在任何刊都是前两种首选格式之一，
而 PNG 在 Nature 主图里是明确被拒的。

---

## 出处

- Nature research figure guide — *Preparing figures: our specifications*:
  https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/
- Nature research figure guide — *Building and exporting figure panels*:
  https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/
- Wong, B. *Points of view: Colour blindness.* Nature Methods **8**, 441 (2011).
- Elsevier artwork guidelines and FAQ:
  https://www.elsevier.com/about/policies-and-standards/author/artwork-and-media-instructions/artwork-faq

> 抓取日期见 `_sources/` 目录下的原始文本（含 HTTP 状态码）。
> 本文件里 Nature 的数值均为上述页面 2026 年版原文，非二手转述。

# assets 目录说明

这里放的是**脚手架模板**和**一个跑通的真实案例**。技能本体（`references/` + `scripts/`）
是可复用的方法；`assets/` 是"照这个样子开工"的起点和"这样算做完了"的样本。

```
assets/
├── BRIEF.md.tpl                   第 01 步：把 SCI 默认值改写成学位论文口径的那张表
├── PIPELINE.md.tpl                人可读进度真源（差异表 / 总检结果 / 未达标项 / 校准记录）
├── PAPER_STATE.json.tpl           机器可读状态（22 步骨架 + gates + decisions）
├── DECISIONS.md.tpl               自动决策记录（D 段流水线决定 / U 段只能用户决定）
└── case_3dprint_lattice/          真实案例：3D 打印点阵结构本科毕业论文
    ├── README.md                  这个案例是什么、结果如何、哪些数字可复用
    ├── PIPELINE.md                案例交付时的原文件（22/22）
    ├── DECISIONS.md               案例的 10 条决策 + 4 条用户决策
    └── code/                      20 个项目专用脚本（含硬编码单项目版）
```

## 怎么用

1. **开工**：跑 `scripts/scaffold.py --dir <项目> --title "<题目>" --type 本科`，
   它按 `BRIEF.md.tpl` / `PAPER_STATE.json.tpl` / `DECISIONS.md.tpl` 的结构生成骨架；
   也可以手工拷模板再替换 `<尖括号>` 占位符。
2. **对照**：走到某一步拿不准产出物长什么样，去看 `case_3dprint_lattice/` 里对应的原文件。
3. **别照抄数字**：案例里的数值属于那个题目、那个模型、那批文献。可复用的是
   **结构、口径、检查项、事故清单**；不可复用的是具体参数与结论。

## 两个容易踩的坑

- `.tpl` 里的占位符用 `<尖括号>` 包住，**不要留在交付稿里**。
  `scripts/selfcheck.py` 会扫占位符残留，`final_check.py` 会扫 `〔待填：…〕`。
- `PAPER_STATE.json.tpl` 是纯 JSON，**不能加注释**（JSON 不认）。说明写在 `_note` 键里。

## 与 `scripts/` 的关系

`assets/case_3dprint_lattice/code/` 里同名的 `build_docx.py`、`final_check.py`、
`math2unicode.py`、`docx_to_pdf.py`、`wordcount.py` 是**硬编码单项目版**：
路径写死在 `Desktop\毕业论文` 下，只服务那一个项目。技能包 `scripts/` 下的是**参数化版**
（`Cfg` 类 + CLI 参数），两者不要互相覆盖。要用通用能力，用 `scripts/`；要学"当年怎么写死的"，看案例。

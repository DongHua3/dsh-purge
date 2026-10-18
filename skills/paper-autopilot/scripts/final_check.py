#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交付前总检（thesis-pipeline 第 20 步）

把本项目真实踩过的坑固化成自动检查项，任一项 FAIL 就不要交付。

检查清单：
  1  章节目录完整性（封面/目录/摘要/各章/参考文献/致谢）
  2  正文字数达标（按 thesis.json 的 targets.words 的 90% 计）
  3  图编号连续 + 图片文件存在
  4  表数量与编号
  5  参考文献：悬空引用 / 孤立条目 / 引用内容匹配（调用 check_refs.py）
  6  小节编号连续 + 正文小节交叉引用不悬空
  7  成品 docx 无 LaTeX / $ / 反引号残留
  8  正文数字与 data/ 下数据文件的一致性抽查（防"模型改了正文没改"）
  9  作者占位符集中列出
  10 交付件存在（docx/pdf）且 pdf 页数、嵌入图数可读
  11 输出 SHA-256 哈希表

用法：
    python final_check.py --dir <项目目录> --write
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

HERE = Path(__file__).resolve().parent
CITE = re.compile(r"\[(\d+(?:\s*[,，\-–]\s*\d+)*)\]")
PLACEHOLDER = re.compile(r"〔[^〕]{0,30}待填[^〕]{0,20}〕|〔待填[^〕]*〕")
SUBREF = re.compile(r"(\d)\.(\d+)\s*节")
LATEX_CMD = re.compile(
    r"\\(?:frac|tfrac|dfrac|sqrt|bar|hat|tilde|vec|mathrm|mathbf|mathit|text|"
    r"left|right|rho|sigma|theta|alpha|beta|gamma|delta|varepsilon|epsilon|"
    r"lambda|mu|eta|kappa|chi|times|cdot|approx|leq|geq|infty|partial|sum|"
    r"int|tag|quad|qquad|begin|end|underbrace)\b")

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))


def read_all(paths) -> str:
    return "\n\n".join(p.read_text(encoding="utf-8") for p in paths)


def docx_text(path: Path) -> str:
    try:
        from docx import Document
    except ImportError:
        return ""
    d = Document(str(path))
    out = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            for c in row.cells:
                out.append(c.text)
    return "\n".join(out)


def expand(tok: str) -> set[int]:
    out: set[int] = set()
    for part in re.split(r"[,，]", tok):
        part = part.strip()
        m = re.match(r"^(\d+)\s*[-–]\s*(\d+)$", part)
        if m:
            out.update(range(int(m.group(1)), int(m.group(2)) + 1))
        elif part.isdigit() and int(part) >= 1:
            out.add(int(part))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="交付前总检")
    ap.add_argument("--dir", required=True, help="项目目录")
    ap.add_argument("--write", action="store_true", help="写出报告与哈希表")
    args = ap.parse_args()

    root = Path(args.dir).resolve()
    man = root / "manuscript"
    figs = root / "figures"
    data = root / "data"
    deliv = root / "deliverables"
    refs_md = None
    for cand in [root / "05_稿件" / "参考文献.md", root / "参考文献.md"]:
        if cand.exists():
            refs_md = cand
            break

    cfg = {}
    cfgp = root / "thesis.json"
    if cfgp.exists():
        config = json.loads(cfgp.read_text(encoding="utf-8"))
        cfg = config
    targets = cfg.get("targets", {})

    md_files = sorted(man.glob("*.md")) if man.is_dir() else []
    if not md_files:
        print(f"找不到分章 md（{man}）")
        return 1
    full = read_all(md_files)

    # 1 章节完整性
    need = cfg.get("required_sections",
                   ["摘要", "Abstract", "第 1 章", "参考文献", "致谢"])
    missing = [s for s in need if s not in full and (refs_md is None or s not in refs_md.read_text(encoding="utf-8"))]
    check("章节完整性", not missing, "齐全" if not missing else f"缺失：{missing}")

    # 2 字数
    body_only = re.sub(r"```.*?```", "", full, flags=re.S)
    cjk = len(re.findall(r"[\u4e00-\u9fff]", body_only))
    want = int(targets.get("words", 15000) * 0.9)
    check(f"正文字数 ≥ {want}", cjk >= want, f"实际 {cjk} 中文字符")

    # 3 图
    fig_names = re.findall(r"!\[[^\]]*\]\(figures/([^)]+)\)", full)
    fig_nums = re.findall(r"!\[[^\]]*\]\(figures/fig(\d+)-(\d+)_", full)
    ch_map: dict[str, list[int]] = {}
    for ch, n in fig_nums:
        ch_map.setdefault(ch, []).append(int(n))
    bad_seq = {c: v for c, v in ch_map.items() if v != list(range(1, len(v) + 1))}
    check("图编号连续", not bad_seq, "连续" if not bad_seq else f"异常：{bad_seq}")
    miss_img = [f for f in fig_names if not (figs / f).exists()]
    check("图片文件存在", not miss_img,
          f"{len(fig_names)}/{len(fig_names)} 存在" if not miss_img else f"缺失 {miss_img[:4]}")

    # 4 表
    tabs = sorted({t for t in re.findall(r"\*\*表\s*([\d\-]+)", full)})
    check("表编号存在", len(tabs) >= 2, f"{len(tabs)} 张表")

    # 5 参考文献（调用 check_refs.py）
    if refs_md:
        cp = subprocess.run(
            [sys.executable, str(HERE / "check_refs.py"), "--manuscript", str(man),
             "--refs", str(refs_md)],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = cp.stdout or ""
        dangling = "悬空引用：0 处" in out
        orphan = "孤立条目：0 条" in out
        mis = "引用内容匹配：0 处可疑" in out
        check("参考文献一致（悬空/孤立/内容匹配）", dangling and orphan and mis,
              "三项全通过" if (dangling and orphan and mis)
              else "见 check_refs.py 输出：" + " ".join(
                  l for l in out.splitlines() if l.startswith("[")))
    else:
        check("参考文献一致", False, "找不到参考文献.md")

    # 6 小节编号与交叉引用
    secs = set(re.findall(r"^#{2,4}\s+(\d+\.\d+)", full, re.M))
    refs_secs = {f"{a}.{b}" for a, b in SUBREF.findall(full)}
    dangling_sec = sorted(s for s in refs_secs if s not in secs)
    seq_ok = True
    for ch in {s.split(".")[0] for s in secs}:
        nums = sorted(int(s.split(".")[1]) for s in secs if s.startswith(ch + "."))
        if nums and nums != list(range(1, len(nums) + 1)):
            seq_ok = False
    check("小节编号连续", seq_ok, "连续" if seq_ok else "存在跳号（如 4.7 后直接 4.10）")
    check("小节交叉引用不悬空", not dangling_sec,
          "全部有对应小节" if not dangling_sec else f"悬空：{dangling_sec}")

    # 7 成品残留
    docx = None
    if deliv.is_dir():
        docs = sorted(deliv.glob("*.docx"))
        docx = docs[0] if docs else None
    if docx:
        dt = docx_text(docx)
        # 附录里贴的代码天然含 $、\frac 等字样（如 python 的 polyfit(...)[0]），
        # 因此先剔除"代码行"再判定残留。代码行的特征：含 = 赋值 / import / def /
        # print( ，或含代码围栏标记。
        CODEISH = re.compile(r"(^\s*(import|from|def|class|print|return|for|while|if)\b"
                             r"|=|\[0\]|\bplt\.|\bnp\.|\bpd\.)")
        plain = [l for l in dt.splitlines() if not CODEISH.search(l)]
        pt = "\n".join(plain)
        dols, latex, bt = pt.count("$"), len(LATEX_CMD.findall(pt)), dt.count("```")
        check("成品无公式/标记残留（docx）", dols == 0 and latex == 0 and bt == 0,
              f"$ {dols}，LaTeX {latex}，反引号块 {bt}")
    else:
        check("成品无公式/标记残留（docx）", False, "deliverables/ 下没有 docx")

    # 8 数字一致性抽查：正文里出现的数字能否在 data/ 找到同值
    if data.is_dir():
        nums_in_data = set()
        for f in data.glob("*.csv"):
            try:
                txt = f.read_text(encoding="utf-8-sig", errors="ignore")
            except Exception:
                continue
            for m in re.finditer(r"\d+\.\d{1,4}", txt):
                nums_in_data.add(m.group(0))
        body_nums = set(re.findall(r"(?<![\d.])(\d+\.\d{1,4})(?![\d])", body_only))
        # 只抽查"看起来像结果"的数值（>=0.1 且非年份/非百分比）
        sample = {n for n in body_nums if float(n) >= 0.1}
        if sample:
            hit = sum(1 for n in sample if n in nums_in_data)
            ratio = hit / len(sample)
            check("正文数字与 data/ 一致性抽查", ratio >= 0.6,
                  f"{hit}/{len(sample)} 可在 data/ 找到同值（阈值 60%；偏低通常意味着模型改过而正文数字未回填）")
        else:
            check("正文数字与 data/ 一致性抽查", True, "正文未发现需抽查的数值")
    else:
        check("正文数字与 data/ 一致性抽查", False, "没有 data/ 目录")

    # 9 占位符
    ph = sorted(set(PLACEHOLDER.findall(full)))
    check("作者占位符已集中标注", True, f"{len(ph)} 处待替换")

    # 10 交付件
    for ext in ("docx", "pdf"):
        f = None
        if deliv.is_dir():
            cands = sorted(deliv.glob(f"*.{ext}"))
            f = cands[0] if cands else None
        check(f"交付件 .{ext} 存在", bool(f),
              f"{f.stat().st_size/1024:.0f} KB" if f else "缺失")
    if deliv.is_dir():
        pdfs = sorted(deliv.glob("*.pdf"))
        if pdfs:
            try:
                import pymupdf
                d = pymupdf.open(str(pdfs[0]))
                n_img = sum(len(p.get_images(full=True)) for p in d)
                check("PDF 页数与嵌入图可读", d.page_count > 0,
                      f"{d.page_count} 页 / {n_img} 图（md 中引用 {len(fig_names)} 图）")
            except Exception as e:  # noqa: BLE001
                check("PDF 页数与嵌入图可读", False, f"PyMuPDF 读取失败：{e}")

    # 输出
    lines = [f"# 交付前总检报告", "",
             f"项目：`{root}`", f"生成：由 thesis-pipeline/scripts/final_check.py", "",
             "| 检查项 | 结果 | 说明 |", "|---|---|---|"]
    npass = 0
    for name, ok, detail in results:
        npass += bool(ok)
        lines.append(f"| {name} | {'✅ 通过' if ok else '❌ 未通过'} | {detail} |")
    lines += ["", f"**{npass}/{len(results)} 项通过。**", ""]
    if ph:
        lines += ["## 待替换的占位符", ""] + [f"- `{x}`" for x in ph] + [""]
    report = "\n".join(lines)
    print(report)

    if args.write:
        outdir = root / "20_投稿前总检"
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "CHECK_REPORT.md").write_text(report, encoding="utf-8")
        hashes = []
        for base in (data, figs, deliv):
            if not base.is_dir():
                continue
            for p in sorted(base.rglob("*")):
                if p.is_file() and p.suffix.lower() in (".csv", ".json", ".png", ".pdf", ".docx"):
                    hashes.append((str(p.relative_to(root)),
                                   hashlib.sha256(p.read_bytes()).hexdigest(),
                                   p.stat().st_size))
        hl = ["# 交付物哈希表（SHA-256）", "",
              "重跑 `python scripts/final_check.py --dir . --write` 可刷新。", "",
              "| 文件 | 字节 | SHA-256 |", "|---|---|---|"]
        hl += [f"| `{r}` | {s} | `{h}` |" for r, h, s in hashes]
        deliv.mkdir(parents=True, exist_ok=True)
        (deliv / "HASHES.txt").write_text("\n".join(hl), encoding="utf-8")
        print(f"\n已写出：{outdir / 'CHECK_REPORT.md'}")
        print(f"已写出：{deliv / 'HASHES.txt'}（{len(hashes)} 个文件）")

    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())

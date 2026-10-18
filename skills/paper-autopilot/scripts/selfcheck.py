#!/usr/bin/env python3
"""selfcheck — audit a paper project for the things that make a manuscript unsafe.

`autopilot.py check` only verifies that each step produced its files. This goes
further and looks at the *content*: leftover placeholders, numbers that appear
in the prose but nowhere in the data, figures cited but not drawn, references
cited but not listed, undisclosed degraded steps, and the de-AI gates.

    python selfcheck.py --dir <project folder>
    python selfcheck.py --dir <project folder> --json report.json

Exit 0 = no blocking problem found. Exit 1 = at least one blocking problem.
Standard library only plus the sibling prose_scan.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Text that means somebody left the work unfinished.
PLACEHOLDERS = [
    "TODO", "TBD", "FIXME", "XXX", "PLACEHOLDER", "待补", "待填", "占位",
    "此处", "lorem ipsum", "[insert", "<insert", "待确认", "未完成",
]
# These appear legitimately in the author field of an unpublished draft. In
# BRIEF.md they are a warning (the pipeline itself scaffolds an author
# placeholder); anywhere else they are still blocking.
PLACEHOLDER_SOFT = {"占位", "待确认", "placeholder", "PLACEHOLDER"}

NUM_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?:\s*%)?")
FIG_CITE = re.compile(r"\b(?:Fig(?:ure)?\.?|图)\s*(\d+)", re.I)
TAB_CITE = re.compile(r"\b(?:Tab(?:le)?\.?|表)\s*(\d+)", re.I)
REF_CITE = re.compile(r"\[(\d+(?:\s*[,\u2013-]\s*\d+)*)\]")
REF_ENTRY = re.compile(r"^\s*\[?(\d+)\]?[.)]?\s+\S", re.M)


def _utf8() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def read(p: str) -> str:
    try:
        with io.open(p, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def walk(root: str, exts=(".md", ".txt", ".csv", ".json")) -> list[str]:
    out = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in ("__pycache__", ".git")]
        for f in fn:
            if f.lower().endswith(exts):
                out.append(os.path.join(dp, f))
    return out


GENERATED = {"SELFCHECK.md", "PIPELINE.md", "DECISIONS.md",
             "PAPER_STATE.json", "_selfcheck_deai.json"}


def collect_numbers(text: str) -> set[str]:
    """Numeric tokens in the prose, normalised.

    Figure numbers, table numbers and reference indices are stripped first:
    'Figure 5' and '[12]' are cross-references, not measurements, and counting
    them would bury the real findings under false positives.
    """
    text = FIG_CITE.sub(" ", text)
    text = TAB_CITE.sub(" ", text)
    text = REF_CITE.sub(" ", text)
    out = set()
    for m in NUM_RE.finditer(text):
        tok = m.group(1)
        try:
            v = float(tok)
        except ValueError:
            continue
        if v < 3:            # 0/1/2 are almost always enumeration
            continue
        if 1900 <= v <= 2100 and "." not in tok:   # years
            continue
        out.add(tok)
    return out


def _traceable(prose_tok: str, data: set[str], data_sorted: list[str]) -> bool:
    """A prose number is traceable if the data contains it exactly, or contains
    a more precise value that rounds to it (182.5 <- 182.5485)."""
    if prose_tok in data:
        return True
    for d in data_sorted:
        if d.startswith(prose_tok) and len(d) > len(prose_tok):
            return True
        # '24.8' should match '24.81' in either direction once both are short
        if len(prose_tok) >= 4 and prose_tok.startswith(d):
            return True
    return False


def expand_cites(raw: str) -> set[int]:
    """'[3, 7-9]' -> {3,7,8,9}"""
    out: set[int] = set()
    for chunk in re.split(r"\s*,\s*", raw.strip()):
        m = re.fullmatch(r"(\d+)\s*[\u2013-]\s*(\d+)", chunk)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if 0 < b - a < 60:
                out.update(range(a, b + 1))
        elif chunk.isdigit():
            out.add(int(chunk))
    return out


BIB_NAMES = ("references.md", "06_references.md", "99_references.md",
             "bibliography.md", "refs.md")


def audit(root: str) -> dict:
    rep: dict = {"dir": root, "blocking": [], "warnings": [], "info": {}}

    ms = os.path.join(root, "manuscript")
    mfiles = sorted(walk(ms)) if os.path.isdir(ms) else []
    bib_file = ""
    for cand in BIB_NAMES:
        p = os.path.join(ms, cand)
        if os.path.isfile(p):
            bib_file = p
            break
    # the reference list is not prose: its bracketed numbers are bibliography
    # indices, not measurements, and would poison every downstream check
    body_files = [f for f in mfiles if f != bib_file]
    prose = "\n".join(read(f) for f in body_files)
    rep["info"]["manuscript_files"] = [os.path.basename(f) for f in body_files]
    rep["info"]["bibliography_file"] = os.path.basename(bib_file) if bib_file else ""

    # ---- 1. placeholders -------------------------------------------------
    for f in walk(root):
        base = os.path.basename(f)
        if base in GENERATED:
            continue                      # our own outputs quote the findings
        if os.sep + "journal_papers" + os.sep in f:
            continue
        t = read(f)
        for ph in PLACEHOLDERS:
            if ph.lower() in t.lower():
                msg = f"{os.path.relpath(f, root)} 含占位文本「{ph}」"
                if ph in PLACEHOLDER_SOFT and base == "BRIEF.md":
                    rep["warnings"].append(msg + "（作者字段，投稿前替换即可）")
                else:
                    rep["blocking"].append(msg)

    # ---- 2. numbers traceable to data ------------------------------------
    data_dir = os.path.join(root, "data")
    data_text = ""
    if os.path.isdir(data_dir):
        data_text = "\n".join(read(f) for f in walk(data_dir))
    figs_dir = os.path.join(root, "figures")
    for sub in ("10_图表制作与引用", "03_检索与导出"):
        d = os.path.join(root, sub)
        if os.path.isdir(d):
            data_text += "\n".join(read(f) for f in walk(d))
    if data_text:
        in_data = collect_numbers(data_text)
        data_sorted = sorted(in_data, key=len, reverse=True)
        in_prose = collect_numbers(prose)
        untraced = sorted((t for t in in_prose
                           if not _traceable(t, in_data, data_sorted)),
                          key=lambda x: -len(x))[:40]
        rep["info"]["numbers_in_prose"] = len(in_prose)
        rep["info"]["numbers_in_data"] = len(in_data)
        rep["info"]["untraced_numbers"] = untraced
        if untraced:
            pct = 100.0 * len(untraced) / max(1, len(in_prose))
            sev = rep["warnings"] if pct <= 40 else rep["blocking"]
            sev.append(
                f"正文有 {len(untraced)} 个数字（{pct:.0f}%）在 data/ 里找不到"
                f"——逐个核对这些是计算值还是笔误：{untraced[:12]}")
    else:
        rep["warnings"].append("没有 data/ 目录或为空，无法核对正文数字来源")

    # ---- 3. figures cited vs drawn ---------------------------------------
    cited_figs = sorted({int(x) for x in FIG_CITE.findall(prose)})
    cited_tabs = sorted({int(x) for x in TAB_CITE.findall(prose)})
    drawn = set()
    for d in (figs_dir, os.path.join(root, "10_图表制作与引用")):
        if os.path.isdir(d):
            for f in os.listdir(d):
                m = re.search(r"(?:fig|figure|图)\s*0*(\d+)", f, re.I)
                if m:
                    drawn.add(int(m.group(1)))
    rep["info"]["figures_cited"] = cited_figs
    rep["info"]["figures_drawn"] = sorted(drawn)
    missing_fig = [n for n in cited_figs if drawn and n not in drawn]
    if missing_fig:
        rep["blocking"].append(f"正文引用但找不到图件文件：Figure {missing_fig}")
    if cited_figs != sorted(set(cited_figs)):
        rep["warnings"].append("图号有重复引用")
    if cited_figs:
        gaps = [n for n in range(1, max(cited_figs) + 1) if n not in cited_figs]
        if gaps:
            rep["warnings"].append(f"图号不连续，缺：{gaps}")
    rep["info"]["tables_cited"] = cited_tabs

    # ---- 4. references cited vs listed -----------------------------------
    cited: set[int] = set()
    for raw in REF_CITE.findall(prose):
        cited |= expand_cites(raw)
    bib_text = read(bib_file) if bib_file else ""
    listed: set[int] = set()
    if bib_text:
        listed = {int(x) for x in REF_ENTRY.findall(bib_text)}
    rep["info"]["refs_cited"] = sorted(cited)
    rep["info"]["refs_listed"] = len(listed)
    if listed:
        never = sorted(listed - cited)
        undef = sorted(cited - listed)
        if undef:
            rep["blocking"].append(f"正文引用了但参考文献表里没有：[{undef}]")
        if never:
            rep["warnings"].append(
                f"参考文献表里列出但正文从未引用：[{never}]——多数刊要求删除")
    elif cited:
        rep["warnings"].append(
            "正文有编号引用，但没找到参考文献文件"
            f"（manuscript/{BIB_NAMES[0]}），无法核对")

    # ---- 5. degraded steps must be disclosed -----------------------------
    stp = os.path.join(root, "PAPER_STATE.json")
    if os.path.isfile(stp):
        try:
            st = json.loads(read(stp))
        except ValueError:
            st = {}
        deg = st.get("degraded") or []
        rep["info"]["degraded_steps"] = deg
        if deg:
            deliv = ""
            for cand in ("submission/README.md", "README.md",
                         "20_投稿前总检/PRESUBMIT_CHECK.md"):
                p = os.path.join(root, cand.replace("/", os.sep))
                if os.path.isfile(p):
                    deliv += read(p)
            undisclosed = [d for d in deg
                           if d.get("reason", "")[:20] not in deliv]
            rep["info"]["undisclosed_degradations"] = undisclosed
            if undisclosed:
                rep["blocking"].append(
                    f"有 {len(undisclosed)} 处降级步骤没有写进交付说明"
                    "——降级可以，瞒着不行")
    else:
        rep["warnings"].append("没有 PAPER_STATE.json，无法核对降级记录")

    # ---- 6. de-AI gates --------------------------------------------------
    scan = os.path.join(HERE, "prose_scan.py")
    if mfiles and os.path.isfile(scan):
        import subprocess
        p = subprocess.run([sys.executable, scan, ms, "--json",
                            os.path.join(root, "_selfcheck_deai.json")],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        rep["info"]["deai_exit"] = p.returncode
        try:
            d = json.loads(read(os.path.join(root, "_selfcheck_deai.json")))
            rep["info"]["deai_failed"] = d.get("failed", [])
            if d.get("failed"):
                rep["blocking"].append(
                    f"去 AI 痕迹判定项未过：{d['failed']}"
                    "（跑 prose_scan.py 看具体怎么改）")
        except (ValueError, OSError):
            pass
    # ---- 6b. data provenance --------------------------------------------
    # References being real is only half the problem: the numbers must come
    # from an actual run. Every data file carries a .prov.json recording the
    # model, its hash, the parameters and the seed - so hand-edited data, or
    # data from a superseded model, is caught rather than trusted.
    sim = os.path.join(HERE, "simulate.py")
    ddir = os.path.join(root, "data")
    data_files = []
    if os.path.isdir(ddir):
        for dp, _dn, fn in os.walk(ddir):
            data_files += [os.path.join(dp, f) for f in fn
                           if f.endswith((".csv", ".json"))
                           and not f.endswith(".prov.json")]
    if data_files and os.path.isfile(sim):
        import subprocess
        p = subprocess.run([sys.executable, sim, "provenance", "--data", ddir],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        rep["info"]["data_files"] = len(data_files)
        rep["info"]["provenance_exit"] = p.returncode
        if p.returncode != 0:
            lines = [l.strip() for l in p.stdout.splitlines()
                     if l.strip().startswith("[")]
            rep["blocking"].append(
                f"data/ 里有 {len(data_files)} 个数据文件，但溯源核查未通过 —— "
                "无法证明这些数字是真跑出来的。跑 "
                "`python scripts/simulate.py provenance --data data/` 看详情。"
                + (" 例如：" + "；".join(lines[:3]) if lines else ""))
        else:
            rep["info"]["provenance"] = "all data files verified"
    elif not data_files:
        rep["warnings"].append(
            "没有 data/ 数据文件 —— 如果是计算/仿真研究，"
            "必须用 `python scripts/simulate.py run` 真跑出来，"
            "不能手写数字")

    # ---- 7. citation verification report --------------------------------
    # A manuscript may only cite literature that was actually retrieved and
    # checked. litsearch.py writes the evidence; this insists that it exists
    # and that nothing inside it is unresolved.
    vr = os.path.join(root, "refs", "citation_verify.json")
    if not os.path.isfile(vr):
        rep["blocking"].append(
            "没有 refs/citation_verify.json —— 参考文献从未核验过。"
            "必须跑：python scripts/litsearch.py verify "
            "--refs manuscript/references.md --out refs/citation_verify.json")
    else:
        try:
            v = json.loads(read(vr))
        except ValueError:
            v = None
        if v is None:
            rep["blocking"].append("refs/citation_verify.json 不是合法 JSON")
        else:
            rep["info"]["citation_tally"] = v.get("tally", {})
            rep["info"]["citation_verified_at"] = v.get("verified_at", "")
            bad = [r for r in v.get("results", [])
                   if r.get("verdict") in ("NOT_FOUND", "RETRACTED", "UNVERIFIED")]
            if bad:
                rep["blocking"].append(
                    f"有 {len(bad)} 条参考文献没通过核验（查不到 / 已撤稿 / "
                    f"未能确认），这些绝对不能引用："
                    + "、".join(f"[{b.get('n')}]" for b in bad[:12]))
            retr = [r for r in v.get("results", [])
                    if r.get("verdict") == "RETRACTED"]
            if retr:
                rep["blocking"].append(
                    f"**引用了 {len(retr)} 篇已被撤稿的文献** —— "
                    "必须删除或替换，这类引用会直接导致拒稿")
            fix = [r for r in v.get("results", []) if r.get("verdict") == "FIX"]
            if fix:
                rep["warnings"].append(
                    f"{len(fix)} 条参考文献元数据与注册库不符（年份/作者/刊名/DOI），"
                    "按报告里的 fix 字段改正")

    return rep


def render(rep: dict) -> str:
    L = [f"# 自检报告 · {rep['dir']}", ""]
    info = rep.get("info", {})
    L.append(f"- 正文文件：{', '.join(info.get('manuscript_files') or ['无'])}")
    if info.get("numbers_in_prose"):
        L.append(f"- 正文数字 {info['numbers_in_prose']} 个，"
                 f"data/ 中数字 {info['numbers_in_data']} 个")
    if info.get("figures_cited"):
        L.append(f"- 引用图号 {info['figures_cited']}；"
                 f"已有图件 {info.get('figures_drawn') or '未找到'}")
    if info.get("refs_cited"):
        L.append(f"- 引用文献 {len(info['refs_cited'])} 条；"
                 f"文献表 {info.get('refs_listed', 0)} 条")
    L.append("")
    if rep["blocking"]:
        L.append(f"## ✗ 阻断问题（{len(rep['blocking'])} 条）")
        L.append("")
        for x in rep["blocking"]:
            L.append(f"- {x}")
        L.append("")
    if rep["warnings"]:
        L.append(f"## ! 需要人工看一眼（{len(rep['warnings'])} 条）")
        L.append("")
        for x in rep["warnings"]:
            L.append(f"- {x}")
        L.append("")
    if not rep["blocking"]:
        L.append("## ✓ 没有发现阻断问题")
        L.append("")
    L.append("> 说明：本报告只查**可自动核对的项**。它不能替代人工核对"
             "（例如数字是否算对、引用内容是否与原文一致）。"
             "自动通过不等于论文正确。")
    return "\n".join(L)


def main() -> int:
    _utf8()
    ap = argparse.ArgumentParser(prog="selfcheck")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--json", dest="json_out", default="")
    a = ap.parse_args()
    root = os.path.abspath(a.dir)
    if not os.path.isdir(root):
        print(f"[fail] 找不到目录 {root}", file=sys.stderr)
        return 1
    rep = audit(root)
    out = render(rep)
    print(out)
    with io.open(os.path.join(root, "SELFCHECK.md"), "w", encoding="utf-8") as fh:
        fh.write(out + "\n")
    if a.json_out:
        with io.open(a.json_out, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, ensure_ascii=False, indent=1)
        print(f"[ok] {a.json_out}")
    return 1 if rep["blocking"] else 0


if __name__ == "__main__":
    sys.exit(main())

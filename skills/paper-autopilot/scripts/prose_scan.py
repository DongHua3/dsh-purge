#!/usr/bin/env python3
"""去 AI 痕迹自测 · anti-AI-trace scan (v2).

Measures the signatures that distinguish machine-written academic prose from
human-written prose, then prints a concrete fix for each failure. Standard
library only.

    python prose_scan.py <file-or-folder> [...]
    python prose_scan.py manuscript/ --strict        # final-pass mode (step 19)
    python prose_scan.py manuscript/ --json report.json

Exit code 0 = all gates pass, 1 = at least one gate failed.

Threshold calibration
---------------------
Every gate is calibrated so that a manuscript that has already passed a human
reviewer audit does NOT fail. An earlier version of this script counted ordinary
scientific connectives (therefore, thus, in particular, for example) as AI
markers and reported 17 per 100 sentences on such a manuscript - all false
positives. The lists below are deliberately narrow.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import statistics
import sys

# --------------------------------------------------------------------------
# Gates. A metric is gated only when published evidence supports it AND it does
# not fire on legitimate scientific prose. See references/deai_protocol.md §3.1
# for the evidence grade of each feature.
# --------------------------------------------------------------------------
GATES = {
    # strongest single published signal (sentence-length uniformity)
    "sent_cv": (">", 0.40, "句子长度变异系数 (burstiness)"),
    "conn_rate": ("<", 2.0, "AI 式附加衔接词 (每 100 句)"),
    "rep_open": ("<=", 4, "同一句首最长重复次数"),
    "dup_sent": ("==", 0, "跨文件完全重复的整句"),
    "excess_vocab": ("<", 8.0, "LLM 高频词 (每 1000 词)"),
    "superficial_ing": ("<", 2.0, "句尾 -ing 附加评论 (每 100 段)"),
    "promo": ("<", 1.0, "宣传性词汇 (每 1000 词)"),
    "vague_attr": ("<", 1.5, "模糊归因 (每 100 段)"),
    "hedge_stack": ("==", 0, "叠加式模糊限定"),
}

# Advisory: real signals, but a global threshold would misjudge them, because
# the legitimate range depends on genre and on the target journal. Report the
# number; compare it against a baseline built from the target journal
# (deai_protocol.md §2), not against a fixed cut-off.
ADVISORY = {
    # NOTE: paragraph-length uniformity has NO published effect size behind it
    # (the one quantitative comparison found was n=4/group, p=0.974). Varying
    # paragraph length is still good style - it is simply not evidence of AI.
    "para_cv": (">", 0.45, "段落长度变异系数（证据不足，仅参考）"),
    "rule3_rate": ("<", 2.0, "规则三连 (每 100 段)（无同行评审频次研究）"),
    "nominal_rate": ("<", 8.0, "名词化词尾 (每 100 词)"),
    "passive_rate": ("<", 45.0, "被动语态占比 (%)"),
    "conn_open": ("<", 12.0, "以衔接词开头的段落 (%)"),
    "neg_par": ("<", 1.0, "否定式平行结构 (每 100 段)"),
}

# Reported with a number and NO verdict: genre- and length-dependent, or the
# human range is so wide that any threshold would be arbitrary.
INFORMATIONAL = [
    ("em_dash_per_1000w", "破折号密度 (次/千词)　[人类区间 0.33-17.12，不要一律清零]"),
    ("msttr", "词汇多样性 MSTTR (1000 词窗口)"),
    ("ttr", "裸 TTR（随篇幅下降，仅供同长度文本比较）"),
    ("sent_mean", "句均长 (词)"),
    ("sent_sd", "句长标准差 (词)　[参考：AI 7.08 vs 人类 14.01，另一语料]"),
    ("para_mean", "段落均长 (词)"),
    ("en_dash", "en dash (–) 数量"),
]

# --------------------------------------------------------------------------
# Word lists
# --------------------------------------------------------------------------
# Additive, throat-clearing connectors that mark machine-written prose.
# Ordinary academic connectives (therefore, thus, hence, in particular, for
# example, as a result, on the other hand) are normal scientific English and
# are deliberately NOT counted.
CONNECTORS = [
    "moreover", "furthermore", "additionally", "in addition", "besides",
    "notably", "importantly", "it is worth noting", "it should be noted",
    "it is important to note", "in conclusion", "in summary", "overall",
    "significantly", "crucially", "interestingly",
]

# Words statistically over-represented in LLM output. Drawn from the
# excess-vocabulary literature - principally Kobak, Gonzalez-Marquez, Horvat &
# Lause, "Delving into LLM-assisted writing in biomedical publications through
# excess vocabulary", Science Advances 11(27):eadt3813 (2025), arXiv:2406.07016,
# which analysed 14,448,711 PubMed abstracts; supplemented by Liang et al.
# (arXiv:2404.01268) and by field observation.
#
# Evidence note: "leverage", "testament" and "robust" are widely repeated as
# LLM markers but were NOT confirmed in either excess-vocabulary study. They are
# kept because they are also generic filler words worth removing on their own
# merits - but do not cite them as evidence of AI authorship.
EXCESS_VOCAB = [
    "delve", "delves", "delving", "underscore", "underscores", "underscoring",
    "showcase", "showcases", "showcasing", "surpass", "surpasses", "surpassing",
    "intricate", "intricacies", "pivotal", "realm", "leverage", "leveraging",
    "meticulous", "meticulously", "testament", "boast", "boasts", "boasting",
    "garner", "garnered", "comprehend", "comprehending", "aligns", "aligning",
    "advancements", "exemplifies", "exemplify", "interplay", "nuanced",
    "pioneering", "profound", "seamlessly", "seamless", "vibrant", "encompass",
    "encompasses", "encompassing", "groundbreaking", "unparalleled",
    "multifaceted", "holistic", "synergy", "synergies", "myriad", "plethora",
    "utilize", "utilizing", "utilization", "endeavor", "paramount",
    "commendable", "tapestry", "beacon", "landscape of", "navigate",
    "navigating", "foster", "fostering", "facilitate", "facilitating",
    "crucial", "robustly", "notably", "importantly", "significantly",
    "cutting-edge", "state-of-the-art", "in today's", "ever-evolving",
    "rapidly evolving", "plays a vital role", "plays a crucial role",
    "sheds light", "shed light", "paves the way", "holds promise",
    "opens new avenues", "a growing body of", "it is worth noting",
]

# Promotional / inflated language. Same source family; stricter than the list
# above because these are unambiguously inappropriate in a research paper.
PROMO = [
    "groundbreaking", "revolutionary", "game-changing", "game changer",
    "paradigm shift", "unprecedented", "world-class", "state-of-the-art",
    "cutting-edge", "breakthrough", "remarkable", "stunning", "exciting",
    "powerful", "elegant solution", "seamless", "effortless", "best-in-class",
]

# Vague attribution - claims with no traceable source.
VAGUE_ATTR = [
    "studies have shown", "research has shown", "researchers have found",
    "it is widely believed", "it is generally accepted", "many researchers",
    "several studies", "numerous studies", "some studies", "it has been reported",
    "experts agree", "it is well known", "it is commonly known",
    "there is a growing consensus", "evidence suggests",
]

# Stacked hedges - two or more in one clause.
HEDGES = ["may", "might", "could", "possibly", "potentially", "perhaps",
          "arguably", "presumably", "apparently", "somewhat", "rather",
          "fairly", "relatively", "seemingly", "likely", "probably"]

# Sentence-final "-ing" clause that adds commentary rather than content.
SUPERFICIAL_ING = re.compile(
    r",\s+(?:thereby\s+|thus\s+)?(?:highlight|underscor|emphasiz|emphasiz|"
    r"demonstrat|illustrat|showcas|reflect|indicat|suggest|reveal|confirm|"
    r"pav|foster|facilitat|enabl|allow|provid)(?:ing|ing)\b[^.]{4,80}\.",
    re.I)

NEG_PAR = re.compile(
    r"\b(?:not only\b[^.]{0,80}\bbut also\b|it is not (?:just|merely|only)\b"
    r"[^.]{0,80}\bit is\b|rather than (?:merely|just|simply)\b)", re.I)

RULE3 = re.compile(
    r"\b([\w\-]+(?:\s+[\w\-]+){0,3}),\s+([\w\-]+(?:\s+[\w\-]+){0,3}),?\s+and\s+"
    r"([\w\-]+(?:\s+[\w\-]+){0,3})\b")

NOMINAL = re.compile(
    r"\b\w{5,}(?:tion|sion|ment|ance|ence|ency|ancy|ility|ness|ization|isation)\b",
    re.I)

PASSIVE = re.compile(
    r"\b(?:is|are|was|were|be|been|being|has been|have been|had been)\s+"
    r"(?:\w+ly\s+)?(\w+(?:ed|en))\b", re.I)

RE_HEAD = re.compile(r"^\s{0,3}#{1,6}\s")
RE_TABLE = re.compile(r"^\s*\|")
RE_CODE = re.compile(r"^\s*```")
RE_FIG = re.compile(r"^\s*(图|表|Figure|Table|Fig\.)\s*\d")
RE_EQ = re.compile(r"^\s*\$\$|^\s*\\\[|^\s*=+\s*$")
CJK = re.compile(r"[\u4e00-\u9fff]")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")


def _stdout_utf8() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def load(paths: list[str]) -> dict[str, str]:
    files: dict[str, str] = {}
    for p in paths:
        if os.path.isdir(p):
            for dirpath, _dirs, names in os.walk(p):
                for n in sorted(names):
                    if n.lower().endswith((".md", ".txt", ".markdown")):
                        fp = os.path.join(dirpath, n)
                        with io.open(fp, encoding="utf-8", errors="replace") as fh:
                            files[fp] = fh.read()
        elif os.path.isfile(p):
            with io.open(p, encoding="utf-8", errors="replace") as fh:
                files[p] = fh.read()
        else:
            print(f"[warn] 找不到 {p}", file=sys.stderr)
    return files


def prose_only(text: str) -> list[str]:
    out, in_code = [], False
    for raw in text.splitlines():
        line = raw.rstrip()
        if RE_CODE.match(line):
            in_code = not in_code
            continue
        if in_code:
            continue
        if (not line.strip() or RE_HEAD.match(line) or RE_TABLE.match(line)
                or RE_FIG.match(line) or RE_EQ.match(line) or LIST_ITEM.match(line)):
            out.append("")
            continue
        out.append(line)
    return out


def paragraphs(lines: list[str]) -> list[str]:
    paras, cur = [], []
    for line in lines:
        if line.strip():
            cur.append(line.strip())
        elif cur:
            paras.append(" ".join(cur))
            cur = []
    if cur:
        paras.append(" ".join(cur))
    return [p for p in paras if len(p) > 40]


def sentences(paras: list[str]) -> list[str]:
    out = []
    for p in paras:
        for s in re.split(r"(?<=[。！？；!?;])\s*|(?<=[.])\s+(?=[A-Z(])", p):
            s = s.strip()
            if len(s) > 15:
                out.append(s)
    return out


def length(s: str) -> int:
    if len(CJK.findall(s)) > len(s) * 0.25:
        return len(CJK.findall(s))
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-]*", s))


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'\-]*", text.lower())


def cv(vals: list[int]) -> float:
    if len(vals) < 3:
        return 0.0
    m = statistics.fmean(vals)
    return statistics.pstdev(vals) / m if m else 0.0


def _count_phrases(low: str, phrases: list[str]) -> tuple[int, dict[str, int]]:
    hits = {}
    total = 0
    for ph in phrases:
        n = low.count(ph)
        if n:
            hits[ph] = n
            total += n
    return total, hits


def analyse(files: dict[str, str]) -> dict:
    all_paras, all_sents, per_file = [], [], {}
    for path, text in files.items():
        ps = paragraphs(prose_only(text))
        ss = sentences(ps)
        per_file[os.path.basename(path)] = {
            "paragraphs": len(ps), "sentences": len(ss),
            "words": sum(length(p) for p in ps)}
        all_paras += ps
        all_sents += ss

    body = "\n".join(all_paras)
    low = body.lower()
    n_words = max(1, len(words(body)))
    n_paras = max(1, len(all_paras))
    n_sents = max(1, len(all_sents))

    em = body.count("\u2014")

    r3 = sum(1 for s in all_sents if RULE3.search(s))
    conn, conn_hits = _count_phrases(low, CONNECTORS)
    exc, exc_hits = _count_phrases(low, EXCESS_VOCAB)
    promo, promo_hits = _count_phrases(low, PROMO)
    vague, vague_hits = _count_phrases(low, VAGUE_ATTR)
    ing = len(SUPERFICIAL_ING.findall(body))
    negp = len(NEG_PAR.findall(body))
    nominal = len(NOMINAL.findall(body))
    passive = len(PASSIVE.findall(body))

    hedge_stack = 0
    hedge_examples = []
    for s in all_sents:
        sl = s.lower()
        present = [h for h in HEDGES
                   if re.search(rf"\b{re.escape(h)}\b", sl)]
        if len(present) >= 3:
            hedge_stack += 1
            if len(hedge_examples) < 5:
                hedge_examples.append((s[:110], present))

    opens: dict[str, int] = {}
    for s in all_sents:
        k = " ".join(s.split()[:3]) if not CJK.search(s) else s[:6]
        opens[k] = opens.get(k, 0) + 1
    top_open = max(opens.items(), key=lambda kv: kv[1]) if opens else ("", 0)

    conn_open = sum(1 for p in all_paras
                    if any(p.lower().lstrip().startswith(c) for c in CONNECTORS))
    conn_open_pct = 100.0 * conn_open / n_paras

    wl = words(body)
    ttr = (len(set(wl)) / len(wl)) if wl else 0.0
    # Plain TTR falls as a text grows, so it is not comparable across papers.
    # MSTTR (mean segmental TTR over 1000-word windows) is length-robust and is
    # the number to quote.
    win = 1000
    if len(wl) >= win:
        segs = [wl[i:i + win] for i in range(0, len(wl) - win + 1, win)]
        msttr = statistics.fmean(len(set(s)) / win for s in segs)
    else:
        msttr = ttr

    seen: dict[str, str] = {}
    dups: list[dict] = []
    for path, text in files.items():
        for s in sentences(paragraphs(prose_only(text))):
            key = re.sub(r"\s+", " ", s.strip().lower())
            if len(key) < 60:
                continue
            if key in seen and seen[key] != path:
                dups.append({"sentence": s.strip()[:120],
                             "in": [os.path.basename(seen[key]),
                                    os.path.basename(path)]})
            else:
                seen.setdefault(key, path)

    sents_sorted = sorted(all_sents, key=len, reverse=True)
    sent_lens = [length(s) for s in all_sents]
    metrics = {
        "files": len(files),
        "paragraphs": len(all_paras),
        "sentences": len(all_sents),
        "words": n_words,
        "para_cv": round(cv([length(p) for p in all_paras]), 3),
        "sent_cv": round(cv(sent_lens), 3),
        "sent_sd": round(statistics.pstdev(sent_lens), 2) if len(sent_lens) > 2 else 0.0,
        "para_mean": round(statistics.fmean([length(p) for p in all_paras]), 1) if all_paras else 0,
        "sent_mean": round(statistics.fmean(sent_lens), 1) if sent_lens else 0,
        "em_dash": em,
        "em_dash_per_1000w": round(1000.0 * em / n_words, 2),
        "en_dash": body.count("\u2013"),
        "rule3_count": r3,
        "rule3_rate": round(100.0 * r3 / n_paras, 2),
        "connector_count": conn,
        "connector_rate": round(100.0 * conn / n_sents, 2),
        "connector_hits": conn_hits,
        "excess_vocab_count": exc,
        "excess_vocab": round(1000.0 * exc / n_words, 2),
        "excess_hits": dict(sorted(exc_hits.items(), key=lambda kv: -kv[1])[:20]),
        "promo_count": promo,
        "promo": round(1000.0 * promo / n_words, 2),
        "promo_hits": promo_hits,
        "vague_attr_count": vague,
        "vague_attr": round(100.0 * vague / n_paras, 2),
        "vague_hits": vague_hits,
        "superficial_ing_count": ing,
        "superficial_ing": round(100.0 * ing / n_paras, 2),
        "hedge_stack_count": hedge_stack,
        "hedge_stack": hedge_stack,
        "hedge_examples": hedge_examples,
        "negative_parallelism": negp,
        "neg_par": round(100.0 * negp / n_paras, 2),
        "nominal_count": nominal,
        "nominal_rate": round(100.0 * nominal / n_words, 2),
        "passive_count": passive,
        "passive_rate": round(100.0 * passive / max(1, len(all_sents)), 2),
        "conn_open_pct": round(conn_open_pct, 2),
        "conn_open": round(conn_open_pct, 2),
        "ttr": round(ttr, 3),
        "msttr": round(msttr, 3),
        "repeat_opening_max": top_open[1],
        "repeat_opening_key": top_open[0],
        "dup_sentences": len(dups),
        "dup_examples": dups[:5],
        "longest_sentence": sents_sorted[0][:160] if sents_sorted else "",
        "per_file": per_file,
    }
    return metrics


def _test(v, op: str, thr) -> bool:
    if op == ">":
        return v > thr
    if op == "<":
        return v < thr
    if op == "==":
        return v == thr
    return v <= thr


# Gate key -> metric key, where the two names differ. Anything not listed here
# must appear in the metrics dict under its own name; _rows() refuses to run
# otherwise, so a typo can never silently report 0 (which would read as PASS).
ALIAS = {
    "conn_rate": "connector_rate",
    "rep_open": "repeat_opening_max",
    "dup_sent": "dup_sentences",
}


def _rows(m: dict, table: dict, attr: str) -> list[tuple]:
    out = []
    for key, (op, thr, label) in table.items():
        mk = ALIAS.get(key, key)
        if mk not in m:
            raise KeyError(
                f"gate '{key}' maps to metric '{mk}', which analyse() does not "
                f"produce - fix the name rather than letting it read as 0/PASS")
        v = m[mk]
        out.append((key, f"{v} {'>' if op == '>' else '<' if op == '<' else '=='} {thr}",
                    label, _test(v, op, thr)))
    return out


FIXES = {
    "para_cv": "把长段拆开、把相邻短段合并，让段落长短交错",
    "sent_cv": "长句断成短句；偶尔用短判断句独立成段",
    "em_dash": "断句，不要用破折号串联（A——也就是 B——导致 C 改成两句话）",
    "conn_rate": "直接删掉 moreover / furthermore / additionally 这类词，让句子自己承接",
    "rep_open": "换主语或换语序；同一句式不要连续三段都用",
    "dup_sent": "讨论里的重复句改写或删除；跨节不要复制粘贴整句",
    "excess_vocab": "换成领域内的具体动词或名词（delve into → 直接说「测量/推导/比较」）",
    "superficial_ing": "把句尾 -ing 评论改成独立事实句，或直接删（它通常没带来新信息）",
    "promo": "删掉宣传腔；把 groundbreaking 换成具体的量（提升了多少、在什么条件下）",
    "vague_attr": "替换成具体引用（作者+年份+文献号），查不到就删掉这句话",
    "hedge_stack": "一句话里最多留一个限定词；may potentially 之类直接删一个",
    "rule3_rate": "删掉最弱一项留两项，或拆成两句各说一件事",
    "nominal_rate": "把 -tion/-ment 名词化还原成动词（perform an evaluation of → evaluate）",
    "passive_rate": "方法可保留被动，结果与讨论改主动",
    "conn_open": "段落不要用衔接词开头；用上一段的内容做主语",
    "ttr": "换掉重复用词，用同义的专业表达",
    "neg_par": "「不是 X 而是 Y」这种结构连用会像模板，改成直接陈述 Y",
}


def main() -> int:
    _stdout_utf8()
    ap = argparse.ArgumentParser(prog="prose_scan")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json", dest="json_out", default="")
    ap.add_argument("--strict", action="store_true",
                    help="终稿模式：额外把参考项也当作提醒重点列出")
    ap.add_argument("--top", type=int, default=20, help="列出前 N 个高频 AI 词")
    ap.add_argument("--baseline", default="",
                    help="目标期刊基线 JSON（由本脚本对期刊文章跑一次得到），"
                         "给出后会把本稿与之对照")
    ap.add_argument("--save-baseline", action="store_true",
                    help="把本次结果存成基线（对期刊文章目录跑时用）")
    a = ap.parse_args()

    files = load(a.paths)
    if not files:
        print("[fail] 没有可读的 .md/.txt 文件", file=sys.stderr)
        return 1
    m = analyse(files)
    rows = _rows(m, GATES, "gates")
    adv = _rows(m, ADVISORY, "advisory")
    failed = [r[0] for r in rows if not r[3]]

    print("去 AI 痕迹自测" + ("（终稿模式）" if a.strict else ""))
    print()
    print(f"文件 {m['files']} 个 · 段 {m['paragraphs']} · 句 {m['sentences']} · 词 {m['words']}")
    print(f"段落均长 {m['para_mean']} 词 · 句均长 {m['sent_mean']} 词\n")

    print("## 判定项")
    print()
    print("| 指标 | 实测 | 门槛 | 结果 |")
    print("|---|---|---|---|")
    for _k, val, label, ok in rows:
        print(f"| {label} | {val} | {'PASS' if ok else '**FAIL**'} |")
    print()

    print("## 参考项（不计入判定，但终稿值得看一眼）")
    print()
    print("| 指标 | 实测 | 参考门槛 | 状态 |")
    print("|---|---|---|---|")
    for _k, val, label, ok in adv:
        print(f"| {label} | {val} | {'OK' if ok else '偏高'} |")
    print()

    print("## 观察项（只报数，不判定——随文体与篇幅变化，和自己以前的稿子比）")
    print()
    for k, label in INFORMATIONAL:
        print(f"  {label}：{m.get(k, 'n/a')}")
    print()

    if m["excess_hits"]:
        print(f"## LLM 高频词命中（共 {m['excess_vocab_count']} 次）")
        print()
        for w, n in list(m["excess_hits"].items())[:a.top]:
            print(f"  {w} ×{n}")
        print()
    if m["promo_hits"]:
        print(f"## 宣传性词汇（共 {m['promo_count']} 次）")
        print()
        for w, n in m["promo_hits"].items():
            print(f"  {w} ×{n}")
        print()
    if m["vague_hits"]:
        print(f"## 模糊归因（共 {m['vague_attr_count']} 次）")
        print()
        for w, n in m["vague_hits"].items():
            print(f"  {w} ×{n}")
        print()
    if m["hedge_examples"]:
        print(f"## 叠加式模糊限定（{m['hedge_stack_count']} 处）")
        print()
        for s, hs in m["hedge_examples"]:
            print(f"  [{'+'.join(hs)}] {s}")
        print()
    if m["dup_examples"]:
        print("## 跨文件重复整句")
        print()
        for d in m["dup_examples"]:
            print(f"  {d['in'][0]} ↔ {d['in'][1]}：{d['sentence']}")
        print()

    print(f"最高频句首：「{m['repeat_opening_key']}」×{m['repeat_opening_max']}")
    print(f"以衔接词开头的段落：{m['conn_open_pct']}% · 被动语态：{m['passive_rate']}%")
    print()

    if a.baseline:
        try:
            with io.open(a.baseline, encoding="utf-8") as fh:
                base = json.load(fh)
            keys = [k for k in ("sent_cv", "para_cv", "sent_mean", "sent_sd",
                                "connector_rate", "em_dash_per_1000w", "msttr",
                                "passive_rate", "nominal_rate", "ttr")]
            print(f"## 与期刊基线对照（{os.path.basename(a.baseline)}）")
            print()
            print("| 指标 | 本稿 | 期刊基线 | 偏离 |")
            print("|---|---|---|---|")
            for k in keys:
                if k not in base:
                    continue
                b, v = base[k], m.get(k)
                if not isinstance(b, (int, float)) or not isinstance(v, (int, float)):
                    continue
                if b == 0:
                    dev = "n/a"
                else:
                    pct = 100.0 * (v - b) / b
                    dev = f"{pct:+.1f}%"
                    if abs(pct) > 50:
                        dev += "  ← 明显偏离"
                print(f"| {k} | {v} | {b} | {dev} |")
            print()
        except Exception as e:  # noqa: BLE001
            print(f"[warn] 读不到基线文件 {a.baseline}：{type(e).__name__}: {e}\n")

    if failed:
        print("## 要改的地方（按这个动作改，不要只写「再润色一遍」）")
        print()
        for k in failed:
            print(f"  - **{dict((r[0], r[2]) for r in rows)[k]}** → {FIXES.get(k, '')}")
        print()
    print(f"结果：{'全部通过' if not failed else '未通过 → ' + ', '.join(failed)}")

    if a.json_out or a.save_baseline:
        m["gates"] = [{"key": k, "value": v, "label": l, "pass": ok}
                      for k, v, l, ok in rows]
        m["advisory"] = [{"key": k, "value": v, "label": l, "ok": ok}
                         for k, v, l, ok in adv]
        m["failed"] = failed
        m["all_pass"] = not failed
        target = a.json_out or "journal_baseline.json"
        with io.open(target, "w", encoding="utf-8") as fh:
            json.dump(m, fh, ensure_ascii=False, indent=1)
        print(f"[ok] {'期刊基线' if a.save_baseline else 'JSON 报告'}：{target}")
        if a.save_baseline:
            print(f"     用它对照自己的稿子：--baseline {target}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

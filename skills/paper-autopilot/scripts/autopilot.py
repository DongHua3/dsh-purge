#!/usr/bin/env python3
"""autopilot — drives paper-pipeline without any human input.

The agent's whole job each turn is three commands:

    python autopilot.py start --dir <folder> --direction "..."   # once
    python autopilot.py next  --dir <folder>                     # what to do now
    python autopilot.py done  --dir <folder>                     # I did it

`next` prints a complete work order: the goal, the exact artifact paths that
must exist when the step is finished, the pass criteria, and where to find the
bare-tool procedure. `done` refuses to advance if the declared artifacts are
missing or empty — that is what stops the pipeline from quietly skipping work.

Nothing here ever asks the user a question. Anything that would normally be a
question becomes a recorded decision (see `decide`) or a recorded degradation
(see `skip`).

Standard library only; Python 3.8+.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from datetime import datetime, timezone

STATE = "PAPER_STATE.json"
SCHEMA = "paper-pipeline/1.2"

# --------------------------------------------------------------------------
# steps: id, name, group, required artifacts (relative paths; a trailing "/"
# means "this directory must contain at least one file"), gate summary
# --------------------------------------------------------------------------
S = [
    ("00", "总控进度判断", "项目与检索", [], "已确定当前步"),
    ("01", "项目初始化", "项目与检索",
     ["01_项目初始化/BRIEF.md"], "目标刊、篇幅、作者占位符已写死"),
    ("02", "检索式生成", "项目与检索",
     ["02_检索式生成/SEARCH_STRINGS.md"], "检索式可执行且返回非零结果"),
    ("03", "检索与导出", "项目与检索",
     ["03_检索与导出/SEARCH_LOG.md", "refs/"], "导出条数与日志一致"),
    ("04", "选题与空白识别", "项目与检索",
     ["04_选题与空白识别/TOPIC.md"], "无「已有人做过」的硬伤"),
    ("05", "对标库深度学习", "文献与证据",
     ["05_对标库深度学习/BENCHMARK.md"], "≥5 篇，每篇写明借鉴点"),
    ("06", "文献筛选分类", "文献与证据",
     ["06_文献筛选分类/SELECTION.csv"], "每条有纳入/排除理由"),
    ("07", "导入引用库取全文", "文献与证据",
     ["07_导入引用库取全文/PDF_STATUS.md", "refs/"], "缺失项有清单"),
    ("08", "文献精读", "文献与证据",
     ["08_文献精读/NOTES/"], "每篇留下可引用条目"),
    ("09", "论文框架搭建", "框架与写作",
     ["09_论文框架搭建/OUTLINE.md"], "到三级标题，每节标图表号"),
    ("10", "图表制作与引用", "框架与写作",
     ["10_图表制作与引用/FIGPLAN.md", "figures/"], "图号连续、引用顺序正确"),
    ("11", "摘要与引言", "框架与写作",
     ["manuscript/00_abstract.md", "manuscript/01_intro.md"], "引言每段有出处"),    ("12", "方法与结果", "框架与写作",
     ["manuscript/02_methods.md", "manuscript/03_results.md",
      "data/", "12_方法与结果/model_verify.json"],
     "每个数字能追到 data/ 里的源文件；数据带溯源；模型自检通过"),
    ("13", "讨论与结论", "框架与写作",
     ["manuscript/04_discussion.md", "manuscript/05_conclusions.md"],
     "不与结果整句重复；局限逐条列明"),
    ("14", "目标期刊选择", "投稿与返修",
     ["14_目标期刊选择/JOURNALS.csv"], "有来源；已排除掠夺性刊"),
    ("15", "目标期刊格式学习", "投稿与返修",
     ["15_目标期刊格式学习/FORMAT_CHECKLIST.md"], "逐条对照过"),
    ("16", "润色与语言打磨", "投稿与返修",
     ["16_润色与语言打磨/scan_report.json"], "去 AI 痕迹判定项全过"),
    ("17", "图片版权", "投稿与返修",
     ["17_图片版权/RIGHTS.md"], "每张图来源与版权状态有记录"),
    ("18", "Cover Letter", "投稿与返修",
     ["18_CoverLetter/Cover_Letter.md"], "每个卖点正文里找得到"),
    ("19", "终稿去 AI 痕迹与合规声明", "投稿与返修",
     ["19_去AI痕迹/scan_after.json", "19_去AI痕迹/statement.md",
      "19_去AI痕迹/diff_check.md"],
     "判定项全过；数字/引用/图号对得上；声明已写"),
    ("20", "投稿前总检", "投稿与返修",
     ["20_投稿前总检/PRESUBMIT_CHECK.md", "submission/",
      "refs/citation_verify.json"],
     "引用与数字零上下文复核通过；所有引用已核验（无查不到/无撤稿）"),
    ("21", "返修与回复", "投稿与返修",
     ["21_返修/Response_Letter.md", "21_返修/CHANGES.md"],
     "每条意见有回复与改动位置"),
]
IDS = [s[0] for s in S]
NAME = {s[0]: s[1] for s in S}
GROUP = {s[0]: s[2] for s in S}
ARTS = {s[0]: s[3] for s in S}
GATE = {s[0]: s[4] for s in S}


def _check_step_table() -> list[str]:
    """Validate the step table itself before anything depends on it.

    A duplicate id makes IDS.index() always return the first occurrence, so the
    pipeline silently stops advancing and loops on the same step forever. That
    happened once; this makes it impossible to ship again.
    """
    problems = []
    expected = [f"{i:02d}" for i in range(len(S))]
    if IDS != expected:
        dupes = sorted({x for x in IDS if IDS.count(x) > 1})
        problems.append(
            f"步骤编号必须是连续的 00..{len(S) - 1:02d}；"
            + (f"重复的编号：{dupes}；" if dupes else "")
            + f"实际得到 {IDS}")
    if not S:
        problems.append("步骤表是空的")
    for sid, name, _g, arts, _gate in S:
        if not arts and sid != "00":
            problems.append(f"第 {sid} 步没有声明任何必需产出，done 无法核查")
        for a in arts:
            if not re.match(r"^[0-9]{2}_|^refs/|^manuscript/|^figures/|^data/|"
                            r"^submission/|^journal_papers/", a):
                problems.append(f"第 {sid} 步的产出路径不像流水线目录：{a}")
    return problems

# --------------------------------------------------------------------------
# intake inference: pick a default venue / type / length from the direction so
# the pipeline never has to stop and ask.
# --------------------------------------------------------------------------
VENUES = [
    # (keywords, venue, publisher, quartile, oa_note, length_words,
    #  figures, refs, style_note)
    (("magnetorheological", "mre", "smart material", "adaptive structure"),
     "Smart Materials and Structures", "IOP", "Q2",
     "订阅制，可免费发表", "7000", "10", "40",
     "IOP 编号引用；方法要写到别人能复现"),
    (("vibration", "rotor", "absorber", "damper", "dynamic", "modal"),
     "Mechanical Systems and Signal Processing", "Elsevier", "Q1",
     "订阅制，可免费发表", "9000", "12", "50",
     "Elsevier 编号引用；验证与不确定度必须成节"),
    (("vibration", "rotor", "bearing", "absorber", "damper"),
     "Journal of Sound and Vibration", "Elsevier", "Q1/Q2",
     "订阅制，可免费发表", "8000", "12", "45",
     "重物理机理与解析对照"),
    (("machine tool", "spindle", "manufacturing", "machining", "additive"),
     "The International Journal of Advanced Manufacturing Technology",
     "Springer", "Q2", "订阅制，可免费发表", "7000", "10", "40",
     "Springer 编号引用；强调工艺可用性"),
    (("control", "anfis", "neural", "fuzzy", "adaptive"),
     "Journal of Vibration and Control", "SAGE", "Q2",
     "订阅制，可免费发表", "8000", "10", "45",
     "SAGE 编号引用；控制律要收敛性论证"),
    (("thermal", "heat transfer", "conjugate"),
     "International Journal of Thermal Sciences", "Elsevier", "Q1/Q2",
     "订阅制，可免费发表", "8000", "10", "45",
     "重实验或高保真数值验证"),
    (("fatigue", "fracture", "stress", "strain"),
     "International Journal of Fatigue", "Elsevier", "Q1",
     "订阅制，可免费发表", "8000", "10", "45",
     "重统计与分散性处理"),
    (("review", "survey", "overview"),
     "Mechanical Systems and Signal Processing", "Elsevier", "Q1",
     "订阅制，可免费发表", "12000", "14", "120",
     "综述：检索策略必须可复现"),
]
FALLBACK_VENUE = (
    "The International Journal of Advanced Manufacturing Technology",
    "Springer", "Q2", "订阅制，可免费发表", "7000", "10", "40",
    "未匹配到更具体的刊，落地到工程刊通用口径")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utf8() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def _die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def _path(root: str, rel: str) -> str:
    return os.path.join(root, rel.replace("/", os.sep))


def _load(root: str) -> dict:
    p = os.path.join(root, STATE)
    if not os.path.isfile(p):
        _die(f"{p} 不存在。先跑：autopilot.py start --dir \"{root}\" "
             f"--direction \"<方向>\"")
    with io.open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _save(root: str, st: dict) -> None:
    st["updated_at"] = _now()
    with io.open(os.path.join(root, STATE), "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False, indent=1)
    with io.open(os.path.join(root, "PIPELINE.md"), "w", encoding="utf-8") as fh:
        fh.write(_human(st))
    with io.open(os.path.join(root, "DECISIONS.md"), "w", encoding="utf-8") as fh:
        fh.write(_decisions(st))


def _human(st: dict) -> str:
    b = st.get("brief") or {}
    L = [f"# 论文流水线 · {st.get('title') or '(未命名)'}", ""]
    L.append(f"- **方向**：{st.get('direction') or '(未填)'}")
    for k, lab in (("type", "论文类型"), ("venue", "目标刊"),
                   ("quartile", "分区"), ("length_limit", "篇幅"),
                   ("figure_limit", "图表"), ("ref_limit", "参考文献"),
                   ("has_experiment", "实验数据"), ("authors", "作者")):
        if b.get(k):
            L.append(f"- **{lab}**：{b[k]}")
    L.append(f"- **模式**：{st.get('mode', 'autopilot（全自动，不询问）')}")
    L.append(f"- **更新**：{st.get('updated_at', '')}")
    L.append("")
    done = st.get("completed", [])
    cur = st.get("current")
    L.append(f"**进度 {len(done)}/{len(S)}**　当前："
             + (f"第 {cur} 步 · {NAME.get(cur, '')}" if cur else "全部完成"))
    L.append("")
    L.append("| 步 | 名称 | 组 | 状态 | 闸门 | 产出 |")
    L.append("|---:|---|---|---|---|---|")
    for sid, name, group, _a, _g in S:
        rec = (st.get("steps") or {}).get(sid) or {}
        if sid in done and rec.get("degraded"):
            status = "降级完成"
        elif sid in done:
            status = "已完成"
        elif sid == cur:
            status = "进行中"
        else:
            status = "未开始"
        arts = rec.get("artifacts") or []
        a = "、".join(f"`{x}`" for x in arts[:2]) + ("…" if len(arts) > 2 else "")
        L.append(f"| {sid} | {name} | {group} | {status} | "
                 f"{rec.get('gate', '')} | {a} |")
    L.append("")
    log = st.get("log") or []
    if log:
        L.append("## 日志")
        L.append("")
        for e in log[-40:]:
            L.append(f"- `{e.get('at','')}` **{e.get('event','')}** "
                     f"{e.get('step','')} {e.get('note','')}".rstrip())
        L.append("")
    return "\n".join(L)


def _decisions(st: dict) -> str:
    L = ["# 自动决策记录 · DECISIONS", "",
         "流水线在运行中自己做的决定都记在这里。",
         "**用户不需要在开始时回答任何问题**；想改哪一条，直接改这个文件，"
         "流水线下一轮会读到。", ""]
    ds = st.get("decisions") or []
    if not ds:
        L.append("（还没有记录）")
    for i, d in enumerate(ds, 1):
        L.append(f"## D{i:02d} · {d.get('q','')}")
        L.append("")
        L.append(f"- **选择**：{d.get('choice','')}")
        L.append(f"- **理由**：{d.get('why','')}")
        L.append(f"- **怎么改**：{d.get('how_to_change','改这一行即可，流水线下一轮会读到')}")
        L.append(f"- **时间/步骤**：{d.get('at','')} · 第 {d.get('step','')} 步")
        L.append("")
    return "\n".join(L)


def _infer_venue(direction: str) -> tuple:
    low = direction.lower()
    best, score = None, 0
    for kws, *rest in VENUES:
        s = sum(1 for k in kws if k in low)
        if s > score:
            best, score = rest, s
    if best is None:
        best = list(FALLBACK_VENUE)
        score = 0
    return tuple(best), score


def _check_artifacts(root: str, rels: list[str]) -> list[str]:
    """Return the list of declared artifacts that are missing or empty."""
    bad = []
    for rel in rels:
        p = _path(root, rel)
        if rel.endswith("/"):
            if not os.path.isdir(p):
                bad.append(rel + " (目录不存在)")
                continue
            files = [f for _d, _s, fs in os.walk(p) for f in fs]
            if not files:
                bad.append(rel + " (目录为空)")
        else:
            if not os.path.isfile(p):
                bad.append(rel + " (文件不存在)")
            elif os.path.getsize(p) < 40:
                bad.append(rel + f" (只有 {os.path.getsize(p)} 字节，基本是空文件)")
    return bad


# ----------------------------------------------------------------- commands
def cmd_start(a) -> int:
    root = os.path.abspath(a.dir)
    os.makedirs(root, exist_ok=True)
    sp = os.path.join(root, STATE)
    if os.path.isfile(sp) and not a.force:
        _die(f"{sp} 已存在。要重来加 --force。")
    if not (a.direction or "").strip():
        _die("必须给 --direction。全自动模式下这是唯一必需的输入。")

    (venue, pub, quart, oa, length, figs, refs, style), score = \
        _infer_venue(a.direction)
    direction = a.direction.strip()
    title = a.title or direction[:40]

    steps = {}
    log = [{"at": _now(), "event": "start", "step": "00",
            "note": f"方向：{direction}"}]
    decisions = [
        {"at": _now(), "step": "01", "q": "投哪个刊？",
         "choice": f"{venue}（{pub}，{quart}）",
         "why": (f"从方向关键词匹配到该刊（匹配度 {score}）；{oa}。"
                 "Q4 刊多为全 OA 且收费，订阅制 Q1–Q3 刊通常免费，故选此档。"),
         "how_to_change": "改这里，或直接改 14_目标期刊选择/JOURNALS.csv"},
        {"at": _now(), "step": "01", "q": "论文类型？",
         "choice": "research article",
         "why": "方向描述的是具体工作而非领域综述。",
         "how_to_change": "改为 review 会让第 09–13 步切换成综述骨架"},
        {"at": _now(), "step": "01", "q": "篇幅与图表上限？",
         "choice": f"{length} words / {figs} figures / {refs} refs",
         "why": f"取 {venue} 的常见量级。",
         "how_to_change": "改这里"},
        {"at": _now(), "step": "01", "q": "有没有真实实验数据？",
         "choice": a.has_experiment or "simulation-only",
         "why": ("用户未声明有实验数据，按计算/仿真研究处理，"
                 "并在摘要与范围声明中写明。"),
         "how_to_change": "有数据就把这里改成 yes，第 12 步会加确认小节"},
        {"at": _now(), "step": "01", "q": "作者与单位？",
         "choice": a.authors or "占位符（待用户补真实作者/单位/邮箱/ORCID）",
         "why": "全自动模式不臆造真实人物信息。",
         "how_to_change": "投稿前必须替换，第 20 步会提醒"},
    ]

    for sid, name, _g, _arts, _gate in S:
        os.makedirs(os.path.join(root, f"{sid}_{name}"), exist_ok=True)
    for extra in ("refs", "data", "figures", "manuscript", "submission",
                  "journal_papers"):
        os.makedirs(os.path.join(root, extra), exist_ok=True)

    st = {
        "schema": SCHEMA, "title": title, "direction": direction,
        "mode": "autopilot", "created_at": _now(), "updated_at": _now(),
        "current": "01", "completed": ["00"], "steps": steps,
        "decisions": decisions, "log": log,
        "brief": {
            "type": "research article", "venue": venue, "publisher": pub,
            "quartile": quart, "oa_note": oa, "length_limit": f"{length} words",
            "figure_limit": f"{figs} figures", "ref_limit": f"{refs} refs",
            "style_note": style,
            "has_experiment": a.has_experiment or "simulation-only",
            "authors": a.authors or
                       "占位符（待用户补真实作者/单位/邮箱/ORCID）",
        },
    }
    _save(root, st)
    print(f"[ok] 项目已建立：{root}")
    print(f"[ok] 自动定下目标刊：{venue}（{pub}，{quart}，{oa}）")
    print(f"[ok] 篇幅 {length} words · {figs} figures · {refs} refs")
    print(f"[ok] 自动决策 {len(decisions)} 条 → DECISIONS.md")
    print("\n下一步：python autopilot.py next --dir \"%s\"" % root)
    return 0


def cmd_next(a) -> int:
    root = os.path.abspath(a.dir)
    st = _load(root)
    sid = st.get("current")
    if not sid:
        print("全部步骤已完成。跑 `autopilot.py check` 做终检。")
        return 0
    b = st.get("brief") or {}
    arts = ARTS[sid]
    print("=" * 66)
    print(f"工单 · 第 {sid} 步 · {NAME[sid]}（{GROUP[sid]}）")
    print("=" * 66)
    print(f"目标刊：{b.get('venue','')}　类型：{b.get('type','')}　"
          f"篇幅：{b.get('length_limit','')}")
    print()
    print("【必须产出】完成前这些文件必须存在且非空：")
    for rel in arts:
        p = _path(root, rel)
        present = (os.path.isdir(p) if rel.endswith("/") else os.path.isfile(p))
        print(f"  - {rel}   [{'已存在' if present else '待创建'}]")
    if not arts:
        print("  （本步无强制产出）")
    print()
    print(f"【通过标准】{GATE[sid]}")
    print()
    print("【怎么做】读技能目录下的 references/pipeline_steps.md 里 "
          f"「{sid} · {NAME[sid]}」那一节，")
    print("          按里面的「有技能时」或「裸做」流程执行。")
    if sid in ("16", "19"):
        print("          → 另外必须读 references/deai_protocol.md")
    if sid == "10":
        print("          → 另外必须读 references/figure_standards.md")
    if sid == "12":
        print("          → 另外必须读 references/simulation_vv.md")
    if sid in ("14", "18", "20", "21"):
        print("          → 另外必须读 references/submission_and_compliance.md")
    if sid == "15":
        print("          → 另外必须读 references/venue_playbooks.md")
    if sid in ("02", "03", "07", "08", "19", "20"):
        print("          → 文献相关步骤必须用 scripts/litsearch.py 做真实检索与核验，"
              "见 references/literature_and_verification.md")
    if sid in ("10", "12"):
        print("          → 数据必须真跑出来：scripts/simulate.py check / run / provenance，"
              "见 references/simulation_and_data.md")
        print("            禁止手写 data/ 里的数字；每个数据文件都要有 .prov.json")
    print()
    print("【完成后】python autopilot.py done --dir \"%s\"" % root)
    print("          （缺文件会被拒绝前进；确实做不了就用 skip 并写清原因）")
    return 0


def cmd_done(a) -> int:
    root = os.path.abspath(a.dir)
    st = _load(root)
    sid = a.step or st.get("current")
    if sid not in IDS:
        _die(f"--step 必须是 00..{IDS[-1]} 之一，收到 {sid!r}")
    need = ARTS[sid] + list(a.extra or [])
    bad = _check_artifacts(root, need)
    if bad and not a.force:
        print(f"[拒绝] 第 {sid} 步声明的产出还没齐：", file=sys.stderr)
        for x in bad:
            print(f"  - {x}", file=sys.stderr)
        print("\n先把它们做出来；确实做不了就用：\n"
              f'  python autopilot.py skip --dir "{root}" --step {sid} '
              f'--reason "<为什么>"', file=sys.stderr)
        return 1
    if bad and a.force:
        print(f"[warn] --force 跳过了产出检查，仍缺：{bad}")

    rec = st.setdefault("steps", {}).setdefault(sid, {})
    rec["artifacts"] = need
    rec["gate"] = "通过"
    rec["gate_note"] = a.note or "自检通过"
    rec["finished_at"] = _now()
    if sid not in st["completed"]:
        st["completed"].append(sid)
    st["completed"] = sorted(set(st["completed"]), key=IDS.index)
    i = IDS.index(sid)
    st["current"] = IDS[i + 1] if i + 1 < len(IDS) else None
    st["log"].append({"at": _now(), "event": "done", "step": sid,
                      "note": f"{len(need)} 个产出"})
    _save(root, st)
    print(f"[ok] 第 {sid} 步完成（{len(need)} 个产出已核）")
    print(f"     进度 {len(st['completed'])}/{len(S)}"
          + (f" → 下一步 第 {st['current']} 步 · {NAME[st['current']]}"
             if st["current"] else " → 全部完成"))
    return 0


def cmd_skip(a) -> int:
    """Record a step that could not be completed. Keeps the pipeline moving."""
    root = os.path.abspath(a.dir)
    st = _load(root)
    sid = a.step or st.get("current")
    if sid not in IDS:
        _die(f"--step 必须是 00..{IDS[-1]} 之一")
    if not (a.reason or "").strip():
        _die("--reason 必填。降级必须写清为什么，否则就是掩盖。")
    rec = st.setdefault("steps", {}).setdefault(sid, {})
    rec["degraded"] = True
    rec["degrade_reason"] = a.reason
    rec["gate"] = "降级"
    rec["gate_note"] = a.reason
    if sid not in st["completed"]:
        st["completed"].append(sid)
    st["completed"] = sorted(set(st["completed"]), key=IDS.index)
    i = IDS.index(sid)
    st["current"] = IDS[i + 1] if i + 1 < len(IDS) else None
    st.setdefault("degraded", []).append({"step": sid, "reason": a.reason,
                                          "at": _now()})
    st["log"].append({"at": _now(), "event": "skip", "step": sid,
                      "note": a.reason})
    _save(root, st)
    print(f"[!] 第 {sid} 步已降级：{a.reason}")
    print("    ⚠️ 降级项必须在最终交付说明里列出来，不能静默吞掉。")
    if st["current"]:
        print(f"    → 继续第 {st['current']} 步 · {NAME[st['current']]}")
    return 0


def cmd_decide(a) -> int:
    root = os.path.abspath(a.dir)
    st = _load(root)
    st.setdefault("decisions", []).append({
        "at": _now(), "step": a.step or st.get("current") or "",
        "q": a.question, "choice": a.choice, "why": a.why or "",
        "how_to_change": a.how_to_change or "改 DECISIONS.md 里这一条即可",
    })
    st["log"].append({"at": _now(), "event": "decide",
                      "step": a.step or st.get("current") or "",
                      "note": f"{a.question} → {a.choice}"})
    _save(root, st)
    print(f"[ok] 已记录决策：{a.question} → {a.choice}")
    return 0


def cmd_check(a) -> int:
    root = os.path.abspath(a.dir)
    st = _load(root)
    print(f"自检 · {st.get('title')}")
    print()
    problems = 0
    for sid, name, _g, arts, _gate in S:
        rec = (st.get("steps") or {}).get(sid) or {}
        if sid in st.get("completed", []):
            if rec.get("degraded"):
                print(f"  [降级] {sid} {name}：{rec.get('degrade_reason','')}")
                problems += 1
                continue
            bad = _check_artifacts(root, arts)
            if bad:
                print(f"  [缺件] {sid} {name}：{bad}")
                problems += 1
            else:
                print(f"  [ok  ] {sid} {name}")
        elif sid == st.get("current"):
            print(f"  [当前] {sid} {name}")
    print()
    if problems:
        print(f"发现 {problems} 处问题。降级项必须在交付说明里列明。")
    else:
        print("已完成的步骤产出齐全。")
    return 0


def cmd_status(a) -> int:
    root = os.path.abspath(a.dir)
    st = _load(root)
    sys.stdout.write(_human(st))
    return 0


def main() -> int:
    _utf8()
    broken = _check_step_table()
    if broken:
        print("[致命] 步骤表本身有问题，流水线不能运行：", file=sys.stderr)
        for b in broken:
            print(f"  - {b}", file=sys.stderr)
        print("\n这通常意味着 autopilot.py 的步骤表被改坏了。"
              "先修好再跑，否则进度会卡住或错位。", file=sys.stderr)
        return 3
    ap = argparse.ArgumentParser(prog="autopilot",
                                 description="全自动论文流水线驱动")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start", help="建立项目并自动推断所有参数")
    s.add_argument("--dir", required=True)
    s.add_argument("--direction", required=True,
                   help="论文方向/题目——全自动模式下唯一必需的输入")
    s.add_argument("--title", default="")
    s.add_argument("--has-experiment", dest="has_experiment", default="")
    s.add_argument("--authors", default="")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_start)

    n = sub.add_parser("next", help="打印当前步的工单")
    n.add_argument("--dir", required=True)
    n.set_defaults(func=cmd_next)

    d = sub.add_parser("done", help="声明本步完成（会核查产出是否存在）")
    d.add_argument("--dir", required=True)
    d.add_argument("--step", default=None)
    d.add_argument("--extra", nargs="*", default=[])
    d.add_argument("--note", default="")
    d.add_argument("--force", action="store_true")
    d.set_defaults(func=cmd_done)

    k = sub.add_parser("skip", help="降级某步并记录原因（保证流程继续）")
    k.add_argument("--dir", required=True)
    k.add_argument("--step", default=None)
    k.add_argument("--reason", required=True)
    k.set_defaults(func=cmd_skip)

    de = sub.add_parser("decide", help="记录一条自动决策")
    de.add_argument("--dir", required=True)
    de.add_argument("--question", required=True)
    de.add_argument("--choice", required=True)
    de.add_argument("--why", default="")
    de.add_argument("--how-to-change", dest="how_to_change", default="")
    de.add_argument("--step", default=None)
    de.set_defaults(func=cmd_decide)

    c = sub.add_parser("check", help="核对已完成步骤的产出是否齐全")
    c.add_argument("--dir", required=True)
    c.set_defaults(func=cmd_check)

    st = sub.add_parser("status", help="显示完整进度")
    st.add_argument("--dir", required=True)
    st.set_defaults(func=cmd_status)

    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())

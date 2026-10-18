#!/usr/bin/env python3
"""paper-pipeline state machine.

Keeps the pipeline's progress in the *project folder* rather than in any one
agent's context, so the run survives a new session, a different AI, or a
different machine. Standard library only; Python 3.8+.

    python pipeline_state.py init   --dir <folder> --title "..." --direction "..."
    python pipeline_state.py status --dir <folder>
    python pipeline_state.py next   --dir <folder>
    python pipeline_state.py advance --dir <folder> --step 07 --artifacts a.md b.csv
    python pipeline_state.py gate   --dir <folder> --step 07 --pass --note "..."
    python pipeline_state.py gate   --dir <folder> --step 07 --fail --note "缺 3 篇全文"
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------- step table
STEPS = [
    ("00", "总控进度判断", "项目与检索"),
    ("01", "项目初始化", "项目与检索"),
    ("02", "检索式生成", "项目与检索"),
    ("03", "检索与导出", "项目与检索"),
    ("04", "选题与空白识别", "项目与检索"),
    ("05", "对标库深度学习", "文献与证据"),
    ("06", "文献筛选分类", "文献与证据"),
    ("07", "导入引用库取全文", "文献与证据"),
    ("08", "文献精读", "文献与证据"),
    ("09", "综述/论文框架搭建", "框架与写作"),
    ("10", "图表制作与引用", "框架与写作"),
    ("11", "摘要与引言", "框架与写作"),
    ("12", "方法与结果", "框架与写作"),
    ("13", "讨论与结论", "框架与写作"),
    ("14", "目标期刊选择", "投稿与返修"),
    ("15", "目标期刊格式学习", "投稿与返修"),
    ("16", "润色与语言打磨", "投稿与返修"),
    ("17", "图片版权", "投稿与返修"),
    ("18", "Cover Letter", "投稿与返修"),
    ("19", "终稿去 AI 痕迹与合规声明", "投稿与返修"),
    ("20", "投稿前总检", "投稿与返修"),
    ("21", "返修与回复", "投稿与返修"),
]
IDS = [s[0] for s in STEPS]
NAME = {s[0]: s[1] for s in STEPS}
GROUP = {s[0]: s[2] for s in STEPS}

STATE_FILE = "PAPER_STATE.json"
HUMAN_FILE = "PIPELINE.md"
SCHEMA = "paper-pipeline/1.1"
# 1.0 had 21 steps (00-20) with no dedicated de-AI step; 1.1 inserts step 19.
LEGACY_SCHEMAS = {"paper-pipeline/1.0": (
    "旧版 1.0 是 21 步（00-20），没有独立的「终稿去 AI 痕迹」步，"
    "且第 19 步当时是「投稿前总检」。1.1 在第 19 位插入了去 AI 痕迹步，"
    "原 19/20 顺延为 20/21。请核对已完成步骤的含义后再继续。")}


def _stdout_utf8() -> None:
    for stream in ("stdout", "stderr"):
        s = getattr(sys, stream)
        try:
            s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(root: str) -> dict:
    p = os.path.join(root, STATE_FILE)
    if not os.path.isfile(p):
        _die(f"{p} 不存在。先跑 init：\n"
             f'  python pipeline_state.py init --dir "{root}" '
             f'--title "<题目>" --direction "<方向>"')
    with io.open(p, encoding="utf-8") as fh:
        st = json.load(fh)
    legacy = LEGACY_SCHEMAS.get(st.get("schema", ""))
    if legacy:
        print(f"[!] 读到旧版状态文件 schema={st.get('schema')}。\n    {legacy}",
              file=sys.stderr)
    return st


def _save(root: str, st: dict) -> None:
    st["updated_at"] = _now()
    with io.open(os.path.join(root, STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False, indent=1)
    with io.open(os.path.join(root, HUMAN_FILE), "w", encoding="utf-8") as fh:
        fh.write(render_human(st))


def _die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


# ------------------------------------------------------------------- render
def render_human(st: dict) -> str:
    L = []
    L.append(f"# 论文流水线进度 · {st.get('title') or '(未命名)'}")
    L.append("")
    L.append(f"- 方向：{st.get('direction') or '(未填)'}")
    b = st.get("brief") or {}
    if b:
        for k in ("type", "venue", "quartile", "length_limit", "figure_limit",
                  "has_experiment", "authors"):
            if b.get(k):
                L.append(f"- {k}：{b[k]}")
    L.append(f"- 模式：{st.get('mode', 'autopilot')}")
    L.append(f"- 更新：{st.get('updated_at', '')}")
    L.append("")
    done = st.get("completed", [])
    cur = st.get("current")
    L.append(f"**进度 {len(done)}/21**　当前：{cur or '完成'}"
             + (f"（{NAME.get(cur, '')}）" if cur else ""))
    L.append("")
    L.append("| 步 | 名称 | 组 | 状态 | 闸门 | 产出 |")
    L.append("|---:|---|---|---|---|---|")
    for sid, name, group in STEPS:
        rec = (st.get("steps") or {}).get(sid) or {}
        if sid in done:
            status = "已完成"
        elif sid == cur:
            status = "进行中"
        else:
            status = "未开始"
        gate = rec.get("gate") or ""
        arts = rec.get("artifacts") or []
        art_s = "、".join(f"`{a}`" for a in arts[:3]) + ("…" if len(arts) > 3 else "")
        L.append(f"| {sid} | {name} | {group} | {status} | {gate} | {art_s} |")
    L.append("")
    log = st.get("log") or []
    if log:
        L.append("## 操作日志")
        L.append("")
        for e in log[-25:]:
            L.append(f"- `{e.get('at','')}` {e.get('event','')} "
                     f"{e.get('step','')} {e.get('note','')}".rstrip())
        L.append("")
    return "\n".join(L)


# ----------------------------------------------------------------- commands
def cmd_init(a) -> int:
    root = os.path.abspath(a.dir)
    os.makedirs(root, exist_ok=True)
    p = os.path.join(root, STATE_FILE)
    if os.path.isfile(p) and not a.force:
        _die(f"{p} 已存在。要重建加 --force（会丢失已有进度记录）。")
    if a.start not in IDS:
        _die(f"--start 必须是 00..20 之一，收到 {a.start!r}")
    st = {
        "schema": SCHEMA,
        "title": a.title or "",
        "direction": a.direction or "",
        "mode": a.mode,
        "created_at": _now(),
        "updated_at": _now(),
        "current": a.start,
        "completed": [s for s in IDS if s < a.start],
        "steps": {},
        "brief": {
            "type": a.type or "",
            "venue": a.venue or "",
            "quartile": a.quartile or "",
            "length_limit": a.length or "",
            "figure_limit": a.figures or "",
            "has_experiment": a.has_experiment or "",
            "authors": a.authors or "占位符（待补真实作者/单位/邮箱/ORCID）",
        },
        "log": [{"at": _now(), "event": "init", "step": a.start,
                 "note": f"从第 {a.start} 步开始"}],
    }
    for sid, name, group in STEPS:
        os.makedirs(os.path.join(root, f"{sid}_{name}"), exist_ok=True)
    for extra in ("refs", "data", "figures", "manuscript"):
        os.makedirs(os.path.join(root, extra), exist_ok=True)
    _save(root, st)
    print(f"[ok] 项目初始化：{root}")
    print(f"[ok] 当前步骤 {a.start} · {NAME[a.start]} · {GROUP[a.start]}")
    print(f"[ok] 已建 {len(STEPS)} 个步骤文件夹 + refs/ data/ figures/ manuscript/")
    if not st["brief"]["venue"]:
        print("[!] 目标期刊还没定 —— 第 01 步必须定下来，否则后面的格式与选刊全靠猜")
    if not st["brief"]["has_experiment"]:
        print("[!] 有无真实实验数据还没写 —— 第 01 步必须写清楚："
              "没有就必须在摘要和范围声明里写明是仿真/计算研究")
    return 0


def cmd_status(a) -> int:
    st = _load(os.path.abspath(a.dir))
    sys.stdout.write(render_human(st))
    nxt = st.get("current")
    if nxt:
        print(f"\n>>> 下一步：第 {nxt} 步 · {NAME[nxt]} · {GROUP[nxt]}")
    else:
        print("\n>>> 21 步已全部完成。")
    return 0


def cmd_next(a) -> int:
    st = _load(os.path.abspath(a.dir))
    s = st.get("current")
    if not s:
        print("21 步已全部完成。")
        return 0
    print(f"{s}\t{NAME[s]}\t{GROUP[s]}")
    bn = st.get("blocked")
    if bn:
        print(f"[!] 上一步闸门未过：{bn}")
    return 0


def cmd_advance(a) -> int:
    root = os.path.abspath(a.dir)
    st = _load(root)
    s = a.step
    if s not in IDS:
        _die(f"--step 必须是 00..20 之一，收到 {s!r}")
    rec = st.setdefault("steps", {}).setdefault(s, {})
    rec.setdefault("gate", "未检查")
    rec["artifacts"] = list(a.artifacts or rec.get("artifacts") or [])
    rec["finished_at"] = _now()
    if s not in st["completed"]:
        st["completed"].append(s)
    st["completed"] = sorted(set(st["completed"]), key=IDS.index)
    i = IDS.index(s)
    st["current"] = IDS[i + 1] if i + 1 < len(IDS) else None
    st["log"].append({"at": _now(), "event": "advance", "step": s,
                      "note": f"{len(rec['artifacts'])} 个产出"})
    _save(root, st)
    # 闸门提醒
    if rec.get("gate") in (None, "", "未检查", "未通过"):
        print(f"[!] 第 {s} 步已标记完成，但闸门状态是「{rec.get('gate')}」——"
              f"请跑 gate --pass 或 gate --fail 把结论记下来")
    print(f"[ok] 第 {s} 步完成 → 下一步 "
          + (f"第 {st['current']} 步 · {NAME[st['current']]}" if st["current"] else "（全部完成）"))
    return 0


def cmd_gate(a) -> int:
    root = os.path.abspath(a.dir)
    st = _load(root)
    s = a.step
    if s not in IDS:
        _die(f"--step 必须是 00..20 之一，收到 {s!r}")
    rec = st.setdefault("steps", {}).setdefault(s, {})
    if a.passed and a.failed:
        _die("--pass 和 --fail 只能选一个")
    if not (a.passed or a.failed):
        _die("必须给 --pass 或 --fail")
    rec["gate"] = "通过" if a.passed else "未通过"
    rec["gate_note"] = a.note or ""
    rec["gate_at"] = _now()
    if a.failed:
        st["blocked"] = f"第 {s} 步闸门未通过：{a.note or ''}"
        if s in st["completed"]:
            st["completed"].remove(s)
        st["current"] = s
    else:
        st.pop("blocked", None)
    st["log"].append({"at": _now(), "event": "gate",
                      "step": s, "note": f"{rec['gate']} {a.note or ''}".strip()})
    _save(root, st)
    print(f"[ok] 第 {s} 步闸门：{rec['gate']}"
          + (f" —— {rec['gate_note']}" if rec["gate_note"] else ""))
    if a.failed:
        print(f"[!] 已回退到第 {s} 步重做。修完再 advance。")
    return 0


def cmd_brief(a) -> int:
    """Record or amend the project brief without rebuilding the project."""
    root = os.path.abspath(a.dir)
    st = _load(root)
    b = st.setdefault("brief", {})
    changed = []
    for k, v in (("type", a.type), ("venue", a.venue), ("quartile", a.quartile),
                 ("length_limit", a.length), ("figure_limit", a.figures),
                 ("has_experiment", a.has_experiment), ("authors", a.authors)):
        if v is not None:
            b[k] = v
            changed.append(k)
    if a.title is not None:
        st["title"] = a.title
        changed.append("title")
    if a.direction is not None:
        st["direction"] = a.direction
        changed.append("direction")
    if a.mode is not None:
        st["mode"] = a.mode
        changed.append("mode")
    st["log"].append({"at": _now(), "event": "brief", "step": st.get("current") or "",
                      "note": "更新 " + "、".join(changed)})
    _save(root, st)
    print(f"[ok] 已更新：{'、'.join(changed) if changed else '（没有变化）'}")
    return 0


def main() -> int:
    _stdout_utf8()
    ap = argparse.ArgumentParser(prog="pipeline_state",
                                 description="paper-pipeline 进度管理（跨会话续跑）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init", help="建立新项目")
    i.add_argument("--dir", required=True)
    i.add_argument("--title", default="")
    i.add_argument("--direction", default="")
    i.add_argument("--type", default="", help="research article / review / ...")
    i.add_argument("--venue", default="")
    i.add_argument("--quartile", default="", help="如 Q2")
    i.add_argument("--length", default="", help="篇幅上限，如 8000 words")
    i.add_argument("--figures", default="", help="图表数量上限，如 8 figures / 6 tables")
    i.add_argument("--has-experiment", dest="has_experiment", default="",
                   help="yes / no / simulation-only")
    i.add_argument("--authors", default="")
    i.add_argument("--mode", default="autopilot", choices=["autopilot", "checkpoint"])
    i.add_argument("--start", default="01", help="从第几步开始，默认 01")
    i.add_argument("--force", action="store_true")
    i.set_defaults(func=cmd_init)

    for nm, fn, hlp in (("status", cmd_status, "显示完整进度"),
                        ("next", cmd_next, "只输出下一步")):
        p = sub.add_parser(nm, help=hlp)
        p.add_argument("--dir", required=True)
        p.set_defaults(func=fn)

    ad = sub.add_parser("advance", help="标记某步完成并前进")
    ad.add_argument("--dir", required=True)
    ad.add_argument("--step", required=True)
    ad.add_argument("--artifacts", nargs="*", default=[])
    ad.set_defaults(func=cmd_advance)

    g = sub.add_parser("gate", help="记录某步闸门结论")
    g.add_argument("--dir", required=True)
    g.add_argument("--step", required=True)
    g.add_argument("--pass", dest="passed", action="store_true")
    g.add_argument("--fail", dest="failed", action="store_true")
    g.add_argument("--note", default="")
    g.set_defaults(func=cmd_gate)

    b = sub.add_parser("brief", help="补充/修改项目基本信息")
    b.add_argument("--dir", required=True)
    b.add_argument("--title")
    b.add_argument("--direction")
    b.add_argument("--type")
    b.add_argument("--venue")
    b.add_argument("--quartile")
    b.add_argument("--length")
    b.add_argument("--figures")
    b.add_argument("--has-experiment", dest="has_experiment")
    b.add_argument("--authors")
    b.add_argument("--mode", choices=["autopilot", "checkpoint"])
    b.set_defaults(func=cmd_brief)

    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())

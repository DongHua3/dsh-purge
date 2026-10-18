#!/usr/bin/env python3
"""探测本机环境：装了哪些工具、哪些技能，以及没有时该走哪条裸做路径。

    python check_env.py                 # 人可读报告
    python check_env.py --json env.json # 机器可读
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import shutil
import subprocess
import sys

TOOLS = {
    "python": ("Python 解释器", True),
    "pandoc": ("Markdown → DOCX/LaTeX", False),
    "git": ("版本管理", False),
    "node": ("Node.js 运行时", False),
    "npx": ("Node 包运行器", False),
    "yt-dlp": ("视频下载（video-reader 用）", False),
    "ffmpeg": ("音视频处理（抽帧/转写用）", False),
    "latexmk": ("LaTeX 编译", False),
    "pdflatex": ("LaTeX 编译", False),
    "tectonic": ("LaTeX 编译", False),
    "libreoffice": ("Office 转换", False),
    "soffice": ("Office 转换", False),
}

PY_LIBS = [
    ("numpy", "数值计算"),
    ("scipy", "科学计算"),
    ("matplotlib", "绘图"),
    ("pandas", "表格与数据"),
    ("docx", "DOCX 生成（python-docx）"),
    ("reportlab", "PDF 生成"),
    ("openpyxl", "Excel 读写"),
    ("PIL", "图像处理（Pillow）"),
    ("cv2", "视频抽帧（OpenCV）"),
    ("fitz", "PDF 解析（PyMuPDF）"),
    ("requests", "HTTP 请求"),
    ("whisper", "语音转写（openai-whisper）"),
    ("faster_whisper", "语音转写（faster-whisper）"),
]

SKILL_ROOTS = {
    "dsh": "~/.dsh/skills",
    "codex": "~/.codex/skills",
    "claude": "~/.claude/skills",
    "cursor": "~/.cursor/skills",
    "windsurf": "~/.windsurf/skills",
    "gemini": "~/.gemini/skills",
    "project(./skills)": "./skills",
    "project(./.agent/skills)": "./.agent/skills",
    "project(./.claude/skills)": "./.claude/skills",
}


def _stdout_utf8() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def scan_skills() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for label, raw in SKILL_ROOTS.items():
        root = os.path.abspath(os.path.expanduser(raw))
        if not os.path.isdir(root):
            continue
        names = sorted(
            d for d in os.listdir(root)
            if os.path.isfile(os.path.join(root, d, "SKILL.md"))
        )
        if names:
            found[label] = names
    return found


def probe() -> dict:
    tools = {}
    for name, (desc, required) in TOOLS.items():
        p = shutil.which(name)
        tools[name] = {"path": p or "", "desc": desc, "required": required,
                       "ok": bool(p)}
    libs = {}
    for mod, desc in PY_LIBS:
        try:
            __import__(mod)
            libs[mod] = {"desc": desc, "ok": True}
        except Exception:
            libs[mod] = {"desc": desc, "ok": False}
    return {
        "python_version": sys.version.split()[0],
        "executable": sys.executable,
        "platform": sys.platform,
        "tools": tools,
        "python_libs": libs,
        "skills": {k: len(v) for k, v in scan_skills().items()},
    }


def main() -> int:
    _stdout_utf8()
    ap = argparse.ArgumentParser(prog="check_env")
    ap.add_argument("--json", dest="json_out", default="")
    a = ap.parse_args()
    env = probe()

    print(f"Python {env['python_version']}  ({env['executable']})")
    print(f"平台 {env['platform']}\n")

    print("外部工具")
    for name, info in env["tools"].items():
        mark = "OK     " if info["ok"] else ("缺失 * " if info["required"] else "缺失   ")
        where = info["path"] or f"（{info['desc']}）"
        print(f"  {mark} {name:14s} {where}")

    print("\nPython 库")
    for mod, info in env["python_libs"].items():
        print(f"  {'OK     ' if info['ok'] else '缺失   '} {mod:16s} {info['desc']}")

    print("\n技能目录")
    if env["skills"]:
        for label, n in env["skills"].items():
            print(f"  {label:26s} {n} 个技能")
    else:
        print("  未发现任何 SKILL.md 目录 —— 走「裸做」路径也能跑完整条流水线")

    miss_req = [n for n, i in env["tools"].items() if i["required"] and not i["ok"]]
    print("\n结论")
    if miss_req:
        print(f"  [!] 必需工具缺失：{', '.join(miss_req)}")
    else:
        print("  [ok] 必需工具齐全")

    hard = [m for m, i in env["python_libs"].items() if not i["ok"]]
    if hard:
        print(f"  [i] 缺少的库（按需装）：{', '.join(hard)}")
    print("  [i] 没有 pandoc/LaTeX 时：DOCX 用 python-docx 直接生成，"
          "PDF 用 reportlab 或浏览器打印，不影响交付")

    if a.json_out:
        with io.open(a.json_out, "w", encoding="utf-8") as fh:
            json.dump(env, fh, ensure_ascii=False, indent=1)
        print(f"\n[ok] JSON：{a.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

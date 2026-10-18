#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LaTeX 数学式 -> Unicode 文本转换（供 docx 构建使用）。

学位论文正文需要人眼可读的公式。python-docx 无法排版真正的数学公式
（OMML），因此本模块把 md 源中的 LaTeX 片段转换为 Unicode 字符表示，
使其在 Word/WPS 中可直接阅读、可复制、可打印。

处理能力：
    - 希腊字母与常用算符：\\rho -> ρ，\\times -> ×，\\approx -> ≈ 等
    - 上标/下标：M^2 -> M²，C_1 -> C₁（无对应 Unicode 时用 ^(...) / _(...)）
    - 常用修饰：\\bar{x} -> x̄，\\tilde{x} -> x̃，\\hat{x} -> x̂
    - 分数：\\frac{a}{b} -> (a)/(b)；\\tfrac 同
    - 根号：\\sqrt{x} -> √(x)
    - 函数名与排版命令：\\mathrm/\\text/\\left/\\right/\\displaystyle/\\quad 等直接剥离
    - 行间公式的 \\tag{2-1} -> （2-1）

不支持任意嵌套的复杂公式（如多重分式嵌套、矩阵）。若遇到无法处理的结构，
保留其原文并在控制台打印警告，由人工核对——不静默产生错误公式。
"""
from __future__ import annotations

import re
import sys

GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "Gamma": "Γ", "delta": "δ",
    "Delta": "Δ", "epsilon": "ε", "varepsilon": "ε", "zeta": "ζ", "eta": "η",
    "theta": "θ", "Theta": "Θ", "iota": "ι", "kappa": "κ", "lambda": "λ",
    "Lambda": "Λ", "mu": "μ", "nu": "ν", "xi": "ξ", "Xi": "Ξ", "pi": "π",
    "Pi": "Π", "rho": "ρ", "sigma": "σ", "Sigma": "Σ", "tau": "τ",
    "upsilon": "υ", "phi": "φ", "varphi": "φ", "chi": "χ", "psi": "ψ",
    "Psi": "Ψ", "omega": "ω", "Omega": "Ω",
}

OPS = {
    "times": "×", "cdot": "·", "pm": "±", "mp": "∓", "approx": "≈",
    "neq": "≠", "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥",
    "ll": "≪", "gg": "≫", "sim": "~", "simeq": "≃", "equiv": "≡",
    "propto": "∝", "infty": "∞", "partial": "∂", "nabla": "∇",
    "rightarrow": "→", "to": "→", "leftarrow": "←", "Rightarrow": "⇒",
    "in": "∈", "notin": "∉", "subset": "⊂", "cup": "∪", "cap": "∩",
    "sum": "Σ", "prod": "Π", "int": "∫", "circ": "∘", "ast": "*",
    "sqrt": "√", "angle": "∠", "perp": "⊥", "parallel": "∥",
    "quad": " ", "qquad": "  ", "enspace": " ", "qquad": "  ",
    ",": " ", ";": " ", "!": "", " ": " ",
}

# 直接剥离的排版命令
STRIP_CMDS = [
    "mathrm", "mathbf", "mathit", "mathsf", "mathtt", "text", "textrm",
    "operatorname", "mathcal", "mathbb", "mathfrak",
    "left", "right", "big", "Big", "bigg", "Bigg", "displaystyle",
    "textstyle", "limits", "nolimits", "mathstrut", "phantom",
    "underbrace", "overbrace", "underset", "overset",
]

FUNCS = ["ln", "log", "exp", "sin", "cos", "tan", "max", "min", "clamp",
         "arccos", "arcsin", "arctan", "det", "dim"]

SUP = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵",
       "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "+": "⁺", "-": "⁻",
       "=": "⁼", "(": "⁽", ")": "⁾", "n": "ⁿ", "i": "ⁱ", "*": "*",
       "ε": "ᵋ", "β": "ᵝ", "γ": "ᵞ", "δ": "ᵟ", "φ": "ᵠ", "χ": "ᵡ",
       "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ", "f": "ᶠ",
       "g": "ᵍ", "h": "ʰ", "j": "ʲ", "k": "ᵏ", "l": "ˡ", "m": "ᵐ",
       "o": "ᵒ", "p": "ᵖ", "r": "ʳ", "s": "ˢ", "t": "ᵗ", "u": "ᵘ",
       "v": "ᵛ", "w": "ʷ", "x": "ˣ", "y": "ʸ", "z": "ᶻ"}

SUB = {"0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅",
       "6": "₆", "7": "₇", "8": "₈", "9": "₉", "+": "₊", "-": "₋",
       "=": "₌", "(": "₍", ")": "₎", "a": "ₐ", "e": "ₑ", "i": "ᵢ",
       "o": "ₒ", "r": "ᵣ", "s": "ₛ", "t": "ₜ", "x": "ₓ", "y": "ᵧ",
       "β": "ᵦ", "γ": "ᵧ", "ρ": "ᵨ", "φ": "ᵩ", "χ": "ᵪ"}

WARNINGS: list[str] = []


def _script(ch: str, table: dict[str, str]) -> str | None:
    return table.get(ch)


def _brace_group(s: str, i: int) -> tuple[str, int]:
    """从 s[i] == '{' 开始取配对花括号内的内容。返回 (内容, 新位置)。"""
    if i >= len(s) or s[i] != "{":
        return "", i
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
    return s[i + 1:], len(s)


def _one_token(s: str, i: int) -> tuple[str, int]:
    """取一个"原子"：{...} 组、单个字符，或反斜杠命令。"""
    if i >= len(s):
        return "", i
    if s[i] == "{":
        return _brace_group(s, i)
    if s[i] == "\\":
        m = re.match(r"\\([a-zA-Z]+)", s[i:])
        if m:
            return "\\" + m.group(1), i + m.end()
        return s[i:i + 2], i + 2
    return s[i], i + 1


def _to_script(content: str, table: dict[str, str], marker: str) -> str:
    """把内容转成 Unicode 上下标。

    优先整体转换；含无法映射的字符时，尝试"最内层可映射子串"策略：
    例如上标内容 "ε_D" 无法整体映射，但去掉 "_D" 后的 "ε" 也不可映射，
    此时退化为 marker(内容)。对下标内容 "bond"，因字母 b/n/d 无下标
    字形，退化为 _(bond)。
    """
    out = []
    content = content.strip()
    # _one_token 在解析 "^" / "_" 后可能返回带花括号的组（如 "{\mathrm{bond}}"）
    # 或未配对的 "{bond}"，这里统一剥掉最外层花括号，否则后续的
    # "纯字母" 判断会因存在 {} 而失败，退化成 _(bond) 形式。
    while len(content) >= 2 and content.startswith("{") and content.endswith("}"):
        content = content[1:-1].strip()
    # 仅当内容里确实还有未处理的 LaTeX 命令（反斜杠）时才递归展开，
    # 否则会把已解析的 "_σ" 再次映射成下标而导致信息丢失。
    if "\\" in content:
        content = latex_to_unicode(content)
        content = re.sub(r"\\[a-zA-Z]+", "", content)
    content = content.strip()
    if not content:
        return ""
    for ch in content:
        rep = _script(ch, table)
        if rep is None:
            # 尝试把内容里的 "^..." 或 "_..." 剥掉后重试（处理 ^{ n} 这类）
            cleaned = re.sub(r"[\^_]\s*\(?[^)]*\)?", "", content).strip()
            if cleaned and cleaned != content:
                return _to_script(cleaned, table, marker)
            # 纯字母或单个希腊字母内容：用 marker + 内容（如 _(bond) -> _bond、
            # _σ -> _σ）。Unicode 没有 σ/ε 的下标字形，加括号反而更差，故不加。
            if re.fullmatch(r"[a-zA-Z]+|[\u0370-\u03ff]", content):
                rep2 = table.get(content) or table.get(GREEK.get(content, ""))
                if rep2 is not None:
                    return rep2
                return f"{marker}{content}"
            return f"{marker}({content})"
        out.append(rep)
    return "".join(out)


def _simplify_frac(s: str) -> str:
    """把 (a)/(b) 化简为 a/b —— 仅当 a、b 不含低优先运算符时。"""
    for _ in range(6):
        m = re.search(r"\(([^()]*)\)/\(([^()]*)\)", s)
        if not m:
            break
        a, b = m.group(1).strip(), m.group(2).strip()
        if any(op in a for op in "+- ") or any(op in b for op in "+- "):
            break
        s = s[:m.start()] + f"{a}/{b}" + s[m.end():]
    return s


def latex_to_unicode(expr: str) -> str:
    """把一段 LaTeX 数学式转换为 Unicode 文本。"""
    s = expr.strip()
    # 0a) 定积分上下限：先把 \int_a^b 展开成可读形式，避免上下标互相覆盖。
    #     例如 "\int_0^{\varepsilon_D}" -> "(从 0 到 ε_D 的积分)"
    def _int_limit(m):
        lo = m.group(1).strip()
        hi = m.group(2).strip()
        lo_t = latex_to_unicode(lo) if "\\" in lo else lo
        hi_t = latex_to_unicode(hi) if "\\" in hi else hi
        return f"(从 {lo_t} 到 {hi_t} 积分) "
    s = re.sub(r"\\int\s*_(\{[^}]*\}|[0-9a-zA-Z])\s*\^\s*(\{[^}]*\}|[0-9a-zA-Z])",
               _int_limit, s)

    # 0b) 清除间距类命令（\, \; \! 等）——必须在上下标解析之前做，
    #     否则 "^{\,n}" 的内容会变成 "\,n"，无法映射为上标。
    s = re.sub(r"\\[,;!>]", "", s)
    s = re.sub(r"\\(?:quad|qquad|enspace|thinspace|medspace|thickspace)\b", " ", s)

    # 1) 处理 \frac{a}{b} / \tfrac / \dfrac（可能嵌套，循环到不动点）
    for _ in range(6):
        m = re.search(r"\\(?:dfrac|tfrac|frac)\s*\{", s)
        if not m:
            break
        start = m.start()
        a, p = _brace_group(s, s.index("{", m.start()))
        # 跳过空白后取第二个组
        while p < len(s) and s[p].isspace():
            p += 1
        if p >= len(s) or s[p] != "{":
            break
        b, p2 = _brace_group(s, p)
        s = s[:start] + f"({a})/({b})" + s[p2:]

    # 2) 处理 \sqrt{x} -> √(x)
    for _ in range(4):
        m = re.search(r"\\sqrt\s*\{", s)
        if not m:
            break
        c, p = _brace_group(s, s.index("{", m.start()))
        s = s[:m.start()] + f"√({c})" + s[p:]

    # 3) 剥离排版命令（保留其内容）
    for cmd in STRIP_CMDS:
        s = re.sub(r"\\" + cmd + r"\s*", "", s)
    s = re.sub(r"\\begin\{[^}]*\}|\\end\{[^}]*\}", "", s)

    # 4) 修饰符：\bar{x} \tilde{x} \hat{x} \dot{x} \vec{x}
    marks = {"bar": "\u0304", "tilde": "\u0303", "hat": "\u0302",
             "dot": "\u0307", "vec": "\u20d7", "overline": "\u0305"}
    for _ in range(6):
        m = re.search(r"\\(bar|tilde|hat|dot|vec|overline)\s*\{", s)
        if not m:
            break
        c, p = _brace_group(s, s.index("{", m.start()))
        comb = marks[m.group(1)]
        s = s[:m.start()] + c + comb + s[p:]

    # 5) 上下标
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in "^_":
            table = SUP if ch == "^" else SUB
            marker = "^" if ch == "^" else "_"
            nxt, i2 = _one_token(s, i + 1)
            if nxt.startswith("\\") and nxt[1:] in GREEK:
                nxt = GREEK[nxt[1:]]
            elif len(nxt) == 1 and nxt.isalpha() and nxt not in table:
                out.append(marker + nxt)
                i = i2
                continue
            out.append(_to_script(nxt, table, marker))
            i = i2
            continue
        out.append(ch)
        i += 1
    s = "".join(out)

    # 6) 希腊字母
    for name, sym in GREEK.items():
        s = re.sub(r"\\" + name + r"(?![a-zA-Z])", sym, s)

    # 7) 函数名：\ln -> ln，\max -> max
    for fn in FUNCS:
        s = re.sub(r"\\" + fn + r"\b", fn, s)

    # 8) 算符与符号
    for name in sorted(OPS, key=len, reverse=True):
        s = re.sub(r"\\" + re.escape(name) + r"(?![a-zA-Z])", OPS[name], s)

    # 9) 剩余未知命令：保留原名并告警
    for m in re.finditer(r"\\[a-zA-Z]+", s):
        if m.group(0) not in ("\\",):
            WARNINGS.append(m.group(0))
    s = re.sub(r"\\,|\\;|\\!|\\ ", " ", s)

    # 10) 清理多余花括号与空白
    s = s.replace("{", "").replace("}", "")
    s = _simplify_frac(s)
    s = re.sub(r"[ \t]{2,}", " ", s).strip()
    return s


_TAG = re.compile(r"\\tag\{([^}]*)\}")


def convert_display(block: str) -> str:
    """转换行间公式：\\tag{2-1} -> （2-1），其余转 Unicode。"""
    tags = _TAG.findall(block)
    body = _TAG.sub("", block)
    conv = latex_to_unicode(body)
    if tags:
        return f"{conv}　　（{tags[0].strip()}）"
    return conv


INLINE = re.compile(r"(?<!\$)\$([^$\n]+)\$(?!\$)")
DISPLAY = re.compile(r"\$\$(.+?)\$\$", re.S)


def convert_text(text: str) -> str:
    """对整篇文本做公式转换（先处理 $$...$$，再处理 $...$）。"""
    text = DISPLAY.sub(lambda m: "\n" + convert_display(m.group(1)) + "\n", text)
    text = INLINE.sub(lambda m: latex_to_unicode(m.group(1)), text)
    return text


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    samples = [
        r"\bar{\rho} = \frac{\rho^*}{\rho_s} = \eta \, \left(\frac{d}{a}\right)^{2}",
        r"\frac{E^*}{E_s} = C_1 \, \bar{\rho}^{\,n}",
        r"\mathrm{SEA} = \frac{\displaystyle\int_0^{\varepsilon_D} \sigma \, \mathrm{d}\varepsilon}{\bar{\rho}\,\rho_s}",
        r"n \approx 2",
        r"30 \times 30 \times 30",
        r"f_{\mathrm{bond}}(t) = 1 - \kappa \, \frac{t - t_{\mathrm{ref}}}{t_{\mathrm{ref}}}",
    ]
    for s in samples:
        print("IN :", s)
        print("OUT:", latex_to_unicode(s))
        print()
    if WARNINGS:
        print("未处理的命令:", sorted(set(WARNINGS)))

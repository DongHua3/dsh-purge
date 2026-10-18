#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引用一致性校验（thesis-pipeline）

校验四件事：
  1. 悬空引用——正文引了 [n]，但参考文献表没有第 n 条；
  2. 孤立条目——文献表有第 n 条，但正文从未引用（顺序编码制下属规范问题）；
  3. **引用内容匹配**——正文里"[n]"前面提到的作者姓氏，是否与文献表第 n 条的
     作者一致。这一项专治"多次重编号后引用号错位指向错误文献"，
     纸质校对几乎查不出来；
  4. 引用号出现顺序是否大体随正文推进（顺序编码制的惯例）。

用法：
    python check_refs.py --manuscript <manuscript/> --refs <参考文献.md>
    python check_refs.py --manuscript manuscript/ --refs 05_稿件/参考文献.md --json out.json

退出码：0 = 全部通过；1 = 有 FAIL 级问题。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# 引用号：支持 [3]、[3,6]、[3-5]、[3，6]
CITE = re.compile(r"\[(\d+(?:\s*[,，\-–]\s*\d+)*)\]")
# 文献条目：[12] 作者. 题名...
REF_LINE = re.compile(r"^\[(\d+)\]\s*(.*)$")

# 拉丁人名（后随 "等" / "et al." 时最可靠）
NAME_LATIN = re.compile(
    r"([A-Z][A-Za-z'’\-]{1,}(?:\s+(?:van|von|de|der|di|del)\b)?)"
    r"\s*(?:等|et\s+al\.?)"
)
# 中文人名：2-4 个汉字 + 「等」
NAME_CN = re.compile(r"([\u4e00-\u9fff]{2,4})\s*等")

# 中文姓氏首字表（用于判定前面确实是个人名，显著降低误判）
CN_SURNAME = set("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
                 "戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐"
                 "费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄"
                 "和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁"
                 "杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍"
                 "虞万支柯昝管卢莫房裘缪干解应宗丁宣邓郁单杭洪包诸左石崔吉龚程邢滑"
                 "裴陆荣翁荀羊惠甄曲封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯"
                 "宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭历戎祖武符刘景詹束龙叶幸司韶郜黎"
                 "蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴胥能苍双闻莘党翟谭贡劳"
                 "逄姬申扶堵冉宰郦雍卻璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎"
                 "充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙"
                 "东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须"
                 "丰巢关蒯相查后荆红游竺权逯盖益桓公")

# 中文里高频出现在句尾、容易被误当作人名的词（简称/名词结尾）
CN_STOPWORDS = {
    "影响", "研究", "分析", "方法", "性能", "结果", "结论", "文献", "标准", "模型",
    "结构", "材料", "工艺", "参数", "数据", "系统", "设计", "实验", "仿真", "数值",
    "问题", "特征", "规律", "机理", "行为", "作用", "意义", "价值", "关系", "变化",
    "讨论", "证明", "表明", "指出", "报道", "提出", "建立", "完成", "实现", "开展",
    "测试", "测量", "表征", "评价", "优化", "验证", "对比", "比较", "综述", "进展",
    "非常规", "双重", "相关", "典型", "常见", "重要", "主要", "关键", "基础", "理论",
}


def expand(token: str) -> list[int]:
    """展开 [3,6] / [3-5] 为编号列表，保持出现顺序。"""
    out: list[int] = []
    for part in re.split(r"[,，]", token):
        part = part.strip()
        m = re.match(r"^(\d+)\s*[-–]\s*(\d+)$", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            out.extend(range(a, b + 1) if a <= b else range(a, b - 1, -1))
        elif part.isdigit():
            v = int(part)
            if v >= 1:          # [0] 是代码里的下标（如 polyfit(...)[0]），不是引用
                out.append(v)
    return out


def parse_refs(path: Path) -> dict[int, dict]:
    """解析参考文献表，返回 {编号: {raw, authors}}。"""
    refs: dict[int, dict] = {}
    if not path.exists():
        return refs
    for line in path.read_text(encoding="utf-8").splitlines():
        m = REF_LINE.match(line.strip())
        if not m:
            continue
        num = int(m.group(1))
        body = m.group(2)
        # 作者在第一个 "." 之前（GB/T 7714 体例）
        authors_blob = body.split(".", 1)[0]
        names: list[str] = []
        for chunk in re.split(r"[,，;；]", authors_blob):
            chunk = chunk.strip()
            if not chunk:
                continue
            # 拉丁："Gonabadi H." -> Gonabadi ; 中文："张（Zhang）等" -> 张
            latin = re.match(r"^([A-Z][A-Za-z'’\-]+)", chunk)
            cn = re.match(r"^([\u4e00-\u9fff]{2,4})", chunk)
            if latin:
                names.append(latin.group(1))
            elif cn:
                names.append(cn.group(1))
        refs[num] = {"raw": body, "authors": names}
    return refs


def read_manuscript(dirpath: Path) -> str:
    files = sorted(dirpath.glob("*.md"))
    return "\n\n".join(p.read_text(encoding="utf-8") for p in files)


def extract_surname_before(text: str, pos: int) -> str:
    """取引用号之前、同一句内**最靠近**引用号的人名。

    实际行文形如「Dziewit 等则同时研究了……的影响[5]」，人名与引用号之间隔着
    若干字，因此不能要求名字紧贴引用号。做法：截出同句片段，用 finditer 找出
    全部「人名+等」，取位置最靠后的一个。

    宁可漏检也不误报——误报会让这一校验失去可信度。
    """
    left = text[max(0, pos - 90):pos]
    for sep in ("。", "；", ";", "！", "？", "\n"):
        i = left.rfind(sep)
        if i >= 0:
            left = left[i + 1:]

    best_pos, best_name = -1, ""
    for m in NAME_LATIN.finditer(left):
        if m.start() >= best_pos:
            best_pos, best_name = m.start(), m.group(1)
    for m in NAME_CN.finditer(left):
        if m.start() < best_pos:
            continue
        name = m.group(1)
        if name in CN_STOPWORDS or name[0] not in CN_SURNAME:
            continue
        best_pos, best_name = m.start(), name
    return best_name


def main() -> int:
    ap = argparse.ArgumentParser(description="引用一致性校验")
    ap.add_argument("--manuscript", required=True, help="分章 md 所在目录")
    ap.add_argument("--refs", required=True, help="参考文献表 md 文件")
    ap.add_argument("--json", default="", help="可选：输出 JSON 报告")
    ap.add_argument("--max-report", type=int, default=12, help="每类问题最多列出几条")
    args = ap.parse_args()

    man_dir = Path(args.manuscript)
    refs_path = Path(args.refs)
    text = read_manuscript(man_dir)
    refs = parse_refs(refs_path)

    used: list[int] = []
    for m in CITE.finditer(text):
        used.extend(expand(m.group(1)))
    used_set = set(used)
    defined = set(refs)

    dangling = sorted(used_set - defined)
    orphan = sorted(i for i in defined - used_set if defined and i <= max(defined))

    # ---- 引用内容匹配 ----
    misaligned: list[dict] = []
    checked = 0
    for m in CITE.finditer(text):
        nums = expand(m.group(1))
        if len(nums) != 1:
            continue          # 多号引用（如 [3,6]）前的名字可能只对应其中一个，跳过
        n = nums[0]
        if n not in refs:
            continue
        surname = extract_surname_before(text, m.start())
        if not surname:
            continue
        checked += 1
        authors = refs[n]["authors"]
        if not authors:
            continue
        # 中文姓氏取首字比对；拉丁取完整姓氏（允许前缀匹配，兼容缩写）
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", surname):
            hit = any(a.startswith(surname[0]) for a in authors)
        else:
            hit = any(a.lower() == surname.lower() or
                      a.lower().startswith(surname.lower()[:4]) for a in authors)
        if not hit:
            misaligned.append({"ref": n, "surname_in_text": surname,
                               "authors_in_ref": authors,
                               "context": text[max(0, m.start() - 120):m.end()].replace("\n", " ")})

    # ---- 引用顺序 ----
    first_pos: dict[int, int] = {}
    for m in CITE.finditer(text):
        for n in expand(m.group(1)):
            first_pos.setdefault(n, m.start())
    seq = [n for n, _ in sorted(first_pos.items(), key=lambda kv: kv[1])]
    inversions = sum(1 for i in range(len(seq) - 1) if seq[i + 1] < seq[i])

    # ---- 输出 ----
    print("=" * 70)
    print("引用一致性校验")
    print("=" * 70)
    print(f"正文引用号 {len(used_set)} 个 | 文献表 {len(defined)} 条 | "
          f"可做内容比对 {checked} 处")
    print()

    problems = 0
    tag = lambda ok: "PASS" if ok else "FAIL"      # noqa: E731
    print(f"[{tag(not dangling)}] 悬空引用：{len(dangling)} 处"
          + (f" -> {dangling[:args.max_report]}" if dangling else ""))
    problems += bool(dangling)

    print(f"[{tag(not orphan)}] 孤立条目：{len(orphan)} 条"
          + (f" -> {orphan[:args.max_report]}" if orphan else ""))
    if orphan:
        print("       （顺序编码制下建议把未引用条目移入「延伸阅读」，不占编号）")
    problems += bool(orphan)

    print(f"[{tag(not misaligned)}] 引用内容匹配：{len(misaligned)} 处可疑"
          + ("（正文提到的作者与文献表作者不一致）" if misaligned else ""))
    for it in misaligned[:args.max_report]:
        print(f"       [{it['ref']}] 正文写的是「{it['surname_in_text']}」，"
              f"文献表作者为 {it['authors_in_ref'][:3]}")
        print(f"              上下文：...{it['context'][-70:]}")
    problems += bool(misaligned)

    order_ok = inversions == 0
    print(f"[{'PASS' if order_ok else 'WARN'}] 引用顺序：{inversions} 处逆序"
          + ("（顺序编码制下建议按首次出现顺序编号）" if inversions else ""))
    if inversions:
        print(f"       实际顺序前 20 个编号：{seq[:20]}")

    print()
    print("结论：" + ("全部通过" if problems == 0 else f"{problems} 项需要处理"))

    if args.json:
        Path(args.json).write_text(json.dumps({
            "used": sorted(used_set), "defined": sorted(defined),
            "dangling": dangling, "orphan": orphan,
            "misaligned": misaligned, "inversions": inversions,
            "order": seq,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"JSON 报告：{args.json}")

    return 0 if problems == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

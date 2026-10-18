#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 Word COM 把 docx 导出为 PDF（Word 未注册时回退到 WPS COM）。

用法：
    python docx_to_pdf.py [输入.docx] [输出.pdf]
    python docx_to_pdf.py --help

不传输入时自动找当前目录 `deliverables/` 下的 docx；该目录恰好一个 docx 才自动选中，
多个则列出候选让你显式指定。输出默认与输入同名 `.pdf`。
"""
from __future__ import annotations

import sys
from pathlib import Path

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

WD_FORMAT_PDF = 17

CANDIDATES = ["Word.Application", "KWPS.Application", "WPS.Application"]


def resolve_src() -> Path | None:
    """定位待转换的 docx：显式参数 > deliverables/ 下唯一的 docx。"""
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    for base in (Path.cwd() / "deliverables", Path.cwd()):
        if not base.is_dir():
            continue
        cands = sorted(p for p in base.glob("*.docx") if not p.name.startswith("~$"))
        if len(cands) == 1:
            return cands[0]
        if len(cands) > 1:
            print(f"{base} 下有多个 docx，请显式指定要转换哪一个：")
            for p in cands:
                print(f"  {p.name}")
            return None
    print("找不到待转换的 docx。用法：python docx_to_pdf.py [输入.docx] [输出.pdf]")
    return None


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    src = resolve_src()
    if src is None:
        return 2
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".pdf")
    if not src.exists():
        print(f"找不到输入文件：{src}")
        return 1

    import win32com.client as win32  # 延迟导入，避免无 pywin32 时脚本不可读

    last_err = None
    for progid in CANDIDATES:
        app = None
        try:
            print(f"尝试通过 {progid} 转换 ...")
            app = win32.DispatchEx(progid)
            try:
                app.Visible = False
            except Exception:
                pass
            try:
                app.DisplayAlerts = 0
            except Exception:
                pass
            doc = app.Documents.Open(str(src), ReadOnly=True, AddToRecentFiles=False)
            try:
                # 导出前尝试更新目录/页码域
                try:
                    doc.Fields.Update()
                except Exception:
                    pass
                try:
                    for toc in doc.TablesOfContents:
                        toc.Update()
                except Exception:
                    pass
                doc.SaveAs(str(dst), FileFormat=WD_FORMAT_PDF)
            finally:
                doc.Close(SaveChanges=False)
            app.Quit()
            if dst.exists() and dst.stat().st_size > 10_000:
                print(f"已生成 PDF：{dst}")
                print(f"  文件大小：{dst.stat().st_size / 1024:.0f} KB")
                return 0
            print(f"  {progid} 未产出有效 PDF，继续尝试下一个")
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"  {progid} 失败：{type(e).__name__}: {e}")
        finally:
            try:
                if app is not None:
                    app.Quit()
            except Exception:
                pass

    print(f"\n全部 COM 通道均失败。最后一次错误：{last_err}")
    print("说明：本机 Word/WPS 未注册或不可用。可改用 PyMuPDF 渲染方案。")
    return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Chuyển phiếu đăng ký Markdown sang DOCX (không cần pandoc).

Nguồn chính thức duy nhất: ``PHIEU_DANG_KY_DE_TAI.md`` → ``PHIEU_DANG_KY_DE_TAI.docx``.
Các phiên bản cũ được lưu trong ``archive/`` và không được script này xử lý.

Chỉ hỗ trợ tập con Markdown đang dùng trong Research/: heading, đoạn văn,
danh sách, bảng, in đậm/nghiêng, inline code, blockquote và đường kẻ ngang.
"""

import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

FONT = "Times New Roman"


def set_run_font(run, size, bold=False, mono=False):
    name = "Consolas" if mono else FONT
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = size
    run.bold = bold


def add_inline(paragraph, text, size, base_bold=False):
    """Tách **đậm** và `code` thành các run riêng."""
    for token in re.split(r"(\*\*.+?\*\*|`.+?`|\*[^*]+?\*)", text):
        if not token:
            continue
        if token.startswith("**") and token.endswith("**"):
            run = paragraph.add_run(token[2:-2])
            set_run_font(run, size, True)
        elif token.startswith("`") and token.endswith("`"):
            run = paragraph.add_run(token[1:-1])
            set_run_font(run, size, base_bold, mono=True)
        elif token.startswith("*") and token.endswith("*") and len(token) > 2:
            run = paragraph.add_run(token[1:-1])
            set_run_font(run, size, base_bold)
            run.italic = True
        else:
            run = paragraph.add_run(token)
            set_run_font(run, size, base_bold)


def add_bottom_border(paragraph):
    p_pr = paragraph._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "808080")
    borders.append(bottom)
    p_pr.append(borders)


def shade_cell(cell, color="E7E6E6"):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    tc_pr.append(shd)


def parse_table(lines, doc, size, avail_cm=None):
    rows = [
        [c.strip() for c in line.strip().strip("|").split("|")]
        for line in lines
    ]
    rows = [r for r in rows if not all(re.fullmatch(r":?-{2,}:?", c) for c in r if c)]
    if not rows:
        return
    ncols = max(len(r) for r in rows)
    table = doc.add_table(rows=len(rows), cols=ncols)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    # Bảng 2 cột (Mục | Nội dung) cần cột nội dung rộng; bảng khác để Word tự cân.
    widths = None
    if avail_cm and ncols == 2:
        widths = [min(4.2, avail_cm * 0.28), avail_cm - min(4.2, avail_cm * 0.28)]
        table.autofit = False
        table.allow_autofit = False
    for i, row in enumerate(rows):
        for j in range(ncols):
            cell = table.cell(i, j)
            text = row[j] if j < len(row) else ""
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_before = Pt(1)
            paragraph.paragraph_format.space_after = Pt(1)
            add_inline(paragraph, text, size, base_bold=(i == 0))
            if i == 0:
                shade_cell(cell)
            if widths:
                cell.width = Cm(widths[j])
    if widths:
        for j, width in enumerate(widths):
            table.columns[j].width = Cm(width)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def add_page_number(doc):
    """Thêm số trang ở footer (căn giữa), hỗ trợ bởi Word/LibreOffice."""
    for section in doc.sections:
        footer = section.footer
        paragraph = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)

        fld_begin = OxmlElement("w:fldChar")
        fld_begin.set(qn("w:fldCharType"), "begin")
        instr = OxmlElement("w:instrText")
        instr.set(qn("xml:space"), "preserve")
        instr.text = " PAGE "
        fld_end = OxmlElement("w:fldChar")
        fld_end.set(qn("w:fldCharType"), "end")

        run = paragraph.add_run()
        run._r.append(fld_begin)
        run._r.append(instr)
        run._r.append(fld_end)
        set_run_font(run, Pt(10))


def convert(md_path, docx_path, title=None, body_size=12, margin_cm=2.0, page_numbers=True):
    body = Pt(body_size)
    lines = md_path.read_text(encoding="utf-8").splitlines()
    doc = Document()

    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21.0)
    section.top_margin = Cm(margin_cm)
    section.bottom_margin = Cm(margin_cm)
    section.left_margin = Cm(margin_cm)
    section.right_margin = Cm(margin_cm)

    style = doc.styles["Normal"]
    style.font.name = FONT
    style.font.size = body
    style.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    style.paragraph_format.space_after = Pt(4)
    style.paragraph_format.line_spacing = 1.15

    if page_numbers:
        add_page_number(doc)

    i = 0
    while i < len(lines):
        stripped = lines[i].strip()

        if not stripped:
            i += 1
            continue

        if stripped == "---":
            add_bottom_border(doc.add_paragraph())
            i += 1
            continue

        if stripped.startswith("|"):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            avail_cm = 21.0 - 2 * (margin_cm + 0.2)
            parse_table(block, doc, Pt(max(body_size - 1.5, 8)), avail_cm=avail_cm)
            continue

        if stripped.startswith(">"):
            paragraph = doc.add_paragraph()
            paragraph.paragraph_format.left_indent = Cm(0.5)
            add_inline(paragraph, stripped.lstrip("> ").strip(), body)
            for run in paragraph.runs:
                run.italic = True
            i += 1
            continue

        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            text = stripped[level:].strip()
            paragraph = doc.add_paragraph()
            paragraph.paragraph_format.space_before = Pt(5 if level >= 2 else 0)
            paragraph.paragraph_format.space_after = Pt(2)
            if level == 1:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            size = body + Pt({1: 3.5, 2: 1.5, 3: 0.5}.get(level, 0))
            add_inline(paragraph, text, size, base_bold=True)
            i += 1
            continue

        match = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if match:
            add_inline(doc.add_paragraph(style="List Number"), match.group(2), body)
            i += 1
            continue

        if stripped.startswith("- "):
            add_inline(doc.add_paragraph(style="List Bullet"), stripped[2:], body)
            i += 1
            continue

        paragraph = doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        add_inline(paragraph, stripped, body)
        i += 1

    core = doc.core_properties
    core.title = title or md_path.stem
    core.author = "Nhóm 7"
    core.language = "vi-VN"

    doc.save(docx_path)
    print(f"Đã tạo {docx_path}")


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    jobs = [
        (
            base / "PHIEU_DANG_KY_DE_TAI.md",
            base / "PHIEU_DANG_KY_DE_TAI.docx",
            "Phiếu đăng ký đề tài nghiên cứu - Nhóm 7",
            12,
            2.0,
            True,
        ),
    ]
    for md_path, docx_path, title, body_size, margin_cm, page_numbers in jobs:
        if not md_path.exists():
            print(f"Bỏ qua (không có tệp): {md_path.name}")
            continue
        convert(
            md_path,
            docx_path,
            title,
            body_size=body_size,
            margin_cm=margin_cm,
            page_numbers=page_numbers,
        )

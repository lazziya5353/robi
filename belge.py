"""
Word (.docx) belgesi oluşturma: Robi'nin yazdığı markdown benzeri metni düzgün bir belgeye çevirir.
Desteklenen: # başlıklar, - / • / 1. listeler, | tablolar |, **kalın**, normal paragraflar.
"""
import re
from datetime import datetime
from pathlib import Path

ACCENT = (0x7C, 0x5C, 0xFF)  # Robi moru


def _runs(par, text):
    """**kalın** kısımları kalın yazar."""
    parts = re.split(r"(\*\*[^*]+\*\*)", text)
    for p in parts:
        if not p:
            continue
        if p.startswith("**") and p.endswith("**"):
            par.add_run(p[2:-2]).bold = True
        else:
            par.add_run(p)


def _table(doc, rows):
    from docx.shared import RGBColor, Pt
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    ncols = max(len(r) for r in rows)
    t = doc.add_table(rows=len(rows), cols=ncols)
    t.style = "Table Grid"
    for i, r in enumerate(rows):
        for j in range(ncols):
            cell = t.cell(i, j)
            cell.text = ""
            par = cell.paragraphs[0]
            _runs(par, r[j] if j < len(r) else "")
            for run in par.runs:
                run.font.size = Pt(10.5)
                if i == 0:
                    run.bold = True
                    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            if i == 0:  # başlık satırı mor zemin
                shd = OxmlElement("w:shd")
                shd.set(qn("w:val"), "clear")
                shd.set(qn("w:fill"), "%02X%02X%02X" % ACCENT)
                cell._tc.get_or_add_tcPr().append(shd)
            elif i % 2 == 0:
                shd = OxmlElement("w:shd")
                shd.set(qn("w:val"), "clear")
                shd.set(qn("w:fill"), "F3F1FF")
                cell._tc.get_or_add_tcPr().append(shd)
    doc.add_paragraph()


def olustur(baslik: str, icerik: str, path: Path):
    from docx import Document
    from docx.shared import Pt, RGBColor
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(11)

    h = doc.add_heading(baslik, level=0)
    for run in h.runs:
        run.font.color.rgb = RGBColor(*ACCENT)
    meta = doc.add_paragraph(datetime.now().strftime("%d.%m.%Y %H:%M") + " · Robi")
    meta.runs[0].font.size = Pt(9)
    meta.runs[0].font.color.rgb = RGBColor(0x88, 0x88, 0x99)

    lines = icerik.replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        s = line.strip()
        if not s:
            i += 1
            continue
        if s.startswith("|"):  # tablo bloğu
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = lines[i].strip()
                if not re.fullmatch(r"\|[\s:|-]+\|?", row):  # ayraç satırını atla
                    rows.append([c.strip() for c in row.strip("|").split("|")])
                i += 1
            if rows:
                _table(doc, rows)
            continue
        m = re.match(r"^(#{1,3})\s+(.*)", s)
        if m:
            hh = doc.add_heading(m.group(2).replace("**", ""), level=len(m.group(1)))
            for run in hh.runs:
                run.font.color.rgb = RGBColor(*ACCENT)
        elif re.match(r"^[-•*]\s+", s):
            _runs(doc.add_paragraph(style="List Bullet"), re.sub(r"^[-•*]\s+", "", s))
        elif re.match(r"^\d+[.)]\s+", s):
            _runs(doc.add_paragraph(style="List Number"), re.sub(r"^\d+[.)]\s+", "", s))
        else:
            _runs(doc.add_paragraph(), s)
        i += 1
    doc.save(str(path))

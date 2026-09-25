#!/usr/bin/env python3
"""Publish a Markdown report as .docx and .pdf alongside the .md.

Markdown is the source of truth, but it is unreadable outside an editor. Every
report in this repo therefore ships in all three formats.

  .md    source, easy to diff and regenerate
  .docx  Word — real heading styles, real tables, readable on a phone
  .pdf   fixed layout, one section per page

Usage:
    python analysis/publish.py                 # REPORT.md and ML_REPORT.md
    python analysis/publish.py SOMEFILE.md     # any markdown file
"""
import re
import sys
from pathlib import Path

import fitz
import markdown
from PIL import Image
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "analysis" / "figures" / "_pdf"
DEFAULTS = ["REPORT.md", "ML_REPORT.md"]

INK = RGBColor(0x1A, 0x1A, 0x1A)
H1 = RGBColor(0x0D, 0x36, 0x6B)
H2 = RGBColor(0x18, 0x4F, 0x95)
H3 = RGBColor(0x25, 0x6A, 0xBF)
CODE = RGBColor(0xA0, 0x38, 0x28)
MUTED = RGBColor(0x79, 0x84, 0x8A)

PDF_CSS = """
body { font-family: sans-serif; font-size: 9.5pt; color: #1a1a1a; line-height: 1.45; }
h1 { font-size: 19pt; color: #0d366b; margin-bottom: 1pt; }
h2 { font-size: 13pt; color: #184f95; margin-top: 0pt; margin-bottom: 4pt; }
h3 { font-size: 10.5pt; color: #256abf; margin-top: 9pt; margin-bottom: 2pt; }
p  { margin-top: 3pt; margin-bottom: 3pt; }
code { font-family: monospace; font-size: 8.5pt; color: #a03828; }
pre  { font-family: monospace; font-size: 8pt; }
blockquote { color: #454f53; margin-left: 10pt; }
table { font-size: 8.5pt; margin-top: 4pt; margin-bottom: 6pt; }
th { text-align: left; padding: 2pt 7pt 3pt 0pt; font-size: 8pt; color: #184f95;
     border-bottom: 1px solid #9ec5f4; }
td { padding: 2pt 7pt 2pt 0pt; border-bottom: 1px solid #ecefec; }
li { margin-top: 1pt; margin-bottom: 1pt; }
"""

INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\*[^*]+\*)")


# ------------------------------------------------------------------ shared
def shrink(rel, max_w=1500):
    """Downsample a figure. Full-res PNGs produced a 19.6 MB PDF."""
    TMP.mkdir(parents=True, exist_ok=True)
    src = ROOT / rel
    dst = TMP / (Path(rel).stem + ".jpg")
    with Image.open(src) as im:
        im = im.convert("RGB")
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        im.save(dst, "JPEG", quality=84, optimize=True)
        return dst, im.width, im.height


def blocks(md_text):
    """Split markdown into (kind, payload) blocks."""
    out, lines, i = [], md_text.splitlines(), 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            buf, i = [], i + 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i]); i += 1
            out.append(("code", "\n".join(buf))); i += 1
        elif ln.startswith("#"):
            lvl = len(ln) - len(ln.lstrip("#"))
            out.append(("h", (lvl, ln.lstrip("# ").strip()))); i += 1
        elif ln.strip().startswith("|") and i + 1 < len(lines) and set(
                lines[i + 1].replace("|", "").replace(" ", "")) <= {"-", ":"}:
            tbl, = [[]],
            tbl = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                tbl.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            out.append(("table", [r for r in tbl
                                  if not set("".join(r).replace(" ", "")) <= {"-", ":"}]))
        elif ln.strip().startswith("!["):
            m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", ln.strip())
            out.append(("img", m.group(2)) if m else ("p", ln)); i += 1
        elif ln.strip().startswith(("- ", "* ")):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(("- ", "* ")):
                buf.append(lines[i].strip()[2:]); i += 1
            out.append(("ul", buf))
        elif re.match(r"^\d+\. ", ln.strip()):
            buf = []
            while i < len(lines) and re.match(r"^\d+\. ", lines[i].strip()):
                buf.append(re.sub(r"^\d+\. ", "", lines[i].strip())); i += 1
            out.append(("ol", buf))
        elif ln.strip().startswith(">"):
            out.append(("quote", ln.strip().lstrip("> "))); i += 1
        elif not ln.strip():
            i += 1
        else:
            buf = []
            while i < len(lines) and lines[i].strip() and not lines[i].startswith(
                    ("#", "|", "```", "- ", "* ", ">")) and not lines[i].strip().startswith("!["):
                buf.append(lines[i].strip()); i += 1
            out.append(("p", " ".join(buf)))
    return out


# ------------------------------------------------------------------ docx
def add_runs(par, text):
    """Inline **bold**, `code` and *italic*."""
    for piece in INLINE.split(text):
        if not piece:
            continue
        if piece.startswith("**") and piece.endswith("**"):
            r = par.add_run(piece[2:-2]); r.bold = True
        elif piece.startswith("`") and piece.endswith("`"):
            r = par.add_run(piece[1:-1]); r.font.name = "Consolas"
            r.font.size = Pt(9); r.font.color.rgb = CODE
        elif piece.startswith("*") and piece.endswith("*") and len(piece) > 2:
            r = par.add_run(piece[1:-1]); r.italic = True
        else:
            par.add_run(piece)


def to_docx(md_path, dest):
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"; st.font.size = Pt(10.5)

    for kind, payload in blocks(md_path.read_text(encoding="utf-8")):
        if kind == "h":
            lvl, text = payload
            p = doc.add_heading(level=min(lvl, 4))
            p.runs.clear() if p.runs else None
            r = p.add_run(re.sub(r"[*`]", "", text))
            r.font.color.rgb = {1: H1, 2: H2, 3: H3}.get(lvl, H3)
            r.font.size = Pt({1: 20, 2: 14, 3: 11.5}.get(lvl, 11))
            # keep_with_next stops a heading stranding at the foot of a page;
            # a forced page_break_before left pages with two lines on them.
            p.paragraph_format.keep_with_next = True
            p.paragraph_format.space_before = Pt(14 if lvl <= 2 else 10)
        elif kind == "p":
            add_runs(doc.add_paragraph(), payload)
        elif kind == "quote":
            p = doc.add_paragraph(); p.paragraph_format.left_indent = Inches(0.3)
            add_runs(p, payload)
            for r in p.runs:
                r.italic = True
        elif kind == "ul":
            for item in payload:
                add_runs(doc.add_paragraph(style="List Bullet"), item)
        elif kind == "ol":
            for item in payload:
                add_runs(doc.add_paragraph(style="List Number"), item)
        elif kind == "code":
            p = doc.add_paragraph()
            r = p.add_run(payload)
            r.font.name = "Consolas"; r.font.size = Pt(8.5)
            p.paragraph_format.left_indent = Inches(0.2)
        elif kind == "table":
            if not payload:
                continue
            t = doc.add_table(rows=len(payload), cols=len(payload[0]))
            t.style = "Light Grid Accent 1"
            t.alignment = WD_TABLE_ALIGNMENT.LEFT
            for ri, row in enumerate(payload):
                for ci, cell in enumerate(row):
                    if ci >= len(t.columns):
                        continue
                    c = t.cell(ri, ci)
                    c.text = ""
                    par = c.paragraphs[0]
                    add_runs(par, cell)
                    for r in par.runs:
                        r.font.size = Pt(9)
                        if ri == 0:
                            r.bold = True
            doc.add_paragraph()
        elif kind == "img":
            src = ROOT / payload
            if src.exists():
                jpg, w, h = shrink(payload, 1400)
                doc.add_picture(str(jpg), width=Inches(6.2))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.save(dest)
    return dest


# ------------------------------------------------------------------ pdf
def to_pdf(md_path, dest):
    text = md_path.read_text(encoding="utf-8")

    def img_tag(m):
        rel = m.group(2)
        if not (ROOT / rel).exists():
            return ""
        jpg, w, h = shrink(rel)
        width = 470
        return (f'<p><img src="{jpg.relative_to(ROOT).as_posix()}" width="{width}" '
                f'height="{round(h * width / w)}"/></p>')

    # One chunk per heading, but chunks FLOW down the page. A new page starts
    # only when the next section will not fit in the space that is left --
    # forcing a break at every heading left pages holding two lines.
    parts = [c for c in re.split(r"\n(?=#{2,3} )", text) if c.strip()]

    writer = fitz.DocumentWriter(str(dest))
    rect = fitz.paper_rect("a4")
    area = rect + (52, 50, -52, -54)
    arch = fitz.Archive(ROOT)
    GAP = 10

    def story_for(chunk):
        body = markdown.markdown(re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", img_tag, chunk),
                                 extensions=["tables", "fenced_code"])
        return fitz.Story(html=f"<html><head><style>{PDF_CSS}</style></head>"
                               f"<body>{body}</body></html>", archive=arch)

    # Pages are opened lazily and only closed once something has been drawn on
    # them, so the document never ends on a blank page.
    pages, dev, cursor = 0, None, area.y0

    def open_page():
        nonlocal dev, pages, cursor
        dev = writer.begin_page(rect)
        pages += 1
        cursor = area.y0

    def close_page():
        nonlocal dev
        if dev is not None:
            writer.end_page()
            dev = None

    for chunk in parts:
        story = story_for(chunk)
        if dev is None:
            open_page()
        room = fitz.Rect(area.x0, cursor, area.x1, area.y1)
        # place() consumes a Story, so probe with a throwaway copy
        probe_more, _ = story_for(chunk).place(room)
        if probe_more and cursor > area.y0:       # will not fit in what is left
            close_page()
            open_page()
            room = fitz.Rect(area.x0, cursor, area.x1, area.y1)

        more, filled = story.place(room)
        story.draw(dev)
        cursor = fitz.Rect(filled).y1 + GAP
        guard = 0
        while more and guard < 12:                # section longer than a page
            close_page()
            open_page()
            more, filled = story.place(area)
            story.draw(dev)
            cursor = fitz.Rect(filled).y1 + GAP
            guard += 1
        if cursor > area.y1 - 40:                 # no useful room left
            close_page()

    close_page()
    writer.close()
    return dest, pages


def main():
    targets = sys.argv[1:] or DEFAULTS
    for name in targets:
        md = ROOT / name
        if not md.exists():
            print(f"  skip {name} (not found)")
            continue
        docx = to_docx(md, ROOT / (md.stem + ".docx"))
        pdf, pages = to_pdf(md, ROOT / (md.stem + ".pdf"))
        print(f"{md.name}")
        print(f"   -> {docx.name}  ({docx.stat().st_size/1024:.0f} KB)")
        print(f"   -> {pdf.name}  ({pages} pages, {pdf.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()

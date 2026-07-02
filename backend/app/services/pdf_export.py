"""Small Markdown-to-PDF renderer used by report exports."""
from io import BytesIO
from pathlib import Path
import re

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


def _register_font() -> str:
    name = "ScopePilotUnicode"
    if name in pdfmetrics.getRegisteredFontNames():
        return name
    candidates = (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/PingFang.ttc"),
    )
    for path in candidates:
        if not path.exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont(name, str(path)))
            return name
        except Exception:
            continue
    return "Helvetica"


def _plain_text(value: str) -> str:
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"\1", value)
    return value


def markdown_to_pdf(content: str, title: str) -> bytes:
    """Render readable report text into a paginated PDF."""
    buffer = BytesIO()
    width, height = A4
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(title)
    font_name = _register_font()
    margin = 48
    y = height - margin

    def new_page() -> None:
        nonlocal y
        pdf.showPage()
        y = height - margin

    def draw_wrapped(text: str, font_size: int, indent: int = 0, leading: int = 0) -> None:
        nonlocal y
        leading = leading or int(font_size * 1.55)
        available = width - margin * 2 - indent
        words = list(text) if any("\u4e00" <= char <= "\u9fff" for char in text) else text.split(" ")
        separator = "" if words and len(words[0]) == 1 else " "
        current = ""
        lines: list[str] = []
        for word in words:
            candidate = f"{current}{separator if current else ''}{word}"
            if pdfmetrics.stringWidth(candidate, font_name, font_size) <= available:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        for line in lines or [""]:
            if y < margin + leading:
                new_page()
            pdf.setFont(font_name, font_size)
            pdf.drawString(margin + indent, y, line)
            y -= leading

    for raw_line in content.splitlines():
        line = _plain_text(raw_line.strip())
        if not line:
            y -= 7
            continue
        if line.startswith("# "):
            draw_wrapped(line[2:], 18, leading=26)
        elif line.startswith("## "):
            y -= 5
            draw_wrapped(line[3:], 14, leading=22)
        elif line.startswith("### "):
            draw_wrapped(line[4:], 12, leading=19)
        elif re.match(r"^\d+\.\s", line):
            draw_wrapped(line, 10, indent=12, leading=16)
        elif line.startswith(("- ", "* ")):
            draw_wrapped(f"• {line[2:]}", 10, indent=12, leading=16)
        elif line == "---":
            y -= 10
        else:
            draw_wrapped(line, 10, leading=16)

    pdf.save()
    buffer.seek(0)
    return buffer.read()

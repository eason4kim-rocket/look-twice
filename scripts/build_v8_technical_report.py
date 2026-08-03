#!/usr/bin/env python3
"""Render the English V8 technical report as a judge-ready PDF."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


INK = colors.HexColor("#111718")
INK_SOFT = colors.HexColor("#263033")
PAPER = colors.HexColor("#F4F2EC")
PAPER_RAISED = colors.HexColor("#FBFAF6")
MUTED = colors.HexColor("#657071")
CYAN = colors.HexColor("#18AAA7")
CYAN_BRIGHT = colors.HexColor("#29CEC8")
GREEN = colors.HexColor("#79CF67")
AMBER = colors.HexColor("#E6A83D")
LINE = colors.HexColor("#D7D5CF")
WHITE = colors.HexColor("#EDF2EF")


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=root / "docs" / "V8_TECHNICAL_REPORT.md",
    )
    parser.add_argument(
        "--poster",
        type=Path,
        default=root / "showcase" / "public" / "media" / "look-twice-replay-30s.poster.webp",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "output" / "pdf" / "Look-Twice-V8-Technical-Report.pdf",
    )
    return parser.parse_args()


def register_fonts() -> None:
    candidates = {
        "LTBody": [
            Path("/System/Library/Fonts/Supplemental/Verdana.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ],
        "LTBodyBold": [
            Path("/System/Library/Fonts/Supplemental/Verdana Bold.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ],
        "LTMono": [
            Path("/System/Library/Fonts/SFNSMono.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
        ],
    }
    for font_name, paths in candidates.items():
        font_path = next((path for path in paths if path.is_file()), None)
        if font_path is None:
            raise RuntimeError(f"no usable font found for {font_name}")
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))


def make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "cover_label": ParagraphStyle(
            "CoverLabel",
            parent=base["Normal"],
            fontName="LTMono",
            fontSize=8.5,
            leading=11,
            textColor=CYAN_BRIGHT,
            spaceAfter=8,
        ),
        "cover_title": ParagraphStyle(
            "CoverTitle",
            parent=base["Title"],
            fontName="LTBodyBold",
            fontSize=31,
            leading=34,
            textColor=WHITE,
            alignment=TA_LEFT,
            spaceAfter=10,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle",
            parent=base["Normal"],
            fontName="LTBody",
            fontSize=11,
            leading=16,
            textColor=colors.HexColor("#B8C4C4"),
            spaceAfter=14,
        ),
        "cover_meta": ParagraphStyle(
            "CoverMeta",
            parent=base["Normal"],
            fontName="LTMono",
            fontSize=7.2,
            leading=10,
            textColor=colors.HexColor("#91A0A1"),
        ),
        "h1": ParagraphStyle(
            "BodyH1",
            parent=base["Heading1"],
            fontName="LTBodyBold",
            fontSize=20,
            leading=24,
            textColor=INK,
            spaceBefore=15,
            spaceAfter=8,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "BodyH2",
            parent=base["Heading2"],
            fontName="LTBodyBold",
            fontSize=13,
            leading=17,
            textColor=CYAN,
            spaceBefore=11,
            spaceAfter=6,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="LTBody",
            fontSize=8.3,
            leading=12.4,
            textColor=INK_SOFT,
            spaceAfter=6.5,
            allowWidows=0,
            allowOrphans=0,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName="LTBody",
            fontSize=8.1,
            leading=12,
            textColor=INK_SOFT,
            leftIndent=13,
            firstLineIndent=-8,
            bulletIndent=2,
            spaceAfter=3.5,
        ),
        "code": ParagraphStyle(
            "Code",
            parent=base["Code"],
            fontName="LTMono",
            fontSize=6.7,
            leading=9.2,
            textColor=colors.HexColor("#CFE9E6"),
            backColor=INK,
            borderColor=INK,
            borderWidth=0.5,
            borderPadding=8,
            leftIndent=0,
            rightIndent=0,
            spaceBefore=3,
            spaceAfter=8,
        ),
        "table": ParagraphStyle(
            "TableCell",
            parent=base["BodyText"],
            fontName="LTBody",
            fontSize=7,
            leading=9.6,
            textColor=INK_SOFT,
        ),
        "table_head": ParagraphStyle(
            "TableHead",
            parent=base["BodyText"],
            fontName="LTBodyBold",
            fontSize=6.8,
            leading=9,
            textColor=WHITE,
        ),
    }


def inline_markup(text: str) -> str:
    value = escape(text.strip())
    value = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r'<a href="\2" color="#087F7C"><u>\1</u></a>',
        value,
    )
    value = re.sub(
        r"(?<![\w\"=])(https?://[^\s<]+)",
        r'<a href="\1" color="#087F7C"><u>\1</u></a>',
        value,
    )
    value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)
    value = re.sub(
        r"`([^`]+)`",
        r'<font name="LTMono" color="#087F7C" size="7.2">\1</font>',
        value,
    )
    return value


def table_from_markdown(
    rows: list[str],
    styles: dict[str, ParagraphStyle],
    available_width: float,
) -> Table:
    parsed = [
        [cell.strip() for cell in row.strip().strip("|").split("|")]
        for row in rows
    ]
    if len(parsed) > 1 and all(re.fullmatch(r":?-{3,}:?", cell) for cell in parsed[1]):
        parsed.pop(1)
    column_count = len(parsed[0])
    if column_count == 2:
        col_widths = [available_width * 0.38, available_width * 0.62]
    elif column_count == 3:
        col_widths = [available_width * 0.28, available_width * 0.28, available_width * 0.44]
    else:
        col_widths = [available_width / column_count] * column_count
    data: list[list[Paragraph]] = []
    for row_index, row in enumerate(parsed):
        style = styles["table_head"] if row_index == 0 else styles["table"]
        data.append([Paragraph(inline_markup(cell), style) for cell in row])
    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("BACKGROUND", (0, 1), (-1, -1), PAPER_RAISED),
                ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def markdown_story(
    markdown: str,
    styles: dict[str, ParagraphStyle],
    available_width: float,
) -> list[object]:
    lines = markdown.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if line.startswith("## Executive summary")),
        0,
    )
    lines = lines[start:]
    story: list[object] = []
    index = 0
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_lines:
            story.append(
                Paragraph(inline_markup(" ".join(paragraph_lines)), styles["body"])
            )
            paragraph_lines.clear()

    while index < len(lines):
        line = lines[index].rstrip()
        if not line:
            flush_paragraph()
            index += 1
            continue
        if line.startswith("```"):
            flush_paragraph()
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                code_lines.append(lines[index].rstrip())
                index += 1
            story.append(
                Paragraph(
                    escape("\n".join(code_lines)).replace("\n", "<br/>"),
                    styles["code"],
                )
            )
            index += 1
            continue
        if line.startswith("|"):
            flush_paragraph()
            table_lines: list[str] = []
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                table_lines.append(lines[index])
                index += 1
            story.append(table_from_markdown(table_lines, styles, available_width))
            story.append(Spacer(1, 7))
            continue
        heading = re.match(r"^(##|###)\s+(.+)$", line)
        if heading:
            flush_paragraph()
            story.append(
                Paragraph(
                    inline_markup(heading.group(2)),
                    styles["h1" if heading.group(1) == "##" else "h2"],
                )
            )
            index += 1
            continue
        bullet = re.match(r"^-\s+(.+)$", line)
        numbered = re.match(r"^(\d+)\.\s+(.+)$", line)
        if bullet or numbered:
            flush_paragraph()
            marker = "•" if bullet else f"{numbered.group(1)}."
            content = bullet.group(1) if bullet else numbered.group(2)
            # Fold indented continuation lines into the current item.
            index += 1
            while index < len(lines) and re.match(r"^\s{2,}\S", lines[index]):
                content += " " + lines[index].strip()
                index += 1
            story.append(
                Paragraph(inline_markup(content), styles["bullet"], bulletText=marker)
            )
            continue
        paragraph_lines.append(line.strip())
        index += 1
    flush_paragraph()
    return story


def draw_cover(canvas, doc) -> None:  # type: ignore[no-untyped-def]
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(INK)
    canvas.rect(0, 0, width, height, stroke=0, fill=1)
    canvas.setFillColor(CYAN)
    canvas.rect(0, height - 8 * mm, width, 8 * mm, stroke=0, fill=1)
    canvas.setFillColor(CYAN_BRIGHT)
    canvas.circle(width - 24 * mm, height - 24 * mm, 2.4 * mm, stroke=0, fill=1)
    canvas.circle(width - 16 * mm, height - 24 * mm, 2.4 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.HexColor("#91A0A1"))
    canvas.setFont("LTMono", 6.5)
    canvas.drawString(20 * mm, 11 * mm, "LOOK TWICE · V8 FROZEN · TRACK 3 PHYSICAL AI")
    canvas.drawRightString(width - 20 * mm, 11 * mm, "2026-08-03")
    canvas.restoreState()


def draw_body(canvas, doc) -> None:  # type: ignore[no-untyped-def]
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(PAPER)
    canvas.rect(0, 0, width, height, stroke=0, fill=1)
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, height - 14 * mm, width - 18 * mm, height - 14 * mm)
    canvas.line(18 * mm, 13 * mm, width - 18 * mm, 13 * mm)
    canvas.setFont("LTBodyBold", 6.4)
    canvas.setFillColor(INK)
    canvas.drawString(18 * mm, height - 10 * mm, "LOOK TWICE V8")
    canvas.setFont("LTMono", 6.2)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(width - 18 * mm, height - 10 * mm, "AMD AI DEVMASTER · TRACK 3")
    canvas.drawString(18 * mm, 8 * mm, "ACTIVE EVIDENCE ASSURANCE FOR PHYSICAL AI")
    canvas.drawRightString(width - 18 * mm, 8 * mm, f"{doc.page}")
    canvas.restoreState()


def build_cover(
    styles: dict[str, ParagraphStyle], poster: Path, available_width: float
) -> list[object]:
    metric_style = ParagraphStyle(
        "CoverMetric",
        parent=styles["cover_meta"],
        fontName="LTBodyBold",
        fontSize=13,
        leading=15,
        textColor=CYAN_BRIGHT,
    )
    metric_label_style = ParagraphStyle(
        "CoverMetricLabel",
        parent=styles["cover_meta"],
        fontSize=5.8,
        leading=8,
        textColor=colors.HexColor("#91A0A1"),
    )
    metric_data = [[
        Paragraph("3,200<br/><font size=\"5.8\" color=\"#91A0A1\">LOCKED SAMPLES</font>", metric_style),
        Paragraph("11 / 12<br/><font size=\"5.8\" color=\"#91A0A1\">ACTIVE DIRECT</font>", metric_style),
        Paragraph("0 / 24<br/><font size=\"5.8\" color=\"#91A0A1\">UNSAFE CROSSINGS</font>", metric_style),
        Paragraph("EP 22<br/><font size=\"5.8\" color=\"#91A0A1\">FROZEN MODEL</font>", metric_style),
    ]]
    metrics = Table(metric_data, colWidths=[available_width / 4] * 4)
    metrics.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#172023")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#334044")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#334044")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    items: list[object] = [
        Spacer(1, 18 * mm),
        Paragraph("AMD AI DEVMASTER HACKATHON 2026 · TRACK 3", styles["cover_label"]),
        Paragraph("Look Twice V8", styles["cover_title"]),
        Paragraph(
            "Active Evidence Assurance for Physical AI<br/>"
            "Technical Report · Frozen Competition Candidate",
            styles["cover_subtitle"],
        ),
    ]
    if poster.is_file():
        image = Image(str(poster), width=available_width, height=available_width * 9 / 16)
        items.extend([image, Spacer(1, 8)])
    items.extend(
        [
            metrics,
            Spacer(1, 9),
            Paragraph(
                "Entrant / team: Liu Liang (solo) · Candidate: v8-frozen · "
                "Apache-2.0 · Simulation only · English submission",
                styles["cover_meta"],
            ),
            PageBreak(),
        ]
    )
    return items


def main() -> int:
    args = parse_args()
    if not args.input.is_file():
        raise SystemExit(f"report source not found: {args.input}")
    register_fonts()
    styles = make_styles()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(args.output),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
        title="Look Twice V8: Active Evidence Assurance for Physical AI",
        author="Liu Liang",
        subject="AMD AI DevMaster Hackathon 2026, Track 3 technical report",
        creator="Look Twice submission report builder",
    )
    available_width = A4[0] - document.leftMargin - document.rightMargin
    story = build_cover(styles, args.poster, available_width)
    story.extend(
        markdown_story(
            args.input.read_text(encoding="utf-8"),
            styles,
            available_width,
        )
    )
    document.build(story, onFirstPage=draw_cover, onLaterPages=draw_body)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

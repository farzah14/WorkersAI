from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import CandidateSummary, ExportRow, SearchCriteria

_ACCENT = colors.HexColor("#d9623c")
_INK = colors.HexColor("#15212b")
_BODY = colors.HexColor("#53616a")
_MUTED = colors.HexColor("#6d787e")
_GREEN = colors.HexColor("#1f6b59")
_RED = colors.HexColor("#9b351c")


def _safe(text: object) -> str:
    return escape(str(text))


def _link(url: str, label: str) -> str:
    return f'<link href="{escape(url)}">{escape(label)}</link>'


def _now() -> datetime:
    return datetime.now(UTC)


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            name="ReportTitle",
            parent=base["Title"],
            textColor=_INK,
            fontSize=22,
            leading=26,
            spaceAfter=2,
        ),
        "sub": ParagraphStyle(
            name="ReportSub",
            parent=base["BodyText"],
            textColor=_MUTED,
            fontSize=8.5,
            leading=11,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            name="ReportH2",
            parent=base["Heading2"],
            textColor=_INK,
            fontSize=13,
            leading=16,
            spaceBefore=12,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            name="ReportBody",
            parent=base["BodyText"],
            textColor=_BODY,
            fontSize=9.5,
            leading=13,
        ),
        "muted": ParagraphStyle(
            name="ReportMuted",
            parent=base["BodyText"],
            textColor=_MUTED,
            fontSize=8.5,
            leading=11,
        ),
        "cell": ParagraphStyle(
            name="ReportCell",
            parent=base["BodyText"],
            textColor=_INK,
            fontSize=8.5,
            leading=11,
        ),
        "cell_header": ParagraphStyle(
            name="ReportCellHeader",
            parent=base["BodyText"],
            textColor=colors.white,
            fontSize=8.5,
            leading=11,
        ),
    }


def _bullets(values: list[str], color: colors.Color | None = None) -> str:
    if not values:
        return ""
    joined = "<br/>".join(f"• {_safe(v)}" for v in values)
    return f'<font color="{color.hexval()}">{joined}</font>' if color else joined


def build_pdf_bytes(
    rows: list[ExportRow],
    candidate: CandidateSummary,
    criteria: SearchCriteria,
    generated_at: datetime | None = None,
) -> bytes:
    s = _styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="Job Match Report",
    )
    story: list = []

    story.append(Paragraph("Job Match Report", s["title"]))
    story.append(Paragraph((generated_at or _now()).strftime("%Y-%m-%d %H:%M UTC"), s["sub"]))

    story.append(Paragraph("Candidate Summary", s["h2"]))
    story.append(Paragraph(f"<b>{_safe(candidate.name)}</b>", s["body"]))
    if candidate.headline:
        story.append(Paragraph(_safe(candidate.headline), s["body"]))
    if candidate.years_experience is not None:
        story.append(Paragraph(f"Years of experience: {candidate.years_experience}", s["body"]))
    if candidate.location:
        story.append(Paragraph(f"Location: {_safe(candidate.location)}", s["body"]))
    if candidate.skills:
        story.append(Paragraph(f"Skills: {_safe(', '.join(candidate.skills))}", s["body"]))
    if candidate.languages:
        story.append(Paragraph(f"Languages: {_safe(', '.join(candidate.languages))}", s["body"]))

    story.append(Paragraph("Search Criteria", s["h2"]))
    criteria_lines = [f"Scope: {criteria.scope}"]
    if criteria.region:
        criteria_lines.append(f"Region: {_safe(', '.join(criteria.region))}")
    if criteria.work_mode:
        criteria_lines.append(f"Work mode: {_safe(', '.join(criteria.work_mode))}")
    if criteria.min_score is not None:
        criteria_lines.append(f"Minimum score: {criteria.min_score}")
    if criteria.status:
        criteria_lines.append(f"Status: {_safe(', '.join(criteria.status))}")
    if criteria.date_from:
        criteria_lines.append(f"Date from: {criteria.date_from.isoformat()}")
    if criteria.date_to:
        criteria_lines.append(f"Date to: {criteria.date_to.isoformat()}")
    for line in criteria_lines:
        story.append(Paragraph(line, s["body"]))

    story.append(Paragraph("Aggregate Stats", s["h2"]))
    if rows:
        average = sum(r.overall_score for r in rows) / len(rows)
        best = sum(1 for r in rows if r.overall_score >= 90)
        strong = sum(1 for r in rows if 80 <= r.overall_score < 90)
    else:
        average = 0.0
        best = 0
        strong = 0
    for line in (
        f"Matches exported: {len(rows)}",
        f"Average match score: {average:.1f}",
        f"Best matches: {best}",
        f"Strong matches: {strong}",
    ):
        story.append(Paragraph(line, s["body"]))

    story.append(Paragraph("Top Matches", s["h2"]))
    if rows:
        header = [Paragraph(h, s["cell_header"]) for h in ("Job Title", "Company", "Score", "Job URL")]
        table_rows = [header]
        for row in rows[:10]:
            table_rows.append(
                [
                    Paragraph(_safe(row.job_title), s["cell"]),
                    Paragraph(_safe(row.company), s["cell"]),
                    Paragraph(str(row.overall_score), s["cell"]),
                    Paragraph(_link(row.original_url, "Open"), s["cell"]),
                ]
            )
        top = Table(table_rows, colWidths=[70 * mm, 50 * mm, 20 * mm, 34 * mm])
        top.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), _INK),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d9d5cc")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f4ee")]),
                ]
            )
        )
        story.append(top)
    else:
        story.append(Paragraph("No matches matched the export criteria.", s["body"]))

    story.append(Paragraph("Match Details", s["h2"]))
    for row in rows:
        story.append(Paragraph(_safe(row.job_title), s["cell"]))
        story.append(Paragraph(_link(row.original_url, "Open job listing"), s["muted"]))
        meta = " · ".join(
            part
            for part in (
                _safe(row.company),
                _safe(row.location or ""),
                _safe(row.work_mode or ""),
                _safe(row.employment_type or ""),
            )
            if part
        )
        if meta:
            story.append(Paragraph(meta, s["muted"]))
        story.append(Paragraph(f"Overall match: <b>{row.overall_score}</b>", s["body"]))
        dimensions = (
            f"Skills {row.skills_score} · Experience {row.experience_score} · "
            f"Seniority {row.seniority_score} · Education {row.education_score} · "
            f"Language {row.language_score} · Location {row.location_score}"
        )
        story.append(Paragraph(dimensions, s["muted"]))
        if row.strengths:
            story.append(Paragraph(f"<b>Strengths:</b> {_safe(', '.join(row.strengths))}", s["body"]))
        if row.critical_gaps:
            story.append(
                Paragraph(
                    f"<b>Critical gaps:</b> <font color='{_RED.hexval()}'>{_safe(', '.join(row.critical_gaps))}</font>",
                    s["body"],
                )
            )
        if row.gaps:
            story.append(Paragraph(f"<b>Gaps:</b> {_safe(', '.join(row.gaps))}", s["body"]))
        if row.recommendations:
            story.append(
                Paragraph(
                    f"<b>Recommendation:</b> {_safe(row.recommendations[0])}",
                    s["body"],
                )
            )
        story.append(Spacer(1, 4))

    doc.build(story)
    return buffer.getvalue()
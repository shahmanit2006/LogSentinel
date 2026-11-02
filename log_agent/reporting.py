"""Create downloadable incident reports and retain local copies."""
import json
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape


def _markdown(report):
    lines = [
        "# AI Log Investigation Report", "",
        f"**Generated:** {report.get('generated_at', datetime.now().isoformat(timespec='seconds'))}", "",
        f"**Question:** {report.get('question', '')}", "",
        "## Investigation", "", report.get("summary", "No summary available."), "",
        "## Retrieved evidence", "",
    ]
    evidence = report.get("evidence", [])
    if evidence:
        for item in evidence:
            lines.append(
                f"- **[{item.get('simulation_time', item.get('timestamp', 'unknown time'))}] {item.get('level', 'UNKNOWN')} / "
                f"{item.get('component', 'unknown')}** — {item.get('message', '')} "
                f"({item.get('source', '')}:{item.get('line_no', '')})"
            )
    else:
        lines.append("No evidence was retrieved.")
    lines += ["", "## Incident timeline", ""]
    for item in report.get("timeline", []):
        time_value = item.get("simulation_time", item.get("timestamp"))
        lines.append(f"- [{time_value}] {item.get('level')} / {item.get('component')}: {item.get('message')}")
    lines += ["", "## Statistics", "", "```json", json.dumps(report.get("statistics", {}), indent=2, default=str), "```", ""]
    return "\n".join(lines)


def _pdf_bytes(report):
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=17*mm, leftMargin=17*mm, topMargin=16*mm, bottomMargin=16*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], textColor=colors.HexColor("#18345b"), alignment=TA_LEFT, fontSize=20, leading=24, spaceAfter=8))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], textColor=colors.HexColor("#2458a6"), fontSize=12, leading=15, spaceBefore=12, spaceAfter=6))
    styles.add(ParagraphStyle(name="BodySmall", parent=styles["BodyText"], fontSize=8.5, leading=12, spaceAfter=5, wordWrap="CJK"))
    story = [Paragraph("AI Log Investigation Report", styles["ReportTitle"]),
             Paragraph(f"<b>Generated:</b> {escape(str(report.get('generated_at', datetime.now().isoformat(timespec='seconds'))))}", styles["BodySmall"]),
             Paragraph(f"<b>Question:</b> {escape(str(report.get('question', '')))}", styles["BodySmall"]),
             Paragraph("Investigation", styles["Section"])]
    for para in str(report.get("summary", "No summary available.")).split("\n"):
        if para.strip():
            story.append(Paragraph(escape(para), styles["BodySmall"]))
        else:
            story.append(Spacer(1, 3))
    story.append(Paragraph("Retrieved evidence", styles["Section"]))
    rows = [["Time", "Level", "Component", "Evidence / message"]]
    for item in report.get("evidence", [])[:35]:
        rows.append([
            escape(str(item.get("simulation_time", item.get("timestamp", ""))))[:24],
            escape(str(item.get("level", ""))),
            escape(str(item.get("component", ""))),
            escape(str(item.get("message", "")))[:240],
        ])
    if len(rows) == 1:
        rows.append(["—", "—", "—", "No evidence retrieved"])
    table = Table(rows, colWidths=[32*mm, 18*mm, 25*mm, 100*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#18345b")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 7),
        ("LEADING", (0,0), (-1,-1), 9),
        ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#d9e1ec")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f3f6fb")]),
        ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(table)
    story.append(Paragraph("Incident timeline", styles["Section"]))
    for item in report.get("timeline", [])[:50]:
        line = f"[{item.get('simulation_time', item.get('timestamp'))}] {item.get('level')} / {item.get('component')}: {item.get('message')}"
        story.append(Paragraph(escape(str(line)), styles["BodySmall"]))
    doc.build(story)
    return buffer.getvalue()


def build_report_files(report):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_report = dict(report)
    safe_report.setdefault("generated_at", datetime.now().isoformat(timespec="seconds"))
    json_bytes = json.dumps(safe_report, indent=2, ensure_ascii=False, default=str).encode("utf-8")
    markdown_bytes = _markdown(safe_report).encode("utf-8")
    pdf = _pdf_bytes(safe_report)
    return {
        "json": json_bytes,
        "markdown": markdown_bytes,
        "pdf": pdf,
        "json_name": f"incident_report_{stamp}.json",
        "markdown_name": f"incident_report_{stamp}.md",
        "pdf_name": f"incident_report_{stamp}.pdf",
    }


def save_report_files(report, output_dir="output_report"):
    files = build_report_files(report)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for key, name_key in (("json", "json_name"), ("markdown", "markdown_name"), ("pdf", "pdf_name")):
        path = out / files[name_key]
        path.write_bytes(files[key])
        paths.append(path)
    return tuple(paths)

# Backwards-compatible function name for earlier project versions.
def save_report(report, output_dir="output_report"):
    return save_report_files(report, output_dir)

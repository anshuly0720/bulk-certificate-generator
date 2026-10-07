from datetime import date
from pathlib import Path

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


def render_certificate(path: Path, *, name: str, course_name: str, issuer: str,
                       issue_date: date, certificate_id: str) -> None:
    width, height = landscape(A4)
    c = canvas.Canvas(str(path), pagesize=(width, height))
    c.setTitle(f"Certificate - {name}")

    # double border
    c.setLineWidth(3)
    c.rect(36, 36, width - 72, height - 72)
    c.setLineWidth(1)
    c.rect(46, 46, width - 92, height - 92)

    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(width / 2, height - 150, "Certificate of Completion")
    c.setFont("Helvetica", 16)
    c.drawCentredString(width / 2, height - 205, "This is to certify that")

    # shrink the name until it fits inside the border
    max_width = width - 160
    full_width = stringWidth(name, "Helvetica-Bold", 40)
    size = 40 if full_width <= max_width else 40 * max_width / full_width
    c.setFont("Helvetica-Bold", size)
    c.drawCentredString(width / 2, height - 265, name)

    c.setFont("Helvetica", 16)
    c.drawCentredString(width / 2, height - 315, "has successfully completed")
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(width / 2, height - 355, course_name)

    c.setFont("Helvetica", 13)
    c.drawString(90, 110, f"Issued by: {issuer}")
    c.drawRightString(width - 90, 110, f"Date: {issue_date.isoformat()}")
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, 60, f"Certificate ID: {certificate_id}")

    c.showPage()
    c.save()
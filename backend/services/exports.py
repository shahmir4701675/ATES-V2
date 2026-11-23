"""Print and CSV renderers for the scoped logical schedule rows."""

from datetime import UTC
from io import BytesIO
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from backend.services.csv_output import csv_text

COLUMNS = ("day", "start", "end", "course", "type", "instructor", "room", "batch")
LABELS = ("Day", "Start time", "End time", "Course code", "Session type", "Instructor", "Room", "Batch")
KARACHI = ZoneInfo("Asia/Karachi")


class CsvExporter:
    media_type = "text/csv"
    extension = "csv"

    def render(self, rows):
        return csv_text([LABELS, *(tuple(row[key] for key in COLUMNS) for row in rows)]).encode("utf-8")


def pdf_font():
    configured = os.getenv("ATES_PDF_FONT")
    windows_font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf"
    linux_font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    candidate = Path(configured) if configured else (windows_font if windows_font.is_file() else linux_font)
    if candidate.is_file():
        if "ATES" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("ATES", str(candidate), shapable=True))
        return "ATES"
    return "Helvetica"


class PdfExporter:
    media_type = "application/pdf"
    extension = "pdf"

    def __init__(self, schedule, term, filters):
        self.schedule = schedule
        self.term = term
        self.filters = filters

    def render(self, rows, group_by=None):
        if group_by:
            field = "batches" if group_by == "batch" else "instructors"
            grouped = {}
            for row in rows:
                for key, name in row[field].items():
                    grouped.setdefault((name, key), []).append(row)
            pages = [(name, records) for (name, _), records in sorted(grouped.items())] or [("No matching entries", [])]
        else:
            pages = [(self.filters, rows[index:index + 29]) for index in range(0, len(rows), 29)] or [(self.filters, [])]
        output = BytesIO()
        document = canvas.Canvas(output, pagesize=landscape(A4), pageCompression=1)
        document.setTitle(f"ATES {self.schedule['schedule_type']} version {self.schedule['version_no']}")
        font = pdf_font()
        for index, (subtitle, records) in enumerate(pages, 1):
            self.page(document, font, subtitle, records, index, len(pages))
        document.save()
        return output.getvalue()

    def page(self, document, font, subtitle, rows, number, count):
        page_width, page_height = landscape(A4)
        margin = 32
        generated = self.schedule["generated_at"].replace(tzinfo=UTC).astimezone(KARACHI)
        document.setFillColor(HexColor("#123D3A"))
        document.setFont("Helvetica-Bold", 19)
        title = "Exam schedule" if self.schedule["schedule_type"] == "Exam" else "Weekly timetable"
        document.drawString(margin, page_height - 52, title)
        document.setFont(font, 9)
        institution = os.getenv("ATES_INSTITUTION", "NED University of Engineering & Technology")
        self.cell(document, font, institution, margin, page_height - 31, page_width - 2 * margin, 10)
        self.cell(document, font, f"{self.term}  |  Version {self.schedule['version_no']}  |  {self.schedule['status']}",
                  margin, page_height - 69, page_width - 2 * margin, 10)
        details = f"{subtitle}  |  Generated {generated:%d/%m/%Y %H:%M} PKT"
        self.cell(document, font, details, margin, page_height - 84, page_width - 2 * margin, 9)
        columns = (("day", "Day / date", 89), ("start", "Start", 42), ("end", "End", 42), ("course", "Course", 72),
                   ("type", "Type", 62), ("instructor", "Instructor", 171), ("room", "Room", 164), ("batch", "Batch", 170))
        width = (page_width - margin * 2) / sum(value[2] for value in columns)
        y = page_height - 111
        row_height = min(14.5, (page_height - 145) / max(1, len(rows)))
        heading_size = 8.5
        document.setFillColor(HexColor("#E8F2EF"))
        document.rect(margin, y - 3, page_width - margin * 2, 15, fill=1, stroke=0)
        x = margin
        for key, label, size in columns:
            self.cell(document, "Helvetica-Bold", label, x + 4, y + 2, size * width - 8, heading_size)
            x += size * width
        y -= row_height
        for index, row in enumerate(rows):
            if index % 2 == 0:
                document.setFillColor(HexColor("#F4F7F6"))
                document.rect(margin, y - 3, page_width - margin * 2, row_height, fill=1, stroke=0)
            x = margin
            for key, _, size in columns:
                value = row["seats"] if key == "room" and row["type"] == "Exam" else row[key]
                self.cell(document, font, str(value), x + 4, y + 1, size * width - 8, min(8.5, row_height - 2))
                x += size * width
            y -= row_height
        if not rows:
            self.cell(document, font, "No matching entries.", margin + 4, y, 300, 10)
        document.setFont("Helvetica", 8)
        document.drawRightString(page_width - margin, 22, f"{number} / {count}")
        document.showPage()

    @staticmethod
    def cell(document, font, value, x, y, width, size):
        value = " ".join(value.split())
        font_size = max(5.5, size)
        while font_size > 5.5 and pdfmetrics.stringWidth(value, font, font_size) > width:
            font_size = max(5.5, font_size - .5)
        if pdfmetrics.stringWidth(value, font, font_size) > width:
            while value and pdfmetrics.stringWidth(value + "...", font, font_size) > width:
                value = value[:-1]
            value += "..."
        document.setFont(font, font_size)
        document.setFillColor(HexColor("#163431"))
        document.drawString(x, y, value, shaping=True)


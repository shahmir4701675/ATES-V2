"""Build the two-page quick start, four-chapter role manual and installation guide."""

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / ".ates" / "evidence"
OUTPUT = ROOT / "output" / "pdf"
GREEN = HexColor("#123D3A")
INK = HexColor("#213936")
DIM = HexColor("#526762")

TITLE = ParagraphStyle("Title", fontName="Helvetica-Bold", fontSize=25, leading=31, textColor=GREEN, spaceAfter=14)
HEADING = ParagraphStyle("Section", fontName="Helvetica-Bold", fontSize=13, leading=18, textColor=GREEN, spaceBefore=12, spaceAfter=6)
BODY = ParagraphStyle("Body", fontName="Helvetica", fontSize=10.6, leading=16, alignment=TA_LEFT, textColor=INK, spaceAfter=8)
CAPTION = ParagraphStyle("Caption", parent=BODY, fontSize=9, leading=12, textColor=DIM)


def page(title, sections, screenshot=None):
    story = [Paragraph(escape(title), TITLE)]
    for heading, text in sections:
        story.extend([Paragraph(escape(heading), HEADING), Paragraph(escape(text), BODY)])
    if screenshot:
        path, caption = screenshot
        figure = Image(str(EVIDENCE / path))
        scale = min(476 / figure.imageWidth, 246 / figure.imageHeight)
        figure.drawWidth, figure.drawHeight = figure.imageWidth * scale, figure.imageHeight * scale
        figure.hAlign = "LEFT"
        story.extend([Spacer(1, 12), figure, Spacer(1, 6), Paragraph(escape(caption), CAPTION)])
    return story


def build(filename, chapters):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / filename
    document = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=55, rightMargin=55, topMargin=66, bottomMargin=58)
    story = []
    for index, chapter in enumerate(chapters):
        if index:
            story.append(PageBreak())
        story.extend(chapter)

    def page_marks(canvas, doc):
        width, height = A4
        canvas.setFillColor(GREEN)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(55, height - 36, "ATES  /  ACADEMIC SCHEDULING")
        canvas.setStrokeColor(HexColor("#BCCFC9"))
        canvas.line(55, height - 46, width - 55, height - 46)
        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(DIM)
        canvas.drawString(55, 32, "Auto Timetable / Exam Scheduler")
        canvas.drawRightString(width - 55, 32, str(doc.page))

    document.build(story, onFirstPage=page_marks, onLaterPages=page_marks)
    return path


QUICK = [
    page("Prepare and generate", [
        ("Set up the term", "Sign in as Coordinator. In Master data, open Terms, add the term and set it Active. "
         "In Weekly grid, choose teaching days, the first start time, minutes per slot and slots per day. Save. Block "
         "breaks by selecting a slot and entering a reason."),
        ("Add or import the teaching records", "Create the department first. Prepare courses, instructors, batches and rooms. "
         "Add each offering with its course, batch, instructor and enrolled count. For a CSV, open Import CSV and download the "
         "template for that record type. Fill it in as UTF-8, preview it and confirm. For rejected rows, correct the indicated "
         "line and column or confirm only the valid rows."),
        ("Generate with the defaults", "On Dashboard select Generate timetable. Leave the active term and Default configuration "
         "selected, then select Generate. Open View timetable when the version is Generated. If the version is a Draft with a "
         "conflict report, correct the listed records and run again."),
    ], ("phase3/weekly-timetable.png", "Weekly timetable with a lecture, a two-slot lab and a blocked break.")),
    page("Review and publish", [
        ("Review the draft result", "The Coordinator can filter the timetable by course, batch, instructor, room or day. "
         "To change a Generated version, drag an entry or open Adjust schedule, select the entry and choose a destination. "
         "Review any rule message and retry. Lock entries that should stay in place during generation from that version."),
        ("Publish as Approver", "Sign in as Approver. Open Timetables, select the term and open the Generated version. "
         "Check the review summary, hard-conflict count and score. Confirm publication and, when applicable, archiving of the "
         "previous version. Select Publish schedule."),
        ("Open the published result", "Faculty and Students can use Published timetable directly from Dashboard. "
         "Apply filters before selecting Export PDF or Export CSV. Reader access follows the Faculty instructor link or "
         "Student batch link."),
        ("Schedule exams", "Prepare dated exam sessions in Settings. If using explicit enrollments, complete each roster. "
         "In Exams, choose Generate exam schedule. Review the dates, rooms and assigned seats before publishing."),
    ], ("phase6/published-version.png", "An Approver's version after publication.")),
]

MANUAL = [
    page("Coordinator", [
        ("Academic data", "Master data holds terms, the weekly grid, departments, rooms, courses, batches, instructors, "
         "offerings and enrollments. Use Edit to correct a record or change its status. Closing a term archives its publications."),
        ("Import and run", "Import CSV validates required fields, duplicate keys and linked records. Confirm valid rows after "
         "reviewing the error report. The Default rule set is created with each term. In Settings, clone a configuration "
         "to tune weights and time limits or set dated exam sessions."),
        ("Adjust and export", "In a Generated version, move entries with drag and drop or Adjust schedule. Lock a class or exam, "
         "or restore the original solver assignments. Select Previous version during generation to preserve its locks. "
         "Export the filtered view or a grouped PDF by instructor or batch."),
    ], ("phase4/import-preview.png", "Import preview with the rejected row and its field-level reason.")),
    page("Approver", [
        ("Inspect a version", "Choose a term and open a Generated timetable or exam version. Review the preview, objective "
         "score, number of sessions and hard conflicts. A hard conflict must be corrected before publication."),
        ("Publish and replace", "Confirm the approval action. If there is already a Published version of the same type and "
         "term, the application archives it. Staff can reopen Archived versions through the version list."),
        ("Restore an older plan", "Ask a Coordinator to duplicate the earlier version to a Draft and validate the copy. "
         "Review and publish the new version through the same approval screen."),
    ], ("phase6/published-version.png", "Version summary with Published status.")),
    page("Faculty and Students", [
        ("Find your published schedule", "Sign in and use Published timetable or Published exams from Dashboard. Faculty see "
         "their assigned teaching and exam courses. Students see the schedule of their linked batch."),
        ("Read the details", "The weekly timetable shows room, instructor and session type. A multi-slot lab is marked across its "
         "occupied slots. Exam schedules list the date, time, course, rooms and seats. On a phone, scroll the timetable inside "
         "the grid, or select a day to narrow it."),
        ("Availability and downloads", "Faculty can mark own teaching slots unavailable for future timetable runs. Apply filters "
         "before downloading a PDF or CSV. Use Change password or Sign out from the workspace."),
    ], ("phase5/exams-mobile.png", "Exam list with a split-room allocation, shown at 360 px.")),
    page("Administrator", [
        ("Create and maintain accounts", "Use User accounts to create users or edit their role and status. A Faculty account needs "
         "an instructor link and a Student account needs a batch link. The form can create the linked record before saving."),
        ("Reset access", "Reset password ends existing sessions for that account. Deactivate an account to withdraw access while "
         "keeping its history. Reactivate to allow the user to sign in again."),
        ("Audit and API reference", "Use Audit log to filter by actor, action and time in Asia/Karachi. Use API reference to inspect "
         "authenticated endpoints. Protect the account and only share schedule exports with authorized recipients."),
    ], ("phase1/accounts-mobile.png", "Account management at 360 px.")),
]

INSTALL = [
    page("Local installation", [
        ("Prerequisites", "Use Python 3.11 or later, Node 18 or later for the browser build, and a current browser. SQLite supports "
         "the standalone local profile. PostgreSQL 15 or later supports the server profile."),
        ("Build and bootstrap", "From the project root create a virtual environment, install requirements-engine.txt and run npm ci "
         "--prefix frontend followed by npm run build --prefix frontend. Run python -m backend.cli bootstrap --email admin@example.test, "
         "then provide the password when prompted."),
        ("Run the application", "Run python -m backend.cli serve. It migrates the local database, starts the independent worker "
         "and serves https://localhost:8443. The local certificate is self-signed. Use the certificate file in .ates/tls to trust "
         "this local profile. Use a trusted TLS endpoint for institutional clients."),
        ("Configure database access", "Use environment variables for database credentials and JWT signing. For a disposable "
         "PostgreSQL rehearsal, set separate migration, API and worker connections and use grant-local-runtime for the profile roles. "
         "See README.md for platform-specific commands. Reconcile the hosted schema and grants before an institutional deployment."),
    ]),
    page("Administration and recovery", [
        ("Accounts and activity", "Create the first Administrator with bootstrap and use User accounts for ordinary access changes. "
         "Sign-in uses bcrypt-protected passwords. Five failed attempts lock an active account for 15 minutes. Sessions end after "
         "30 minutes of inactivity."),
        ("Back up and restore", "Set ATES_BACKUP_DIRECTORY for the daily local backup at 19:00 Asia/Karachi, or run python -m backend.cli "
         "backup manually. The application keeps seven generated copies per database engine in the designated directory. Use "
         "python -m backend.cli restore with a fresh disposable destination and a selected backup. Store the copies in a "
         "restricted location and rehearse recovery before deployment."),
        ("Operational checks", "Run the test suite with requirements-test.txt. Use the dated evidence and release checklist to track "
         "browser coverage, capacity measurements and recovery. Check the institution's privacy rules and retain only the "
         "account, availability and candidate information the department needs."),
    ]),
]

if __name__ == "__main__":
    for name, chapters in (("ATES-Quick-Start.pdf", QUICK), ("ATES-Role-Manual.pdf", MANUAL),
                           ("ATES-Installation-and-Administration.pdf", INSTALL)):
        print(build(name, chapters))


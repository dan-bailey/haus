from datetime import date
from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

from app.meals import shopping_list
def shopping_pdf(session, *, week_start: date) -> bytes:
    items = shopping_list(session, week_start=week_start)
    week_end = week_start.fromordinal(week_start.toordinal() + 6)
    output = BytesIO()
    canvas = Canvas(output, pagesize=letter)
    canvas.setTitle(f"Haus shopping list {week_start.isoformat()}")
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawString(72, 740, f"Shopping List: {week_start:%b %-d} - {week_end:%b %-d, %Y}")
    canvas.setFont("Helvetica", 12)
    y = 710
    if not items:
        canvas.drawString(72, y, "No approved meals scheduled.")
    for name, count in items:
        label = name if count == 1 else f"{name}, x{count}"
        canvas.drawString(84, y, f"[ ] {label}")
        y -= 20
        if y < 60:
            canvas.showPage()
            canvas.setFont("Helvetica", 12)
            y = 740
    canvas.save()
    return output.getvalue()
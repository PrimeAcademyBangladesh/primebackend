from datetime import date, timedelta
from django.utils import timezone
import csv
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from django.http import HttpResponse
from reportlab.platypus import Image
from django.conf import settings
import os



def resolve_date_range(range_key):
    today = timezone.now().date()

    if range_key == "this_month":
        start = today.replace(day=1)
        end = today
    elif range_key == "last_month":
        first = today.replace(day=1)
        last_month_end = first - timedelta(days=1)
        start = last_month_end.replace(day=1)
        end = last_month_end
    elif range_key == "last_3_months":
        start = today - timedelta(days=90)
        end = today
    elif range_key == "last_6_months":
        start = today - timedelta(days=180)
        end = today
    elif range_key == "last_12_months":
        start = today - timedelta(days=365)
        end = today
    elif range_key == "this_year":
        start = date(today.year, 1, 1)
        end = today
    elif range_key == "financial_year":
        fy_start = date(today.year if today.month >= 4 else today.year - 1, 4, 1)
        start = fy_start
        end = today
    else:
        return None, None

    return start, end


# -------------------------
# Export Functions for CSV
# -------------------------

def export_transactions_csv(rows):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="transactions.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Transaction ID", "Description", "Category",
        "Reference", "Date", "Type", "Status", "Amount"
    ])

    for r in rows:
        writer.writerow(r.values())

    return response


# -------------------------
# Export Functions for PDF
# -------------------------
def export_transactions_pdf(rows):
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="transactions.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20,
    )

    styles = getSampleStyleSheet()
    elements = []

    # ======================================================
    # HEADER (LOGO + TITLE)
    # ======================================================
    logo_path = os.path.join(settings.STATIC_ROOT, "default_images/prime-academy-logo.png")
    print(logo_path)
    header_table_data = []

    if os.path.exists(logo_path):
        logo = Image(logo_path, width=60, height=60)
        header_table_data.append([
            logo,
            Paragraph("<b>LMS Accounting – Transactions Report</b>", styles["Title"])
        ])
    else:
        header_table_data.append([
            "",
            Paragraph("<b>LMS Accounting – Transactions Report</b>", styles["Title"])
        ])

    header = Table(
        header_table_data,
        colWidths=[80, 680],
        style=[
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, 0), "CENTER"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ],
    )

    elements.append(header)
    elements.append(Spacer(1, 12))

    # ======================================================
    # TABLE DATA
    # ======================================================
    table_data = [[
        "Transaction ID",
        "Description",
        "Category",
        "Reference",
        "Date",
        "Type",
        "Status",
        "Amount",
    ]]

    for r in rows:
        amount = f"+{r['amount']}" if r["amount"] > 0 else f"{r['amount']}"

        table_data.append([
            r["id"],
            r["description"],
            r["category"],
            r["reference"],
            r["date"].strftime("%Y-%m-%d"),
            r["type"],
            r["status"].capitalize(),
            amount,
        ])

    table = Table(
        table_data,
        repeatRows=1,
        colWidths=[80, 220, 90, 120, 80, 60, 80, 80],
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (5, 1), (6, -1), "CENTER"),
        ("ALIGN", (7, 1), (7, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
    ]))

    elements.append(table)

    doc.build(elements)
    return response

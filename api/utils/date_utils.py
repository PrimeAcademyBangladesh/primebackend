from datetime import date
from django.utils import timezone


def uk_report_title(base_title, start_date=None, end_date=None):
    """
    Returns a UK-style report title.

    Examples:
    - Student List (as of 26 January 2026)
    - Student List (01 January 2026 – 26 January 2026)
    """

    def fmt(d):
        return d.strftime("%d %B %Y")

    # No dates at all → as of today
    if not start_date and not end_date:
        today = timezone.now().date()
        return f"{base_title} (as of {fmt(today)})"

    # Only one date → as of
    if start_date and not end_date:
        return f"{base_title} (as of {fmt(start_date)})"

    if end_date and not start_date:
        return f"{base_title} (as of {fmt(end_date)})"

    # Same date → as of
    if start_date == end_date:
        return f"{base_title} (as of {fmt(end_date)})"

    # Proper range
    return f"{base_title} ({fmt(start_date)} – {fmt(end_date)})"

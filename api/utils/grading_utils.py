# api/utils/grading_utils.py
from decimal import Decimal, ROUND_HALF_UP

def apply_late_penalty(marks, penalty_percentage):
    if marks is None:
        return marks

    penalty_percentage = Decimal(str(penalty_percentage))
    if penalty_percentage <= 0:
        return marks

    penalty_amount = (
        marks * penalty_percentage / Decimal('100')
    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    return max(
        (marks - penalty_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        Decimal('0.00')
    )

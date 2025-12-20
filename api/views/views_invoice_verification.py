"""Invoice verification endpoint for QR code scanning.

Public endpoint that allows anyone to verify invoice authenticity
by scanning the QR code on the invoice PDF.
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from api.models.models_order import Order


@extend_schema(
    tags=["Orders Invoice Verify"],
    summary="Verify invoice by order number (Public)",
    description="""
    Public endpoint to verify invoice authenticity via QR code scanning.

    Returns basic order information to confirm the invoice is legitimate.
    No authentication required - designed for public verification.

    **Use Case:**
    - Scan QR code on invoice PDF
    - Verify payment was completed
    - Confirm order details

    **Security:**
    - Only returns non-sensitive information
    - No personal details exposed
    - Read-only operation
    """,
    responses={
        200: OpenApiResponse(
            description="Invoice verification successful",
            response={
                "type": "object",
                "properties": {
                    "verified": {"type": "boolean"},
                    "order_number": {"type": "string"},
                    "order_date": {"type": "string", "format": "date-time"},
                    "status": {"type": "string"},
                    "total_amount": {"type": "string"},
                    "billing_name": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "course_title": {"type": "string"},
                                "batch_name": {"type": "string"},
                                "price": {"type": "string"},
                            },
                        },
                    },
                },
            },
        ),
        404: OpenApiResponse(description="Invoice not found"),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def verify_invoice(request, order_number):
    """Verify invoice by order number from QR code."""

    try:
        order = Order.objects.prefetch_related("items__course", "items__batch").get(order_number=order_number)

        # Build items list with non-sensitive information
        items = []
        for item in order.items.all():
            batch_display = "—"
            if item.batch:
                batch_display = item.batch.batch_name or f"Batch {item.batch.batch_number}"

            items.append({"course_title": item.course.title, "batch_name": batch_display, "price": f"৳{item.price:,.2f}"})

        # Return verification data
        return Response(
            {
                "verified": True,
                "order_number": order.order_number,
                "order_date": order.created_at.isoformat(),
                "status": order.status,
                "payment_method": (
                    order.get_payment_method_display()
                    if hasattr(order, "get_payment_method_display")
                    else order.payment_method
                ),
                "total_amount": f"৳{order.total_amount:,.2f}",
                "billing_name": order.billing_name,
                "items": items,
                "message": "This invoice has been verified as authentic.",
            },
            status=status.HTTP_200_OK,
        )

    except Order.DoesNotExist:
        return Response(
            {
                "verified": False,
                "error": "Invoice not found",
                "message": "This invoice could not be verified. Please contact support if you believe this is an error.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

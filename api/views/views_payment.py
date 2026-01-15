"""Payment gateway views for SSLCommerz integration."""


import traceback
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models.models_order import Enrollment, Order
from api.serializers.serializers_order import OrderListSerializer
from api.utils.response_utils import api_response
from api.utils.sslcommerz import SSLCommerzError, SSLCommerzPayment


class PaymentInitiateView(APIView):
    """
    Initialize payment with SSLCommerz for an order.

    POST /api/payment/initiate/
    Body: {"order_id": 123}
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Initiate payment for order",
        description="Initialize SSLCommerz payment session for a pending order. Returns payment gateway URL.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "integer",
                        "description": "Order ID to pay for",
                    }
                },
                "required": ["order_id"],
            }
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "message": {"type": "string"},
                    "data": {
                        "type": "object",
                        "properties": {
                            "payment_url": {
                                "type": "string",
                                "description": "SSLCommerz payment page URL",
                            },
                            "order_number": {"type": "string"},
                            "amount": {"type": "string"},
                            "currency": {"type": "string"},
                        },
                    },
                },
            }
        },
        tags=["Course - Payment"],
    )
    def post(self, request):
        """Initiate payment for an order."""
        order_id = request.data.get("order_id")

        if not order_id:
            return api_response(False, "Order ID is required", {}, status.HTTP_400_BAD_REQUEST)

        try:
            # Get order and verify ownership
            order = Order.objects.select_related("user").get(id=order_id)

            # Students can only pay for their own orders, staff can pay for any
            if not request.user.is_staff and order.user != request.user:
                return api_response(
                    False,
                    "You can only pay for your own orders",
                    {},
                    status.HTTP_403_FORBIDDEN,
                )

            # Check if order can be paid
            if order.status not in ["pending", "processing"]:
                return api_response(
                    False,
                    f"Order cannot be paid. Current status: {order.get_status_display()}",
                    {},
                    status.HTTP_400_BAD_REQUEST,
                )

            # Initialize payment with SSLCommerz
            gateway = SSLCommerzPayment()

            try:
                # Calculate payment amount (installment or full)
                amount_to_pay = order.total_amount
                if order.is_installment:
                    installment = order.installment_payments.filter(status="pending").order_by("installment_number").first()
                    if installment:
                        amount_to_pay = installment.amount

                # Pass the correct amount to SSLCommerz
                session_data = gateway.init_payment(order, amount=amount_to_pay)

                # Update order status to processing
                order.status = "processing"
                order.payment_method = "ssl_commerce"
                order.save()

                return api_response(
                    True,
                    "Payment session initialized successfully",
                    {
                        "payment_url": session_data.get("GatewayPageURL"),
                        "session_key": session_data.get("sessionkey"),
                        "order_number": order.order_number,
                        "amount": str(amount_to_pay),
                        "currency": order.currency,
                    },
                )

            except SSLCommerzError as e:
                return api_response(
                    False,
                    f"Payment gateway error: {str(e)}",
                    {},
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except Order.DoesNotExist:
            return api_response(False, "Order not found", {}, status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return api_response(
                False,
                f"Unexpected error: {str(e)}",
                {},
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema(
    summary="Payment webhook (IPN) from SSLCommerz",
    description="Receives payment notifications from SSLCommerz. This endpoint is called by SSLCommerz automatically after payment.",
    request={
        "application/x-www-form-urlencoded": {
            "type": "object",
            "properties": {
                "tran_id": {
                    "type": "string",
                    "description": "Transaction ID (order_number)",
                },
                "val_id": {"type": "string", "description": "Validation ID"},
                "amount": {"type": "string", "description": "Payment amount"},
                "status": {"type": "string", "description": "Payment status"},
            },
        }
    },
    responses={200: {"description": "Webhook processed"}},
    tags=["Course - Payment"],
)
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
@transaction.atomic
def payment_webhook(request):
    """
    SSLCommerz IPN Handler — FIXED INSTALLMENT LOGIC
    """

    try:
        tran_id = request.data.get("tran_id")
        val_id = request.data.get("val_id")
        amount = request.data.get("amount")
        payment_status = request.data.get("status")

        if not tran_id or not val_id:
            return Response({"error": "Missing parameters"}, status=400)

        try:
            order = Order.objects.get(order_number=tran_id)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)

        gateway = SSLCommerzPayment()
        payment_amount = Decimal(amount)
        is_valid, _ = gateway.validate_payment(val_id, payment_amount)

        if not is_valid or payment_status not in ["VALID", "VALIDATED"]:
            # Payment failed
            order.status = "failed"
            order.save()
            return api_response(
                False,
                "Payment validation failed",
                {"order_number": order.order_number},
                status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # INSTALLMENT LOGIC — FIXED
        # ---------------------------------------------------------
        if order.is_installment:
            # from api.models.models_order import OrderInstallment

            next_installment = order.installment_payments.filter(status="pending").order_by("installment_number").first()

            if not next_installment:
                return Response({"error": "No pending installment"}, status=400)

            if next_installment.status == "paid":
                return api_response(
                    True,
                    "Installment already processed",
                    {
                        "order_number": order.order_number,
                        "installments_paid": order.installments_paid,
                        "installment_plan": order.installment_plan,
                        "payment_status": order.payment_status,
                        "enrollments_created": order.enrollments.count(),
                    },
                )

            # Mark paid

            next_installment.mark_as_paid(
                payment_id=val_id,
                payment_method="ssl_commerce",
                gateway_transaction_id=tran_id,
            )

            order.refresh_from_db()

            # ------------------------------------------------------
            # ❌ OLD WRONG LOGIC (you had this)
            # order.mark_as_completed()
            # ------------------------------------------------------

            # ------------------------------------------------------
            # ✔ NEW CORRECT LOGIC
            # If this is the FIRST installment → give access ONLY
            # ------------------------------------------------------
            if order.installments_paid == 1:
                for item in order.items.all():
                    Enrollment.objects.get_or_create(
                        user=order.user,
                        batch=item.batch,
                        course=item.course,
                        defaults={"order": order},
                    )

                order.status = "processing"
                order.payment_status = "partial"
                order.save()

            # ------------------------------------------------------
            # ✔ FINAL INSTALLMENT → COMPLETE ORDER
            # ------------------------------------------------------
            if order.is_fully_paid():
                order.mark_as_completed()
                order.payment_status = "completed"
                order.save()

            enrollment_count = order.enrollments.count()

            return api_response(
                True,
                f"Installment {order.installments_paid}/{order.installment_plan} paid",
                {
                    "order_number": order.order_number,
                    "installments_paid": order.installments_paid,
                    "installment_plan": order.installment_plan,
                    "payment_status": order.payment_status,
                    "enrollments_created": enrollment_count,
                },
            )
        # ---------------------------------------------------------
        # FULL PAYMENT FLOW (unchanged)
        # ---------------------------------------------------------
        order.mark_as_completed()
        return api_response(
            True,
            "Full payment completed",
            {"order_number": order.order_number},
            status.HTTP_200_OK,
        )

    except Exception as e:
        return Response({"error": str(e)}, status=500)


@csrf_exempt
@transaction.atomic
def payment_success_redirect(request):
    """
    Success redirect from SSLCommerz — FIXED INSTALLMENT LOGIC
    """
    from django.http import HttpResponseForbidden, HttpResponseRedirect, JsonResponse

    try:
        if request.method == "POST":
            store_id = request.POST.get("store_id")
            expected_store = settings.SSLCOMMERZ_STORE_ID

            if store_id != expected_store:
                return HttpResponseForbidden("Invalid request")

            tran_id = request.POST.get("tran_id")
            val_id = request.POST.get("val_id")
            amount = request.POST.get("amount")

            try:
                order = Order.objects.get(order_number=tran_id)
            except Order.DoesNotExist:
                return HttpResponseRedirect(f"{settings.FRONTEND_URL}/payment/fail")

            gateway = SSLCommerzPayment()
            is_valid, _ = gateway.validate_payment(val_id, Decimal(amount))

            if is_valid:
                # ---------------------------------------------------
                # INSTALLMENT LOGIC (same as webhook)
                # ---------------------------------------------------
                if order.is_installment:
                    next_installment = (
                        order.installment_payments.filter(status="pending").order_by("installment_number").first()
                    )

                    if next_installment:


                        next_installment.mark_as_paid(
                            payment_id=val_id,
                            payment_method="ssl_commerce",
                            gateway_transaction_id=tran_id,
                        )

                        order.refresh_from_db()

                        # ❌ OLD WRONG LOGIC
                        # order.mark_as_completed()

                        # ✔ NEW CORRECT LOGIC
                        if order.installments_paid == 1:
                            for item in order.items.all():
                                Enrollment.objects.get_or_create(
                                    user=order.user,
                                    batch=item.batch,
                                    course=item.course,
                                    defaults={"order": order},
                                )

                            order.status = "processing"
                            order.payment_status = "partial"
                            order.save()

                        if order.is_fully_paid():
                            order.mark_as_completed()
                            order.payment_status = "completed"
                            order.save()

                else:
                    order.mark_as_completed()

            # Redirect user safely
            return HttpResponseRedirect(f"{settings.FRONTEND_URL}/payment/success?tran_id={tran_id}")

        # GET request fallback
        tran_id = request.GET.get("tran_id")
        return HttpResponseRedirect(f"{settings.FRONTEND_URL}/payment/success?tran_id={tran_id}")

    except Exception as e:
        return JsonResponse({"error": str(e), "trace": traceback.format_exc()}, status=500)


@csrf_exempt
def payment_fail_redirect(request):
    """Plain Django view - Redirect failed payments to frontend."""

    from django.conf import settings
    from django.http import HttpResponseForbidden, HttpResponseRedirect

    # SECURITY: Verify request is from SSLCommerz (for POST requests)
    if request.method == "POST":
        store_id = request.POST.get("store_id", "")
        expected_store_id = getattr(settings, "SSLCOMMERZ_STORE_ID", "")

        if store_id != expected_store_id:
            return HttpResponseForbidden("Invalid request")

    tran_id = request.POST.get("tran_id", "") or request.GET.get("tran_id", "")
    frontend_url = f"{settings.FRONTEND_URL}/payment/fail?tran_id={tran_id}"
    return HttpResponseRedirect(frontend_url)


@csrf_exempt
def payment_cancel_redirect(request):
    """Plain Django view - Redirect cancelled payments to frontend."""

    from django.conf import settings
    from django.http import HttpResponseForbidden, HttpResponseRedirect

    # SECURITY: Verify request is from SSLCommerz (for POST requests)
    if request.method == "POST":
        store_id = request.POST.get("store_id", "")
        expected_store_id = getattr(settings, "SSLCOMMERZ_STORE_ID", "")

        if store_id != expected_store_id:
            return HttpResponseForbidden("Invalid request")

    tran_id = request.POST.get("tran_id", "") or request.GET.get("tran_id", "")
    frontend_url = f"{settings.FRONTEND_URL}/payment/cancel?tran_id={tran_id}"
    return HttpResponseRedirect(frontend_url)


@extend_schema(
    summary="Verify payment status",
    description="Manually verify payment status for an order. Used by frontend after payment redirect. Accepts both GET and POST. No authentication required for basic status check.",
    parameters=[
        {
            "name": "order_number",
            "in": "query",
            "description": "Order number to verify (for GET requests)",
            "required": False,
            "schema": {"type": "string"},
        }
    ],
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "order_number": {
                    "type": "string",
                    "description": "Order number to verify (for POST requests)",
                }
            },
            "required": ["order_number"],
        }
    },
    responses={
        200: {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "message": {"type": "string"},
                "data": {
                    "type": "object",
                    "properties": {
                        "order_number": {"type": "string"},
                        "status": {"type": "string"},
                        "payment_verified": {"type": "boolean"},
                        "enrolled_courses": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
            },
        }
    },
    tags=["Course - Payment"],
)
@api_view(["GET", "POST"])
@permission_classes([AllowAny])  # Allow unauthenticated access for payment verification
def verify_payment(request):
    """
    Verify payment status for an order.

    This endpoint is called by the frontend after payment redirect
    to check if the payment was successful and order was completed.
    Accepts both GET (query params) and POST (body) requests.

    NOTE: Allows unauthenticated access to support post-payment verification
    when user's session might have expired during payment gateway redirect.
    """
    # Support both GET and POST
    if request.method == "GET":
        order_number = request.GET.get("order_number")
    else:
        order_number = request.data.get("order_number")

    if not order_number:
        return api_response(False, "Order number is required", {}, status.HTTP_400_BAD_REQUEST)

    try:
        order = Order.objects.get(order_number=order_number)

        # Optional: Verify ownership if user is authenticated
        # If not authenticated (payment redirect scenario), allow access
        if request.user and request.user.is_authenticated:
            if not request.user.is_staff and order.user != request.user:
                return api_response(
                    False,
                    "You can only verify your own orders",
                    {},
                    status.HTTP_403_FORBIDDEN,
                )

        # Get enrolled courses
        enrolled_courses = list(order.enrollments.filter(is_active=True).values_list("course__title", flat=True))

        return api_response(
            True,
            f"Order status: {order.get_status_display()}",
            {
                "order_number": order.order_number,
                "status": order.status,
                "payment_method": order.payment_method,
                "payment_id": order.payment_id,
                "payment_verified": order.status == "completed",
                "amount": str(order.total_amount),
                "currency": order.currency,
                "completed_at": order.completed_at,
                "enrolled_courses": enrolled_courses,
                "enrollment_count": len(enrolled_courses),
            },
        )

    except Order.DoesNotExist:
        return api_response(False, "Order not found", {}, status.HTTP_404_NOT_FOUND)


# class InstallmentPaymentInitiateView(APIView):
#     """
#     Initiate payment for the next pending installment.
#     """
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         order_id = request.data.get("order_id")

#         if not order_id:
#             return api_response(False, "Order ID is required", {}, status.HTTP_400_BAD_REQUEST)

#         try:
#             order = Order.objects.get(id=order_id)

#             # Ownership check
#             if not request.user.is_staff and request.user != order.user:
#                 return api_response(False, "You can only pay your own installments", {}, status.HTTP_403_FORBIDDEN)

#             # Must be installment order
#             if not order.is_installment:
#                 return api_response(False, "This order does not use installment payments", {}, status.HTTP_400_BAD_REQUEST)

#             # Find next pending installment
#             next_installment = (
#                 order.installment_payments.filter(status="pending")
#                 .order_by("installment_number")
#                 .first()
#             )

#             if not next_installment:
#                 return api_response(False, "No pending installment available", {}, status.HTTP_400_BAD_REQUEST)

#             amount_to_pay = next_installment.amount

#             # Initiate payment with SSLCommerz
#             gateway = SSLCommerzPayment()
#             session_data = gateway.init_payment(order, amount=amount_to_pay)

#             # Set order status to processing
#             order.status = "processing"
#             order.payment_method = "ssl_commerce"
#             order.save()

#             return api_response(
#                 True,
#                 "Installment payment session initialized",
#                 {
#                     "payment_url": session_data.get("GatewayPageURL"),
#                     "session_key": session_data.get("sessionkey"),
#                     "order_number": order.order_number,
#                     "installment_number": next_installment.installment_number,
#                     "amount": str(amount_to_pay),
#                     "due_date": next_installment.due_date,
#                     "currency": order.currency,
#                 }
#             )

#         except Order.DoesNotExist:
#             return api_response(False, "Order not found", {}, status.HTTP_404_NOT_FOUND)

#         except Exception as e:
#             return api_response(False, str(e), {}, status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    summary="Initiate installment payment",
    description="Starts SSLCommerz payment session for the next pending installment of an installment-based order.",
    tags=["Installment"],
    request={
        "application/json": {
            "type": "object",
            "required": ["order_id"],
            "properties": {
                "order_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "Order ID for which the next installment payment should be initiated.",
                }
            },
        }
    },
    responses={
        200: {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "message": {"type": "string"},
                "data": {
                    "type": "object",
                    "properties": {
                        "payment_url": {"type": "string"},
                        "session_key": {"type": "string"},
                        "order_number": {"type": "string"},
                        "installment_number": {"type": "integer"},
                        "amount": {"type": "string"},
                        "due_date": {"type": "string", "format": "date-time"},
                        "currency": {"type": "string"},
                    },
                },
            },
            "example": {
                "success": True,
                "message": "Installment payment session initialized",
                "data": {
                    "payment_url": "https://sandbox.sslcommerz.com/gwprocess/v4/gw.php?sessionkey=ABC123",
                    "session_key": "ABC123XYZ",
                    "order_number": "ORD-20240215-XY11",
                    "installment_number": 2,
                    "amount": "2500.00",
                    "due_date": "2025-03-01T00:00:00Z",
                    "currency": "BDT",
                },
            },
        },
        400: {
            "type": "object",
            "example": {
                "success": False,
                "message": "No pending installment available",
                "data": {},
            },
        },
        403: {
            "type": "object",
            "example": {
                "success": False,
                "message": "You can only pay your own installments",
                "data": {},
            },
        },
        404: {
            "type": "object",
            "example": {"success": False, "message": "Order not found", "data": {}},
        },
        500: {
            "type": "object",
            "example": {
                "success": False,
                "message": "Internal server error",
                "data": {},
            },
        },
    },
)
class InstallmentPaymentInitiateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get("order_id")

        if not order_id:
            return api_response(False, "Order ID is required", {}, status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.get(id=order_id)

            # Ownership check
            if not request.user.is_staff and request.user != order.user:
                return api_response(
                    False,
                    "You can only pay your own installments",
                    {},
                    status.HTTP_403_FORBIDDEN,
                )

            # Must be installment order
            if not order.is_installment:
                return api_response(
                    False,
                    "This order does not use installment payments",
                    {},
                    status.HTTP_400_BAD_REQUEST,
                )

            # Find next pending installment
            next_installment = order.installment_payments.filter(status="pending").order_by("installment_number").first()

            if not next_installment:
                return api_response(
                    False,
                    "No pending installment available",
                    {},
                    status.HTTP_400_BAD_REQUEST,
                )

            amount_to_pay = next_installment.amount

            # Initiate payment with SSLCommerz
            gateway = SSLCommerzPayment()
            session_data = gateway.init_payment(order, amount=amount_to_pay)

            # Set order status to processing
            order.status = "processing"
            order.payment_method = "ssl_commerce"
            order.save()

            return api_response(
                True,
                "Installment payment session initialized",
                {
                    "payment_url": session_data.get("GatewayPageURL"),
                    "session_key": session_data.get("sessionkey"),
                    "order_number": order.order_number,
                    "installment_number": next_installment.installment_number,
                    "amount": str(amount_to_pay),
                    "due_date": next_installment.due_date,
                    "currency": order.currency,
                },
            )

        except Order.DoesNotExist:
            return api_response(False, "Order not found", {}, status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return api_response(False, str(e), {}, status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    summary="Installment summary for an order",
    description="Returns paid installments, next pending installment, remaining amount, and full payment status.",
    tags=["Installment"],
    responses={
        200: {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "message": {"type": "string"},
                "data": {
                    "type": "object",
                    "properties": {
                        "order_number": {"type": "string"},
                        "installments_paid": {"type": "integer"},
                        "installment_plan": {"type": "integer"},
                        "next_installment": {
                            "type": "object",
                            "nullable": True,
                            "properties": {
                                "installment_number": {"type": "integer"},
                                "amount": {"type": "string"},
                                "due_date": {"type": "string", "format": "date-time"},
                                "is_overdue": {"type": "boolean"},
                                "days_until_due": {"type": "integer"},
                            },
                        },
                        "remaining_amount": {"type": "string"},
                        "is_fully_paid": {"type": "boolean"},
                    },
                },
            },
        }
    },
)
class InstallmentSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id, user=request.user)

            if not order.is_installment:
                return api_response(False, "Order is not installment based", {}, 400)

            next_installment = order.installment_payments.filter(status="pending").order_by("installment_number").first()

            next_data = None
            if next_installment:
                next_data = {
                    "installment_number": next_installment.installment_number,
                    "amount": str(next_installment.amount),
                    "due_date": next_installment.due_date,
                    "is_overdue": next_installment.is_overdue_now(),
                    "days_until_due": next_installment.days_until_due(),
                }

            return api_response(
                True,
                "Installment summary loaded",
                {
                    "order_number": order.order_number,
                    "installments_paid": order.installments_paid,
                    "installment_plan": order.installment_plan,
                    "next_installment": next_data,
                    "remaining_amount": str(order.get_remaining_amount()),
                    "is_fully_paid": order.is_fully_paid(),
                },
            )

        except Order.DoesNotExist:
            return api_response(False, "Order not found", {}, 404)

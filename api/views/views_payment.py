from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from api.models.models_order import Order, PaymentTransaction
from api.utils.response_utils import api_response
from api.utils.sslcommerz import SSLCommerzPayment
from django.utils import timezone

@extend_schema(
    summary="Initiate payment",
    description="Creates an SSLCommerz payment session for an order",
    request={"application/json": {"example": {"order_id": "uuid"}}},
    responses={200: dict},
    tags=["Payment"],
)
class PaymentInitiateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get("order_id")
        if not order_id:
            return api_response(False, "Order ID is required", {}, status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return api_response(False, "Order not found", {}, status.HTTP_404_NOT_FOUND)

        if order.status == "completed":
            return api_response(False, "Order already completed", {}, status.HTTP_400_BAD_REQUEST)

        if order.status == "processing" and order.payment_id:
            return api_response(False, "Payment already in progress", {}, status.HTTP_400_BAD_REQUEST)

        # ==================================================
        # ✅ FIX: INSTALLMENT vs FULL AMOUNT
        # ==================================================
        if order.is_installment:
            installment = (
                order.installment_payments
                .filter(status="pending")
                .order_by("installment_number")
                .first()
            )
            if not installment:
                return api_response(False, "No pending installment", {}, status.HTTP_400_BAD_REQUEST)

            amount = installment.amount
        else:
            amount = order.total_amount

        # ==================================================
        # 🚀 INITIATE SSLCommerz SESSION
        # ==================================================
        gateway = SSLCommerzPayment()
        try:
            session = gateway.init_payment(order, amount=amount)
        except Exception as e:
            return api_response(False, str(e), {}, status.HTTP_500_INTERNAL_SERVER_ERROR)

        # ==================================================
        # 🧾 UPDATE ORDER STATE
        # ==================================================
        order.status = "processing"
        order.payment_method = "ssl_commerce"

        if session.get("sessionkey"):
            order.notes = f"SSLCommerz session: {session.get('sessionkey')}"

        order.save(update_fields=["status", "payment_method", "notes"])

        return api_response(
            True,
            "Payment session initialized",
            {
                "payment_url": session.get("GatewayPageURL"),
                "order_number": order.order_number,
                "amount": str(amount),
                "currency": order.currency,
            },
            status.HTTP_200_OK,
        )


@extend_schema(
    summary="SSLCommerz webhook (IPN) – IDEMPOTENT",
    description="Processes payment confirmation from SSLCommerz safely",
    tags=["Payment"],
)
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
@transaction.atomic
def payment_webhook(request):
    tran_id = request.data.get("tran_id")
    val_id = request.data.get("val_id")
    amount = request.data.get("amount")
    status_raw = request.data.get("status")

    if not tran_id or not val_id or not amount:
        return api_response(False, "Missing parameters", {}, 400)

    try:
        order = Order.objects.select_for_update().get(order_number=tran_id)
    except Order.DoesNotExist:
        return api_response(True, "Order not found (ignored)", {}, 200)

    gateway = SSLCommerzPayment()

    # ==================================================
    # 🔥 INSTALLMENT PAYMENT FLOW
    # ==================================================
    if order.is_installment:
        installment = (
            order.installment_payments
            .filter(status="pending")
            .order_by("installment_number")
            .first()
        )

        if not installment:
            return api_response(True, "All installments already processed", {}, 200)

        # 🔒 Idempotency guard
        if installment.payment_id == val_id:
            return api_response(True, "Installment already paid", {}, 200)

        expected_amount = installment.amount

        if Decimal(amount) != expected_amount:
            return api_response(True, "Amount mismatch", {}, 200)

        is_valid, _ = gateway.validate_payment(val_id, expected_amount)
        if not is_valid or status_raw not in ("VALID", "VALIDATED"):
            return api_response(True, "Invalid installment payment", {}, 200)

        # ✅ CORE ACTION
        installment.mark_as_paid(
            payment_id=val_id,
            payment_method="ssl_commerce",
            gateway_transaction_id=tran_id,
        )

        # 🔥 CRITICAL: refresh fields updated via F()
        order.refresh_from_db(fields=["installments_paid", "payment_status", "status"])

        # 🧑‍🎓 ENROLL AFTER FIRST INSTALLMENT
        if order.installments_paid == 1:
            order.ensure_enrollments_created()

        # 🏁 FINAL INSTALLMENT
        if order.is_fully_paid():
            order.payment_method = "ssl_commerce"
            order.payment_id = val_id
            order.completed_at = timezone.now()
            order.save(update_fields=["payment_method", "payment_id", "completed_at"])
            order.mark_as_completed()
        else:
            order.status = "processing"
            order.payment_status = "partial"
            order.save(update_fields=["status", "payment_status"])

        return api_response(True, "Installment processed", {}, 200)

    # ==================================================
    # 🔥 FULL PAYMENT FLOW (NON-INSTALLMENT)
    # ==================================================
    if order.status == "completed":
        return api_response(True, "Payment already processed", {}, 200)

    expected_amount = order.total_amount

    if Decimal(amount) != expected_amount:
        return api_response(True, "Amount mismatch", {}, 200)

    is_valid, _ = gateway.validate_payment(val_id, expected_amount)
    if not is_valid or status_raw not in ("VALID", "VALIDATED"):
        if order.status not in ("completed", "failed"):
            order.status = "failed"
            order.payment_status = "failed"
            order.save(update_fields=["status", "payment_status"])
        return api_response(True, "Invalid payment", {}, 200)

    # ✅ SUCCESS
    order.payment_method = "ssl_commerce"
    order.payment_id = val_id
    order.completed_at = timezone.now()
    order.save(update_fields=["payment_method", "payment_id", "completed_at"])

    order.mark_as_completed()

    return api_response(
        True,
        "Full payment completed",
        {"order_number": order.order_number},
        200,
    )




@csrf_exempt
def payment_success_redirect(request):
    from django.http import HttpResponseRedirect
    from django.conf import settings

    tran_id = (
        request.POST.get("tran_id")
        if request.method == "POST"
        else request.GET.get("tran_id")
    )

    if not tran_id:
        return HttpResponseRedirect(
            f"{settings.FRONTEND_URL}/payment/pending"
        )

    return HttpResponseRedirect(
        f"{settings.FRONTEND_URL}/payment/success?tran_id={tran_id}"
    )


@csrf_exempt
def payment_fail_redirect(request):
    from django.http import HttpResponseRedirect

    tran_id = (
        request.POST.get("tran_id")
        if request.method == "POST"
        else request.GET.get("tran_id")
    )

    return HttpResponseRedirect(
        f"{settings.FRONTEND_URL}/payment/fail?tran_id={tran_id or ''}"
    )


@csrf_exempt
def payment_cancel_redirect(request):
    from django.http import HttpResponseRedirect

    tran_id = (
        request.POST.get("tran_id")
        if request.method == "POST"
        else request.GET.get("tran_id")
    )

    return HttpResponseRedirect(
        f"{settings.FRONTEND_URL}/payment/cancel?tran_id={tran_id or ''}"
    )


@extend_schema(
    summary="Verify payment",
    description="Used by frontend after redirect to check order/payment status",
    parameters=[
        OpenApiParameter(
            name="order_number",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=False,
        )
    ],
    tags=["Payment"],
)
@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def verify_payment(request):
    order_number = (
        request.GET.get("order_number")
        if request.method == "GET"
        else request.data.get("order_number")
    )

    if not order_number:
        return api_response(False, "Order number required", {}, 400)

    try:
        order = Order.objects.get(order_number=order_number)
    except Order.DoesNotExist:
        return api_response(False, "Order not found", {}, 404)

    # 🔥 DERIVE payment success from transactions
    payment_success = PaymentTransaction.objects.filter(
        installment__order=order,
        status__in=["verified", "settled"],
    ).exists()

    # 🔥 FINALIZE full-payment orders
    if not order.is_installment and payment_success and order.status != "completed":
        order.payment_status = "completed"
        order.mark_as_completed()

    # Determine payment state
    if payment_success:
        payment_state = "completed"
    elif order.payment_status == "partial":
        payment_state = "partial"
    elif order.status == "failed":
        payment_state = "failed"
    else:
        payment_state = "pending"

    courses = list(
        order.enrollments.filter(is_active=True)
        .values_list("course__title", flat=True)
    )

    return api_response(
        True,
        "Order status",
        {
            "order_number": order.order_number,
            "status": order.status,
            "payment_status": order.payment_status,
            "payment_state": payment_state,
            "payment_verified": payment_state in ("partial", "completed"),
            "is_installment": order.is_installment,
            "installments_paid": order.installments_paid,
            "installment_plan": order.installment_plan,
            "enrolled_courses": courses,
        },
    )



class InstallmentPaymentInitiateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get("order_id")
        if not order_id:
            return api_response(False, "Order ID is required", {}, status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return api_response(False, "Order not found", {}, status.HTTP_404_NOT_FOUND)

        if not order.is_installment:
            return api_response(False, "Order is not installment based", {}, status.HTTP_400_BAD_REQUEST)

        if order.is_fully_paid():
            return api_response(
                False,
                "All installments already paid",
                {},
                status.HTTP_400_BAD_REQUEST,
            )

        next_installment = (
            order.installment_payments
            .filter(status="pending")
            .order_by("installment_number")
            .first()
        )

        if not next_installment:
            return api_response(False, "No pending installment available", {}, status.HTTP_400_BAD_REQUEST)

        gateway = SSLCommerzPayment()
        session = gateway.init_payment(order, amount=next_installment.amount)

        order.status = "processing"
        order.payment_method = "ssl_commerce"
        order.payment_id = session.get("sessionkey", "")
        order.save(update_fields=["status", "payment_method", "payment_id"])

        return api_response(
            True,
            "Installment payment session initialized",
            {
                "payment_url": session.get("GatewayPageURL"),
                "session_key": session.get("sessionkey"),
                "order_number": order.order_number,
                "installment_number": next_installment.installment_number,
                "amount": str(next_installment.amount),
                "due_date": next_installment.due_date,
                "currency": order.currency,
            },
        )



class InstallmentSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return api_response(False, "Order not found", {}, 404)

        if not order.is_installment:
            return api_response(False, "Order is not installment based", {}, 400)

        next_installment = (
            order.installment_payments
            .filter(status="pending")
            .order_by("installment_number")
            .first()
        )

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
            "Installment summary",
            {
                "order_number": order.order_number,
                "installments_paid": order.installments_paid,
                "installment_plan": order.installment_plan,
                "next_installment": next_data,
                "remaining_amount": str(order.get_remaining_amount()),
                "is_fully_paid": order.is_fully_paid(),
                "payment_status": order.payment_status,
            },
        )

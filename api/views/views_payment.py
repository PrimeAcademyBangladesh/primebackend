"""
Payment gateway views for SSLCommerz integration.

Single initiate endpoint supports:
- Full payment
- Installment payment (first + next installments)

Webhook (IPN) is the single source of truth.
"""

from decimal import Decimal
import logging

from django.conf import settings
from django.db import transaction
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from api.models.models_order import Enrollment, Order, OrderInstallment
from api.utils.response_utils import api_response
from api.utils.sslcommerz import SSLCommerzError, SSLCommerzPayment

logger = logging.getLogger(__name__)


# ======================================================
# COMMON SERIALIZERS
# ======================================================

class BaseResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()


class OrderIdSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()


# ======================================================
# PAYMENT INITIATE SERIALIZERS
# ======================================================

class PaymentInitiateResponseDataSerializer(serializers.Serializer):
    payment_url = serializers.URLField()
    session_key = serializers.CharField()
    order_number = serializers.CharField()
    amount = serializers.CharField()
    currency = serializers.CharField()
    payment_type = serializers.CharField()
    installment_number = serializers.IntegerField(required=False)


class PaymentInitiateResponseSerializer(BaseResponseSerializer):
    data = PaymentInitiateResponseDataSerializer(required=False)


# ======================================================
# INSTALLMENT SUMMARY SERIALIZERS
# ======================================================

class InstallmentSummaryNextSerializer(serializers.Serializer):
    installment_number = serializers.IntegerField()
    amount = serializers.CharField()
    due_date = serializers.DateTimeField()
    is_overdue = serializers.BooleanField()
    days_until_due = serializers.IntegerField()


class InstallmentSummaryResponseDataSerializer(serializers.Serializer):
    order_number = serializers.CharField()
    installments_paid = serializers.IntegerField()
    installment_plan = serializers.IntegerField()
    next_installment = InstallmentSummaryNextSerializer(required=False, allow_null=True)
    remaining_amount = serializers.CharField()
    is_fully_paid = serializers.BooleanField()


class InstallmentSummaryResponseSerializer(BaseResponseSerializer):
    data = InstallmentSummaryResponseDataSerializer(required=False)


class VerifyPaymentResponseDataSerializer(serializers.Serializer):
    order_number = serializers.CharField()
    status = serializers.CharField()
    payment_verified = serializers.BooleanField()
    enrolled_courses = serializers.ListField(
        child=serializers.CharField()
    )


class VerifyPaymentResponseSerializer(BaseResponseSerializer):
    data = VerifyPaymentResponseDataSerializer(required=False)


class VerifyPaymentRequestSerializer(serializers.Serializer):
    order_number = serializers.CharField()


# ======================================================
# PAYMENT INITIATE VIEW (FULL + INSTALLMENT)
# ======================================================

@extend_schema(
    summary="Initiate payment",
    request=OrderIdSerializer,
    responses=PaymentInitiateResponseSerializer,
    tags=["Payment"],
)
class PaymentInitiateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get("order_id")

        if not order_id:
            return api_response(False, "Order ID is required", {}, status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.select_related("user").get(id=order_id)

            if not request.user.is_staff and order.user != request.user:
                return api_response(False, "You can only pay your own orders", {}, status.HTTP_403_FORBIDDEN)

            if order.status not in ["pending", "processing"]:
                return api_response(
                    False,
                    f"Order cannot be paid. Current status: {order.get_status_display()}",
                    {},
                    status.HTTP_400_BAD_REQUEST,
                )

            amount_to_pay = order.total_amount
            payment_type = "full"
            installment_number = None
            custom_fields = {}
            pending_installment = None

            # -------- INSTALLMENT LOGIC --------
            if order.is_installment:
                pending_installment = (
                    order.installment_payments
                    .filter(status="pending")
                    .order_by("installment_number")
                    .first()
                )

                if not pending_installment:
                    return api_response(False, "All installments already paid", {}, status.HTTP_400_BAD_REQUEST)

                amount_to_pay = pending_installment.amount
                payment_type = "installment"
                installment_number = pending_installment.installment_number

                custom_fields = {
                    "value_a": str(pending_installment.id),
                    "value_b": str(installment_number),
                    "value_c": payment_type,
                    "value_d": str(order.id),
                }

            # -------- INIT GATEWAY --------
            gateway = SSLCommerzPayment()

            try:
                session_data = gateway.init_payment(order=order, amount=amount_to_pay, **custom_fields)
            except SSLCommerzError as e:
                return api_response(False, f"Gateway error: {str(e)}", {}, status.HTTP_500_INTERNAL_SERVER_ERROR)

            # -------- SAVE METADATA ONLY --------
            with transaction.atomic():
                order.payment_method = "ssl_commerce"
                order.save(update_fields=["payment_method", "updated_at"])

                if pending_installment:
                    pending_installment.update_extra_data({
                        "session_key": session_data.get("sessionkey"),
                        "gateway_page_url": session_data.get("GatewayPageURL"),
                        "initiated_at": timezone.now().isoformat(),
                    })

            response_data = {
                "payment_url": session_data.get("GatewayPageURL"),
                "session_key": session_data.get("sessionkey"),
                "order_number": order.order_number,
                "amount": str(amount_to_pay),
                "currency": order.currency,
                "payment_type": payment_type,
            }

            if installment_number:
                response_data["installment_number"] = installment_number

            return api_response(True, "Payment session initialized", response_data)

        except Order.DoesNotExist:
            return api_response(False, "Order not found", {}, status.HTTP_404_NOT_FOUND)


# ======================================================
# PAYMENT WEBHOOK (IPN)
# ======================================================

@extend_schema(summary="SSLCommerz IPN", tags=["Payment"])
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def payment_webhook(request):
    def get_param(key):
        return request.data.get(key) or request.POST.get(key)

    try:
        tran_id = get_param("tran_id")
        val_id = get_param("val_id")
        amount = get_param("amount")
        status_raw = get_param("status")
        card_type = get_param("card_type")

        installment_id = get_param("value_a")
        payment_type = get_param("value_c")

        if not tran_id or not val_id:
            return api_response(False, "Missing required parameters", {}, status.HTTP_400_BAD_REQUEST)

        order_number = "-".join(tran_id.split("-")[:3])

        try:
            order = Order.objects.select_for_update().get(order_number=order_number)
        except Order.DoesNotExist:
            return api_response(False, "Order not found", {}, status.HTTP_404_NOT_FOUND)

        gateway = SSLCommerzPayment()
        is_valid, _ = gateway.validate_payment(val_id, Decimal(amount))

        if not is_valid or status_raw not in ["VALID", "VALIDATED"]:
            with transaction.atomic():
                order.status = "failed"
                order.payment_status = "failed"
                order.save()
            return api_response(False, "Payment validation failed", {}, status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():

            # -------- INSTALLMENT PAYMENT --------
            if payment_type == "installment" and installment_id:
                installment = OrderInstallment.objects.select_for_update().get(id=installment_id, order=order)

                if installment.status == "paid":
                    return api_response(True, "Installment already processed", {})

                installment.mark_as_paid(
                    payment_id=val_id,
                    payment_method=card_type or "ssl_commerce",
                    gateway_transaction_id=tran_id,
                )

                order.refresh_from_db()

                if order.installments_paid == 1:
                    for item in order.items.all():
                        Enrollment.objects.get_or_create(
                            user=order.user,
                            batch=item.batch,
                            defaults={"course": item.course, "order": order},
                        )
                    order.status = "processing"
                    order.payment_status = "partial"

                elif order.is_fully_paid():
                    order.mark_as_completed()
                    order.payment_status = "completed"

                else:
                    order.status = "processing"
                    order.payment_status = "partial"

                order.save()

                return api_response(
                    True,
                    "Installment paid",
                    {
                        "order_number": order.order_number,
                        "installments_paid": order.installments_paid,
                        "installment_plan": order.installment_plan,
                        "is_fully_paid": order.is_fully_paid(),
                    },
                )

            # -------- FULL PAYMENT --------
            order.payment_id = tran_id
            order.payment_method = card_type or "ssl_commerce"
            order.mark_as_completed()

            return api_response(
                True,
                "Payment completed",
                {
                    "order_number": order.order_number,
                    "status": order.status,
                    "enrollments": order.enrollments.count(),
                },
            )

    except Exception as e:
        logger.exception("Webhook error")
        return api_response(False, "Server error", {}, status.HTTP_500_INTERNAL_SERVER_ERROR)


# ======================================================
# REDIRECT HANDLERS
# ======================================================

@csrf_exempt
def payment_success_redirect(request):
    store_id = request.POST.get("store_id")
    if request.method == "POST" and store_id != settings.SSLCOMMERZ_STORE_ID:
        return HttpResponseForbidden("Invalid request")

    tran_id = request.POST.get("tran_id") or request.GET.get("tran_id", "")
    return HttpResponseRedirect(f"{settings.FRONTEND_URL}/payment/success?tran_id={tran_id}")


@csrf_exempt
def payment_fail_redirect(request):
    store_id = request.POST.get("store_id")
    if request.method == "POST" and store_id != settings.SSLCOMMERZ_STORE_ID:
        return HttpResponseForbidden("Invalid request")

    tran_id = request.POST.get("tran_id") or request.GET.get("tran_id", "")
    return HttpResponseRedirect(f"{settings.FRONTEND_URL}/payment/fail?tran_id={tran_id}")


@csrf_exempt
def payment_cancel_redirect(request):
    store_id = request.POST.get("store_id")
    if request.method == "POST" and store_id != settings.SSLCOMMERZ_STORE_ID:
        return HttpResponseForbidden("Invalid request")

    tran_id = request.POST.get("tran_id") or request.GET.get("tran_id", "")
    return HttpResponseRedirect(f"{settings.FRONTEND_URL}/payment/cancel?tran_id={tran_id}")


# ======================================================
# INSTALLMENT SUMMARY
# ======================================================

@extend_schema(
    summary="Installment summary",
    responses=InstallmentSummaryResponseSerializer,
    tags=["Installment"],
)
class InstallmentSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id, user=request.user)

            if not order.is_installment:
                return api_response(False, "Order is not installment based", {}, status.HTTP_400_BAD_REQUEST)

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
                },
            )

        except Order.DoesNotExist:
            return api_response(False, "Order not found", {}, status.HTTP_404_NOT_FOUND)


@extend_schema(
    summary="Verify payment status",
    description=(
        "Used by frontend after payment redirect to verify payment status. "
        "Supports both authenticated and unauthenticated access."
    ),
    request=VerifyPaymentRequestSerializer,
    responses={
        200: VerifyPaymentResponseSerializer,
        400: VerifyPaymentResponseSerializer,
        403: VerifyPaymentResponseSerializer,
        404: VerifyPaymentResponseSerializer,
    },
    tags=["Course - Payment"],
)
@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def verify_payment(request):
    """
    Verify payment status for an order.

    Called by frontend after payment redirect.

    Accepts:
    - GET  ?order_number=XXX
    - POST {"order_number": "XXX"}
    """

    # ---------------------------
    # 1. READ INPUT
    # ---------------------------
    if request.method == "GET":
        order_number = request.GET.get("order_number")
    else:
        order_number = request.data.get("order_number")

    if not order_number:
        return api_response(
            False,
            "Order number is required",
            {},
            status.HTTP_400_BAD_REQUEST,
        )

    try:
        # ---------------------------
        # 2. FETCH ORDER
        # ---------------------------
        order = Order.objects.get(order_number=order_number)


        # Optional ownership check
        if request.user.is_authenticated:
            if not request.user.is_staff and order.user != request.user:
                return api_response(
                    False,
                    "You can only verify your own orders",
                    {},
                    status.HTTP_403_FORBIDDEN,
                )

        # ---------------------------
        # 3. PREPARE RESPONSE DATA
        # ---------------------------
        enrolled_courses = list(
            order.enrollments
            .filter(is_active=True)
            .values_list("course__title", flat=True)
        )

        return api_response(
            True,
            f"Order status: {order.get_status_display()}",
            {
                "order_number": order.order_number,
                "status": order.status,
                "payment_verified": order.status == "completed",
                "enrolled_courses": enrolled_courses,
            },
            status.HTTP_200_OK,
        )

    except Order.DoesNotExist:
        return api_response(
            False,
            "Order not found",
            {},
            status.HTTP_404_NOT_FOUND,
        )
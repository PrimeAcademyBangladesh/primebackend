"""Payment gateway views for SSLCommerz integration."""

from decimal import Decimal

from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models.models_order import Order
from api.permissions import IsStaff, IsStudent
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
            'application/json': {
                'type': 'object',
                'properties': {
                    'order_id': {'type': 'integer', 'description': 'Order ID to pay for'}
                },
                'required': ['order_id']
            }
        },
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'payment_url': {'type': 'string', 'description': 'SSLCommerz payment page URL'},
                            'order_number': {'type': 'string'},
                            'amount': {'type': 'string'},
                            'currency': {'type': 'string'}
                        }
                    }
                }
            }
        },
        tags=['Course - Payment']
    )
    def post(self, request):
        """Initiate payment for an order."""
        order_id = request.data.get('order_id')
        
        if not order_id:
            return api_response(
                False,
                "Order ID is required",
                {},
                status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get order and verify ownership
            order = Order.objects.select_related('user').get(id=order_id)
            
            # Students can only pay for their own orders, staff can pay for any
            if not request.user.is_staff and order.user != request.user:
                return api_response(
                    False,
                    "You can only pay for your own orders",
                    {},
                    status.HTTP_403_FORBIDDEN
                )
            
            # Check if order can be paid
            if order.status not in ['pending', 'processing']:
                return api_response(
                    False,
                    f"Order cannot be paid. Current status: {order.get_status_display()}",
                    {},
                    status.HTTP_400_BAD_REQUEST
                )
            
            # Initialize payment with SSLCommerz
            gateway = SSLCommerzPayment()
            
            try:
                session_data = gateway.init_payment(order)
                
                # Update order status to processing
                order.status = 'processing'
                order.payment_method = 'ssl_commerce'
                order.save()
                
                # --- Old code: always sent full order amount ---
                # return api_response(
                #     True,
                #     "Payment session initialized successfully",
                #     {
                #         'payment_url': session_data.get('GatewayPageURL'),
                #         'session_key': session_data.get('sessionkey'),
                #         'order_number': order.order_number,
                #         'amount': str(order.total_amount),
                #         'currency': order.currency,
                #     }
                # )

                # --- New code: send next unpaid installment amount if applicable ---
                amount_to_pay = order.total_amount
                if order.is_installment:
                    installment = order.installment_payments.filter(status='pending').order_by('installment_number').first()
                    if installment:
                        amount_to_pay = installment.amount
                return api_response(
                    True,
                    "Payment session initialized successfully",
                    {
                        'payment_url': session_data.get('GatewayPageURL'),
                        'session_key': session_data.get('sessionkey'),
                        'order_number': order.order_number,
                        'amount': str(amount_to_pay),
                        'currency': order.currency,
                    }
                )
                
            except SSLCommerzError as e:
                return api_response(
                    False,
                    f"Payment gateway error: {str(e)}",
                    {},
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Order.DoesNotExist:
            return api_response(
                False,
                "Order not found",
                {},
                status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return api_response(
                False,
                f"Unexpected error: {str(e)}",
                {},
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    summary="Payment webhook (IPN) from SSLCommerz",
    description="Receives payment notifications from SSLCommerz. This endpoint is called by SSLCommerz automatically after payment.",
    request={
        'application/x-www-form-urlencoded': {
            'type': 'object',
            'properties': {
                'tran_id': {'type': 'string', 'description': 'Transaction ID (order_number)'},
                'val_id': {'type': 'string', 'description': 'Validation ID'},
                'amount': {'type': 'string', 'description': 'Payment amount'},
                'status': {'type': 'string', 'description': 'Payment status'},
            }
        }
    },
    responses={200: {'description': 'Webhook processed'}},
    tags=['Course - Payment']
)
@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def payment_webhook(request):
    """
    SSLCommerz IPN (Instant Payment Notification) webhook.
    
    This endpoint receives payment status updates from SSLCommerz.
    It validates the payment and automatically completes the order.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Log incoming webhook data for debugging
        logger.info(f"Payment webhook received: {request.POST.dict() if hasattr(request.POST, 'dict') else request.data}")
        
        # Extract data from POST request
        tran_id = request.data.get('tran_id') or request.POST.get('tran_id')
        val_id = request.data.get('val_id') or request.POST.get('val_id')
        payment_status = request.data.get('status') or request.POST.get('status')
        amount = request.data.get('amount') or request.POST.get('amount')
        bank_tran_id = request.data.get('bank_tran_id') or request.POST.get('bank_tran_id')
        card_type = request.data.get('card_type') or request.POST.get('card_type')
        
        if not tran_id or not val_id:
            logger.error(f"Missing required parameters. tran_id: {tran_id}, val_id: {val_id}")
            return Response({'error': 'Missing required parameters'}, status=400)
        
        # Find order by transaction ID (order_number)
        try:
            order = Order.objects.get(order_number=tran_id)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=404)
        
        # Initialize gateway
        gateway = SSLCommerzPayment()
        
        # Verify webhook signature (optional but recommended)
        # if not gateway.verify_webhook_signature(request.POST.dict()):
        #     return Response({'error': 'Invalid signature'}, status=403)
        
        # Validate payment with SSLCommerz
        is_valid, validation_data = gateway.validate_payment(val_id, order.total_amount)
        
        if is_valid and payment_status in ['VALID', 'VALIDATED']:
            # Payment successful - complete the order
            logger.info(f"Payment validated for order {tran_id}. Completing order...")
            
            order.status = 'completed'
            order.completed_at = timezone.now()
            order.payment_id = bank_tran_id or val_id
            order.payment_method = 'ssl_commerce'
            
            # Store payment details in notes
            order.notes = f"SSLCommerz Payment - Val ID: {val_id}, Bank Tran ID: {bank_tran_id}, Card: {card_type}"
            order.save()
            
            # Create enrollments automatically
            logger.info(f"Creating enrollments for order {order.order_number}...")
            order.mark_as_completed()
            
            enrollment_count = order.enrollments.count()
            logger.info(f"Order {order.order_number} completed. Created {enrollment_count} enrollments.")
            
            return Response({
                'success': True,
                'message': 'Payment verified and order completed',
                'order_number': order.order_number,
                'enrollments_created': enrollment_count
            })
        else:
            # Payment failed or invalid
            order.status = 'failed'
            order.notes = f"Payment failed - Status: {payment_status}, Validation: {validation_data}"
            order.save()
            
            return Response({
                'success': False,
                'message': 'Payment validation failed',
                'order_number': order.order_number
            })
            
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@csrf_exempt
def payment_success_redirect(request):
    """
    Plain Django view - Receives POST from SSLCommerz and redirects to frontend with GET.
    
    SSLCommerz sends POST after payment. This backend endpoint:
    1. Receives POST with payment data
    2. Verifies request is from SSLCommerz (checks store_id)
    3. Validates the payment with SSLCommerz
    4. Updates order status if payment is valid
    5. Redirects to frontend success page with GET + query params
    
    Frontend receives clean GET request and can handle it properly.
    
    NOTE: This is a plain Django view (not DRF) to avoid authentication issues.
    """
    from django.http import HttpResponseRedirect, HttpResponseForbidden, JsonResponse
    from django.conf import settings
    import logging
    import traceback
    
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"=== Payment Success Redirect ===")
        logger.info(f"Method: {request.method}")
        logger.info(f"POST data: {dict(request.POST)}")
        logger.info(f"GET data: {dict(request.GET)}")
        logger.info(f"Headers: {dict(request.headers)}")
        
        if request.method == 'POST':
            # SECURITY: Verify request is from SSLCommerz
            store_id = request.POST.get('store_id', '')
            expected_store_id = getattr(settings, 'SSLCOMMERZ_STORE_ID', '')
            
            if store_id != expected_store_id:
                logger.warning(f"Invalid store_id in payment redirect: {store_id}")
                return HttpResponseForbidden("Invalid request")
            
            # Extract data from SSLCommerz POST
            tran_id = request.POST.get('tran_id', '')
            value_a = request.POST.get('value_a', '')  # order_id
            payment_status = request.POST.get('status', '')
            val_id = request.POST.get('val_id', '')
            amount = request.POST.get('amount', '')
            bank_tran_id = request.POST.get('bank_tran_id', '')
            card_type = request.POST.get('card_type', '')
            
            # Try to validate and complete the order here
            try:
                order = Order.objects.get(order_number=tran_id)
                
                # Only validate if not already completed
                if order.status != 'completed' and val_id:
                    gateway = SSLCommerzPayment()
                    is_valid, validation_data = gateway.validate_payment(val_id, order.total_amount)
                    
                    if is_valid and payment_status in ['VALID', 'VALIDATED']:
                        # Payment successful - complete the order
                        logger.info(f"Payment validated for order {tran_id} in success redirect")
                        
                        order.status = 'completed'
                        order.completed_at = timezone.now()
                        order.payment_id = bank_tran_id or val_id
                        order.payment_method = 'ssl_commerce'
                        order.notes = f"SSLCommerz Payment - Val ID: {val_id}, Bank Tran ID: {bank_tran_id}, Card: {card_type}"
                        order.save()
                        
                        # Create enrollments
                        order.mark_as_completed()
                        logger.info(f"Order {order.order_number} completed in success redirect")
                
            except Order.DoesNotExist:
                logger.error(f"Order not found for tran_id: {tran_id}")
            except Exception as validation_error:
                logger.error(f"Error validating payment in success redirect: {str(validation_error)}")
            
            # Build frontend URL with query parameters
            frontend_url = f"{settings.FRONTEND_URL}/payment/success?tran_id={tran_id}&value_a={value_a}&status={payment_status}"
            
            return HttpResponseRedirect(frontend_url)
        
        # If GET request (direct access), also redirect to frontend
        tran_id = request.GET.get('tran_id', '')
        value_a = request.GET.get('value_a', '')
        payment_status = request.GET.get('status', '')
        frontend_url = f"{settings.FRONTEND_URL}/payment/success?tran_id={tran_id}&value_a={value_a}&status={payment_status}"
        return HttpResponseRedirect(frontend_url)
    
    except Exception as e:
        logger.error(f"Error in payment_success_redirect: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)


@csrf_exempt
def payment_fail_redirect(request):
    """Plain Django view - Redirect failed payments to frontend."""
    from django.http import HttpResponseRedirect, HttpResponseForbidden
    from django.conf import settings
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info(f"Payment fail redirect - Method: {request.method}")
    
    # SECURITY: Verify request is from SSLCommerz (for POST requests)
    if request.method == 'POST':
        store_id = request.POST.get('store_id', '')
        expected_store_id = getattr(settings, 'SSLCOMMERZ_STORE_ID', '')
        
        if store_id != expected_store_id:
            logger.warning(f"Invalid store_id in fail redirect: {store_id}")
            return HttpResponseForbidden("Invalid request")
    
    tran_id = request.POST.get('tran_id', '') or request.GET.get('tran_id', '')
    frontend_url = f"{settings.FRONTEND_URL}/payment/fail?tran_id={tran_id}"
    return HttpResponseRedirect(frontend_url)


@csrf_exempt
def payment_cancel_redirect(request):
    """Plain Django view - Redirect cancelled payments to frontend."""
    from django.http import HttpResponseRedirect, HttpResponseForbidden
    from django.conf import settings
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info(f"Payment cancel redirect - Method: {request.method}")
    
    # SECURITY: Verify request is from SSLCommerz (for POST requests)
    if request.method == 'POST':
        store_id = request.POST.get('store_id', '')
        expected_store_id = getattr(settings, 'SSLCOMMERZ_STORE_ID', '')
        
        if store_id != expected_store_id:
            logger.warning(f"Invalid store_id in cancel redirect: {store_id}")
            return HttpResponseForbidden("Invalid request")
    
    tran_id = request.POST.get('tran_id', '') or request.GET.get('tran_id', '')
    frontend_url = f"{settings.FRONTEND_URL}/payment/cancel?tran_id={tran_id}"
    return HttpResponseRedirect(frontend_url)


@extend_schema(
    summary="Verify payment status",
    description="Manually verify payment status for an order. Used by frontend after payment redirect. Accepts both GET and POST. No authentication required for basic status check.",
    parameters=[
        {
            'name': 'order_number',
            'in': 'query',
            'description': 'Order number to verify (for GET requests)',
            'required': False,
            'schema': {'type': 'string'}
        }
    ],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'order_number': {'type': 'string', 'description': 'Order number to verify (for POST requests)'}
            },
            'required': ['order_number']
        }
    },
    responses={
        200: {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'message': {'type': 'string'},
                'data': {
                    'type': 'object',
                    'properties': {
                        'order_number': {'type': 'string'},
                        'status': {'type': 'string'},
                        'payment_verified': {'type': 'boolean'},
                        'enrolled_courses': {'type': 'array', 'items': {'type': 'string'}}
                    }
                }
            }
        }
    },
    tags=['Course - Payment']
)
@api_view(['GET', 'POST'])
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
    if request.method == 'GET':
        order_number = request.GET.get('order_number')
    else:
        order_number = request.data.get('order_number')
    
    if not order_number:
        return api_response(
            False,
            "Order number is required",
            {},
            status.HTTP_400_BAD_REQUEST
        )
    
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
                    status.HTTP_403_FORBIDDEN
                )
        
        # Get enrolled courses
        enrolled_courses = list(
            order.enrollments.filter(is_active=True)
            .values_list('course__title', flat=True)
        )
        
        return api_response(
            True,
            f"Order status: {order.get_status_display()}",
            {
                'order_number': order.order_number,
                'status': order.status,
                'payment_method': order.payment_method,
                'payment_id': order.payment_id,
                'payment_verified': order.status == 'completed',
                'amount': str(order.total_amount),
                'currency': order.currency,
                'completed_at': order.completed_at,
                'enrolled_courses': enrolled_courses,
                'enrollment_count': len(enrolled_courses),
            }
        )
        
    except Order.DoesNotExist:
        return api_response(
            False,
            "Order not found",
            {},
            status.HTTP_404_NOT_FOUND
        )

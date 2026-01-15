"""SSLCommerz Payment Gateway Integration."""

import requests
from django.conf import settings
from django.utils import timezone


class SSLCommerzError(Exception):
    """Custom exception for SSLCommerz errors."""

    pass


# api/utils/sslcommerz.py

class SSLCommerzPayment:
    """SSLCommerz payment gateway integration"""

    def __init__(self):
        self.store_id = settings.SSLCOMMERZ_STORE_ID
        self.store_password = settings.SSLCOMMERZ_STORE_PASSWORD
        self.is_sandbox = settings.SSLCOMMERZ_IS_SANDBOX

        if self.is_sandbox:
            self.api_url = "https://sandbox.sslcommerz.com/gwprocess/v4/api.php"
        else:
            self.api_url = "https://securepay.sslcommerz.com/gwprocess/v4/api.php"

    def init_payment(self, order, amount, **custom_fields):
        """
        Initialize payment session with SSLCommerz

        Args:
            order: Order instance
            amount: Decimal amount to charge
            **custom_fields: Custom data (value_a, value_b, value_c, value_d)

        Returns:
            dict: Session data with GatewayPageURL and sessionkey
        """

        # Generate unique transaction ID
        tran_id = f"{order.order_number}-{int(timezone.now().timestamp())}"

        # Prepare payment data
        post_data = {
            # Store credentials
            'store_id': self.store_id,
            'store_passwd': self.store_password,

            # Transaction info
            'total_amount': str(amount),
            'currency': order.currency,
            'tran_id': tran_id,

            # URLs
            'success_url': settings.SSLCOMMERZ_SUCCESS_URL,
            'fail_url': settings.SSLCOMMERZ_FAIL_URL,
            'cancel_url': settings.SSLCOMMERZ_CANCEL_URL,
            'ipn_url': settings.SSLCOMMERZ_IPN_URL,

            # Customer information
            'cus_name': order.billing_name or order.user.get_full_name() or order.user.email,
            'cus_email': order.billing_email or order.user.email,
            'cus_phone': order.billing_phone or '01700000000',
            'cus_add1': order.billing_address or 'Dhaka',
            'cus_city': order.billing_city,
            'cus_country': order.billing_country,
            'cus_postcode': order.billing_postcode,

            # Product information
            'product_name': f"Order #{order.order_number}",
            'product_category': 'Course',
            'product_profile': 'general',

            # Shipping (required by SSLCommerz)
            'shipping_method': 'NO',
            'num_of_item': order.get_total_items(),

            # ⭐ CUSTOM FIELDS - Sent to webhook
            **custom_fields  # value_a, value_b, value_c, value_d
        }

        try:
            response = requests.post(
                self.api_url,
                data=post_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            response.raise_for_status()

            result = response.json()

            if result.get('status') == 'SUCCESS':
                return {
                    'GatewayPageURL': result.get('GatewayPageURL'),
                    'sessionkey': result.get('sessionkey'),
                    'tran_id': tran_id,
                }
            else:
                raise SSLCommerzError(
                    result.get('failedreason', 'Unknown error from SSLCommerz')
                )

        except requests.RequestException as e:
            raise SSLCommerzError(f"Network error: {str(e)}")
        except ValueError as e:
            raise SSLCommerzError(f"Invalid response from SSLCommerz: {str(e)}")

    def validate_payment(self, val_id, param):
        pass

# class SSLCommerzPayment:
#     """
#     SSLCommerz payment gateway integration.
#
#     Usage:
#         gateway = SSLCommerzPayment()
#         session_data = gateway.init_payment(order)
#         redirect_url = session_data['GatewayPageURL']
#     """
#
#     def __init__(self):
#         """Initialize SSLCommerz with credentials from settings."""
#         self.store_id = getattr(settings, "SSLCOMMERZ_STORE_ID", "")
#         self.store_password = getattr(settings, "SSLCOMMERZ_STORE_PASSWORD", "")
#         self.is_sandbox = getattr(settings, "SSLCOMMERZ_IS_SANDBOX", True)
#
#         # API endpoints
#         if self.is_sandbox:
#             self.session_url = "https://sandbox.sslcommerz.com/gwprocess/v4/api.php"
#             self.validation_url = "https://sandbox.sslcommerz.com/validator/api/validationserverAPI.php"
#         else:
#             self.session_url = "https://securepay.sslcommerz.com/gwprocess/v4/api.php"
#             self.validation_url = "https://securepay.sslcommerz.com/validator/api/validationserverAPI.php"
#
#     def init_payment(self, order, token: str = None, amount: Decimal = None) -> Dict:
#         """
#         Initialize payment session with SSLCommerz.
#
#         Args:
#             order: Order instance
#             token: Optional payment token
#             amount: Optional specific amount (for installment payments). If None, uses order.total_amount
#
#         Returns:
#             dict: Response from SSLCommerz containing GatewayPageURL
#
#         Raises:
#             SSLCommerzError: If payment initialization fails
#         """
#         from api.models.models_order import Order
#
#         # Use provided amount or fall back to total_amount
#         payment_amount = amount if amount is not None else order.total_amount
#
#         # Build payment data
#         post_data = {
#             # Store credentials
#             "store_id": self.store_id,
#             "store_passwd": self.store_password,
#             # Transaction info
#             "total_amount": str(payment_amount),
#             "currency": order.currency,
#             "tran_id": order.order_number,
#             # URLs - Point to BACKEND endpoints (they will redirect to frontend with GET)
#             "success_url": f"{settings.BACKEND_URL}/api/payment/success/",
#             "fail_url": f"{settings.BACKEND_URL}/api/payment/fail/",
#             "cancel_url": f"{settings.BACKEND_URL}/api/payment/cancel/",
#             "ipn_url": f"{settings.BACKEND_URL}/api/payment/webhook/",
#             # Customer info
#             "cus_name": order.billing_name or order.user.get_full_name() or order.user.email,
#             "cus_email": order.billing_email or order.user.email,
#             "cus_phone": order.billing_phone or "",
#             "cus_add1": order.billing_address or "N/A",
#             "cus_city": order.billing_city,
#             "cus_country": order.billing_country,
#             "cus_postcode": order.billing_postcode,
#             # Shipping info (same as billing for digital products)
#             "shipping_method": "NO",
#             "product_name": "Course Enrollment",
#             "product_category": "Education",
#             "product_profile": "digital-good",
#             # Additional
#             "value_a": order.id,  # Store order ID for reference
#             # Use value_b to store the signed payment token when provided (returned by gateway on redirect)
#             "value_b": token if token else order.user.id,
#             "value_c": order.order_number,  # Store order number
#         }
#
#         try:
#             response = requests.post(self.session_url, data=post_data)
#             response.raise_for_status()
#
#             result = response.json()
#
#             if result.get("status") == "SUCCESS":
#                 return result
#             else:
#                 raise SSLCommerzError(f"Payment initialization failed: {result.get('failedreason', 'Unknown error')}")
#
#         except requests.exceptions.RequestException as e:
#             raise SSLCommerzError(f"Network error during payment initialization: {str(e)}")
#         except Exception as e:
#             raise SSLCommerzError(f"Unexpected error: {str(e)}")
#
#     def validate_payment(self, transaction_id: str, amount: Decimal) -> Tuple[bool, Dict]:
#         """
#         Validate payment with SSLCommerz.
#
#         Args:
#             transaction_id: Transaction ID from SSLCommerz
#             amount: Expected payment amount
#
#         Returns:
#             tuple: (is_valid, validation_data)
#         """
#         post_data = {
#             "val_id": transaction_id,
#             "store_id": self.store_id,
#             "store_passwd": self.store_password,
#         }
#
#         try:
#             response = requests.get(self.validation_url, params=post_data)
#             response.raise_for_status()
#
#             result = response.json()
#
#             # Check if validation was successful
#             if result.get("status") == "VALID" or result.get("status") == "VALIDATED":
#                 # Verify amount matches
#                 paid_amount = Decimal(str(result.get("amount", 0)))
#                 if paid_amount >= amount:
#                     return True, result
#                 else:
#                     return False, {"error": "Amount mismatch", "paid": paid_amount, "expected": amount}
#             else:
#                 return False, result
#
#         except Exception as e:
#             return False, {"error": str(e)}
#
#     def verify_webhook_signature(self, post_data: Dict) -> bool:
#         """
#         Verify webhook signature from SSLCommerz IPN.
#
#         Args:
#             post_data: POST data from webhook
#
#         Returns:
#             bool: True if signature is valid
#         """
#         # SSLCommerz sends verify_sign and verify_key
#         verify_sign = post_data.get("verify_sign", "")
#         verify_key = post_data.get("verify_key", "")
#
#         if not verify_sign or not verify_key:
#             return False
#
#         # Generate expected hash
#         # SSLCommerz uses MD5 hash of specific fields
#         hash_string = f"{self.store_password}{verify_key}"
#         expected_hash = hashlib.md5(hash_string.encode()).hexdigest()
#
#         return verify_sign == expected_hash
#
#     def refund_payment(self, bank_tran_id: str, refund_amount: Decimal, refund_remarks: str = "") -> Dict:
#         """
#         Initiate refund for a transaction.
#
#         Args:
#             bank_tran_id: Bank transaction ID from SSLCommerz
#             refund_amount: Amount to refund
#             refund_remarks: Reason for refund
#
#         Returns:
#             dict: Refund response from SSLCommerz
#         """
#         refund_url = f"https://{'sandbox' if self.is_sandbox else 'securepay'}.sslcommerz.com/validator/api/merchantTransIDvalidationAPI.php"
#
#         post_data = {
#             "refund_amount": str(refund_amount),
#             "refund_remarks": refund_remarks or "Course refund",
#             "bank_tran_id": bank_tran_id,
#             "store_id": self.store_id,
#             "store_passwd": self.store_password,
#         }
#
#         try:
#             response = requests.get(refund_url, params=post_data)
#             response.raise_for_status()
#             return response.json()
#         except Exception as e:
#             raise SSLCommerzError(f"Refund failed: {str(e)}")
#
#     def check_transaction_status(self, tran_id: str) -> Dict:
#         """
#         Check transaction status by transaction ID.
#
#         Args:
#             tran_id: Transaction ID (order_number)
#
#         Returns:
#             dict: Transaction status information
#         """
#         query_url = f"https://{'sandbox' if self.is_sandbox else 'securepay'}.sslcommerz.com/validator/api/merchantTransIDvalidationAPI.php"
#
#         post_data = {
#             "tran_id": tran_id,
#             "store_id": self.store_id,
#             "store_passwd": self.store_password,
#         }
#
#         try:
#             response = requests.get(query_url, params=post_data)
#             response.raise_for_status()
#             return response.json()
#         except Exception as e:
#             raise SSLCommerzError(f"Status check failed: {str(e)}")

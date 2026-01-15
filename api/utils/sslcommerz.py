"""
SSLCommerz Payment Gateway Integration
"""

from decimal import Decimal
import requests

from django.conf import settings
from django.utils import timezone


class SSLCommerzError(Exception):
    """Custom exception for SSLCommerz errors."""
    pass


class SSLCommerzPayment:
    """
    SSLCommerz payment gateway integration.
    """

    def __init__(self):
        self.store_id = settings.SSLCOMMERZ_STORE_ID
        self.store_password = settings.SSLCOMMERZ_STORE_PASSWORD
        self.is_sandbox = settings.SSLCOMMERZ_IS_SANDBOX

        if self.is_sandbox:
            self.session_url = "https://sandbox.sslcommerz.com/gwprocess/v4/api.php"
            self.validation_url = "https://sandbox.sslcommerz.com/validator/api/validationserverAPI.php"
        else:
            self.session_url = "https://securepay.sslcommerz.com/gwprocess/v4/api.php"
            self.validation_url = "https://securepay.sslcommerz.com/validator/api/validationserverAPI.php"

    # ======================================================
    # INITIATE PAYMENT
    # ======================================================

    def init_payment(self, order, amount, **custom_fields):
        """
        Initialize payment session with SSLCommerz

        Args:
            order: Order instance
            amount: Decimal amount to charge
            **custom_fields: value_a, value_b, value_c, value_d

        Returns:
            dict: {GatewayPageURL, sessionkey, tran_id}
        """

        tran_id = f"{order.order_number}-{int(timezone.now().timestamp())}"

        post_data = {
            # Store credentials
            "store_id": self.store_id,
            "store_passwd": self.store_password,

            # Transaction
            "total_amount": str(amount),
            "currency": order.currency,
            "tran_id": tran_id,

            # Backend URLs (redirect → frontend handled separately)
            "success_url": f"{settings.BACKEND_URL}/api/payment/success/",
            "fail_url": f"{settings.BACKEND_URL}/api/payment/fail/",
            "cancel_url": f"{settings.BACKEND_URL}/api/payment/cancel/",
            "ipn_url": f"{settings.BACKEND_URL}/api/payment/webhook/",

            # Customer info
            "cus_name": order.billing_name or order.user.get_full_name() or order.user.email,
            "cus_email": order.billing_email or order.user.email,
            "cus_phone": order.billing_phone or "01700000000",
            "cus_add1": order.billing_address or "Dhaka",
            "cus_city": order.billing_city or "Dhaka",
            "cus_country": order.billing_country or "Bangladesh",
            "cus_postcode": order.billing_postcode or "1200",

            # Product info
            "product_name": f"Order #{order.order_number}",
            "product_category": "Course",
            "product_profile": "general",

            # Required by SSLCommerz
            "shipping_method": "NO",
            "num_of_item": order.get_total_items(),

            # ⭐ Custom fields (used in webhook)
            **custom_fields,
        }

        try:
            response = requests.post(
                self.session_url,
                data=post_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()

            if result.get("status") == "SUCCESS":
                return {
                    "GatewayPageURL": result.get("GatewayPageURL"),
                    "sessionkey": result.get("sessionkey"),
                    "tran_id": tran_id,
                }

            raise SSLCommerzError(
                result.get("failedreason", "Unknown error from SSLCommerz")
            )

        except requests.RequestException as e:
            raise SSLCommerzError(f"Network error: {str(e)}")
        except ValueError:
            raise SSLCommerzError("Invalid JSON response from SSLCommerz")

    # ======================================================
    # VALIDATE PAYMENT (USED BY WEBHOOK)
    # ======================================================

    def validate_payment(self, val_id, expected_amount):
        """
        Validate payment using SSLCommerz validation API.

        Args:
            val_id: Validation ID from SSLCommerz
            expected_amount: Decimal expected amount

        Returns:
            (bool, dict): (is_valid, validation_response)
        """

        params = {
            "val_id": val_id,
            "store_id": self.store_id,
            "store_passwd": self.store_password,
            "format": "json",
        }

        try:
            response = requests.get(
                self.validation_url,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()

            if result.get("status") in ("VALID", "VALIDATED"):
                paid_amount = Decimal(str(result.get("amount", "0")))
                return paid_amount >= expected_amount, result

            return False, result

        except Exception as e:
            return False, {"error": str(e)}

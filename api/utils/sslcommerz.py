"""
SSLCommerz Payment Gateway Integration
SAFE + PRODUCTION READY
"""

import hashlib
from decimal import Decimal
from typing import Dict, Tuple

import requests
from django.conf import settings


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
    def init_payment(self, order, amount: Decimal = None) -> Dict:
        """
        Initialize payment session with SSLCommerz.
        """

        payment_amount = amount if amount is not None else order.total_amount

        post_data = {
            # Store credentials
            "store_id": self.store_id,
            "store_passwd": self.store_password,

            # Transaction
            "total_amount": str(payment_amount),
            "currency": order.currency,
            "tran_id": order.order_number,

            # Backend URLs (VERY IMPORTANT)
            "success_url": f"{settings.BACKEND_URL}/api/payment/success/",
            "fail_url": f"{settings.BACKEND_URL}/api/payment/fail/",
            "cancel_url": f"{settings.BACKEND_URL}/api/payment/cancel/",
            "ipn_url": f"{settings.BACKEND_URL}/api/payment/webhook/",

            # Customer info
            "cus_name": order.billing_name or order.user.get_full_name() or order.user.email,
            "cus_email": order.billing_email or order.user.email,
            "cus_phone": order.billing_phone or "01700000000",
            "cus_add1": order.billing_address or "N/A",
            "cus_city": order.billing_city or "Dhaka",
            "cus_country": order.billing_country or "Bangladesh",
            "cus_postcode": order.billing_postcode or "1200",

            # Product info
            "product_name": f"Order {order.order_number}",
            "product_category": "Education",
            "product_profile": "digital",

            # REQUIRED FIELDS
            "shipping_method": "NO",
            "num_of_item": order.get_total_items(),

            # ⭐ CRITICAL: Custom fields (USED BY WEBHOOK)
            "value_a": str(order.id),          # order_id
            "value_b": str(order.user.id),     # user_id
            "value_c": "full",                 # payment type
            "value_d": order.order_number,     # order number
        }

        try:
            response = requests.post(
                self.session_url,
                data=post_data,
                timeout=15,  # 🔥 REQUIRED
            )
            response.raise_for_status()

            try:
                result = response.json()
            except ValueError:
                raise SSLCommerzError("Invalid JSON response from SSLCommerz")

            if result.get("status") == "SUCCESS":
                return result

            raise SSLCommerzError(
                result.get("failedreason", "Payment initialization failed")
            )

        except requests.Timeout:
            raise SSLCommerzError("SSLCommerz timeout")
        except requests.RequestException as e:
            raise SSLCommerzError(f"Network error: {str(e)}")

    # ======================================================
    # VALIDATE PAYMENT
    # ======================================================
    def validate_payment(self, val_id: str, expected_amount: Decimal) -> Tuple[bool, Dict]:
        """
        Validate payment with SSLCommerz.
        """

        if not isinstance(expected_amount, Decimal):
            expected_amount = Decimal(str(expected_amount))

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
                timeout=15,  # 🔥 REQUIRED
            )
            response.raise_for_status()

            try:
                result = response.json()
            except ValueError:
                return False, {"error": "Invalid JSON from validation API"}

            if result.get("status") in ("VALID", "VALIDATED"):
                paid_amount = Decimal(str(result.get("amount", "0")))
                return paid_amount >= expected_amount, result

            return False, result

        except requests.Timeout:
            return False, {"error": "SSLCommerz validation timeout"}
        except requests.RequestException as e:
            return False, {"error": str(e)}

    # ======================================================
    # VERIFY WEBHOOK SIGNATURE (OPTIONAL)
    # ======================================================
    def verify_webhook_signature(self, post_data: Dict) -> bool:
        verify_sign = post_data.get("verify_sign")
        verify_key = post_data.get("verify_key")

        if not verify_sign or not verify_key:
            return False

        raw = f"{self.store_password}{verify_key}"
        expected = hashlib.md5(raw.encode()).hexdigest()

        return verify_sign == expected

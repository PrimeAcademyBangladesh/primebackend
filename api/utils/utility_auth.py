"""Authentication helpers and secure login view.

Provides SecureLoginView which wraps login serializer validation and
returns the project's api_response envelope on success/failure.
"""

from django.forms import ValidationError

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from ..models.models_auth import CustomUser
from ..utils.response_utils import api_response
from ..utils.throttles import LoginRateThrottle


def merge_guest_cart_to_user(user, session_key):
    """
    Merge guest cart into user cart after login.
    Called automatically when a guest with items in cart logs in.

    Returns:
        tuple: (user_cart, merged_count) - User's cart object and number of items merged
    """
    from ..models.models_cart import Cart, CartItem

    # Get or create user cart first
    user_cart, _ = Cart.objects.get_or_create(user=user)

    if not session_key:
        return user_cart, 0

    try:
        # Get guest cart by session key
        guest_cart = Cart.objects.filter(session_key=session_key, user__isnull=True).first()

        if not guest_cart or not guest_cart.items.exists():
            return user_cart, 0  # No guest cart or empty cart

        # Move items from guest cart to user cart
        merged_count = 0
        for guest_item in guest_cart.items.all():
            # Check if course already in user cart
            if not user_cart.items.filter(course=guest_item.course).exists():
                # Move item to user cart
                guest_item.cart = user_cart
                guest_item.save()
                merged_count += 1
            else:
                # Course already in user cart, just delete the duplicate
                guest_item.delete()

        # Delete the now-empty guest cart
        guest_cart.delete()

        return user_cart, merged_count

    except Exception as e:
        # Log error but don't fail login
        print(f"Error merging guest cart: {e}")
        return user_cart, 0


class SecureLoginView(APIView):
    throttle_classes = [LoginRateThrottle]
    permission_classes = [permissions.AllowAny]
    role_allowed: CustomUser.Role = None

    def post(self, request, *args, **kwargs):
        from api.serializers.serializers_auth import LoginSerializer

        serializer = LoginSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            detail = e.detail
            if isinstance(detail, dict):
                detail = next(iter(detail.values()))
            if isinstance(detail, list):
                detail = detail[0]
            return api_response(False, str(detail), {}, status.HTTP_401_UNAUTHORIZED)

        user = serializer.validated_data["user"]

        if self.role_allowed and user.role != self.role_allowed:
            return api_response(False, "User does not have permission to login here.", {}, status.HTTP_401_UNAUTHORIZED)

        # Merge guest cart to user cart if session has items
        session_key = request.session.session_key
        merged_items = 0
        if session_key:
            _, merged_items = merge_guest_cart_to_user(user, session_key)

        refresh = RefreshToken.for_user(user)
        token = {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }

        response_data = {
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
            },
            "tokens": token,
        }

        # Add cart merge info if items were merged
        if merged_items and merged_items > 0:
            response_data["cart_merged"] = True
            response_data["cart_items_merged"] = merged_items

        return api_response(True, "Login successful", response_data, status.HTTP_200_OK)

"""Authentication and profile API views.

Provides view classes for:
- student/teacher/admin login and logout flows,
- registration, email verification and resend endpoints,
- password reset and change endpoints,
- student/teacher profile retrieve/update endpoints,
- admin management viewsets for students and teachers.

Docstrings are intentionally short — they explain responsibilities for
Pylance and human readers without changing behavior.
"""

import datetime
import logging
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.utils import timezone

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import filters, generics, permissions, status
from rest_framework.generics import CreateAPIView, GenericAPIView
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from api.models.models_auth import CustomUser, Profile, Skill
from api.permissions import IsAdmin, IsStaff, IsStudent, IsTeacher
from api.serializers.serializers_auth import (
    ChangePasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetSerializer,
    RequestPhoneChangeSerializer,
    ResendVerificationEmailSerializer,
    SkillSerializer,
    StudentProfileUpdateSerializer,
    StudentRegistrationSerializer,
    TeacherCreateSerializer,
    TeacherProfileUpdateSerializer,
    UserProfileSerializer,
    VerifyEmailSerializer,
)
from api.utils.email_utils import send_system_email
from api.utils.filters_utils import UserFilter
from api.utils.pagination import StandardResultsSetPagination
from api.utils.response_utils import api_response
from api.utils.resposne_return import APIResponseSerializer
from api.utils.url_utils import build_full_url
from api.utils.utility_auth import SecureLoginView
from api.views.views_base import BaseAdminViewSet

logger = logging.getLogger(__name__)

# =============================================
# AUTHENTICATION & REGISTRATION VIEWS
# =============================================


@extend_schema(
    tags=["Students"],
    summary="Register a new student",
    description="Registers a new student and sends a verification email.",
    responses=APIResponseSerializer,
)
class StudentRegisterView(CreateAPIView):
    """Register a new student and send verification email."""

    permission_classes = [permissions.AllowAny]
    serializer_class = StudentRegistrationSerializer
    throttle_classes = [AnonRateThrottle]

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        msg = "Student registered successfully. Please check your email for verification."
        return api_response(True, msg, response.data, response.status_code)


# Student login view
@extend_schema(
    tags=["Students"],
    summary="Login a Student",
    description="Logs in a Student and returns JWT tokens.",
    request=LoginSerializer,
    responses=APIResponseSerializer,
    examples=[
        OpenApiExample(
            "Successful login",
            value={
                "success": True,
                "message": "Login successful",
                "data": {
                    "user": {
                        "id": 38,
                        "email": "youremail@gmail.com",
                        "role": "student",
                    }
                },
                "tokens": {
                    "access": "eIjM4In0.QXaECbo",
                    "refresh": "eIjM4In0.QXaECbo",
                },
            },
            response_only=True,
            status_codes=["200"],
        ),
        OpenApiExample(
            "Invalid credentials",
            value={"success": False, "message": "Invalid credentials", "data": {}},
            response_only=True,
            status_codes=["401"],
        ),
    ],
)
class StudentLoginView(SecureLoginView):
    """Login view for students only."""

    serializer_class = LoginSerializer
    role_allowed = CustomUser.Role.STUDENT


@extend_schema(
    tags=["Teachers"],
    summary="Login a Teacher",
    description="Logs in a Teacher and returns JWT tokens.",
    request=LoginSerializer,
    responses=APIResponseSerializer,
    examples=[
        OpenApiExample(
            "Successful login",
            value={
                "success": True,
                "message": "Login successful",
                "data": {
                    "user": {
                        "id": 38,
                        "email": "youremail@gmail.com",
                        "role": "teacher",
                    }
                },
                "tokens": {
                    "access": "eIjM4In0.QXaECbo",
                    "refresh": "eIjM4In0.QXaECbo",
                },
            },
            response_only=True,
            status_codes=["200"],
        ),
        OpenApiExample(
            "Invalid credentials",
            value={"success": False, "message": "Invalid credentials", "data": {}},
            response_only=True,
            status_codes=["401"],
        ),
    ],
)
class TeacherLoginView(SecureLoginView):
    """Login view for teachers only."""

    serializer_class = LoginSerializer
    role_allowed = CustomUser.Role.TEACHER




@extend_schema(
    tags=["Shared Authentication"],
    summary="Logout a user",
    responses=APIResponseSerializer,
    request=LogoutSerializer,
)
class LogoutView(APIView):
    """Logout user by blacklisting refresh token."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LogoutSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data["refresh"])
            token.blacklist()
            return api_response(True, "Logout successful.", {}, status.HTTP_200_OK)
        except TokenError:
            return api_response(False, "Token is invalid or expired.", {}, status.HTTP_400_BAD_REQUEST)


# =============================================
# USER PROFILE VIEWS
# =============================================


@extend_schema(
    tags=["Shared Authentication"],
    methods=["GET"],
    summary="Get current user's profile",
    description="Retrieve the logged-in user's profile for any role",
    responses=APIResponseSerializer,
)
@extend_schema(
    tags=["Shared Authentication"],
    methods=["PUT", "PATCH"],
    summary="Update current user's profile",
    description="Update the logged-in user's profile. Serializer chosen based on user role.",
    request=StudentProfileUpdateSerializer,
    responses=APIResponseSerializer,
)
class CurrentUserProfileView(generics.RetrieveUpdateAPIView):
    """Retrieve or update the authenticated user's profile regardless of role.

    This view picks an update serializer based on the user's role so existing
    student/teacher update serializers are reused.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        user = self.request.user
        Profile.objects.get_or_create(user=user)
        return user

    def get_serializer_class(self):
        # Read operations use the unified UserProfileSerializer
        if self.request.method in ["PUT", "PATCH"]:
            role = getattr(self.request.user, "role", None)
            if role == CustomUser.Role.TEACHER:
                return TeacherProfileUpdateSerializer
            if role == CustomUser.Role.STUDENT:
                return StudentProfileUpdateSerializer
            # Fallback to student update serializer which is generic enough
            return StudentProfileUpdateSerializer
        return UserProfileSerializer

    def retrieve(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = self.get_serializer(user)
        return api_response(True, "Profile retrieved successfully.", serializer.data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", True)
        user = self.get_object()

        serializer = self.get_serializer(
            user,
            data=request.data or {},
            partial=partial,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        updated_user = serializer.save()

        full_serializer = UserProfileSerializer(updated_user, context={"request": request})
        return api_response(True, "Profile updated successfully.", full_serializer.data)


# =============================================
# ADMIN MANAGEMENT VIEWS (using ViewSets)
# =============================================


@extend_schema(
    tags=["Admin Management for Students"],
    summary="Delete a student",
)
class AdminStudentViewSet(BaseAdminViewSet):
    """Admin viewset for managing students."""

    pagination_class = StandardResultsSetPagination
    queryset = CustomUser.objects.filter(role=CustomUser.Role.STUDENT).order_by("-date_joined")

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    filterset_class = UserFilter

    search_fields = ["email", "first_name", "last_name", "phone", "student_id"]
    # Allow admins to explicitly order by common user fields
    ordering_fields = ["date_joined", "last_login", "email"]

    # Handle full_name ordering by combining first_name and last_name
    def get_ordering(self):
        """Handle full_name ordering by combining first_name and last_name."""
        ordering = self.request.query_params.get("ordering", "")

        if ordering == "full_name":
            return ["first_name", "last_name"]
        elif ordering == "-full_name":
            return ["-first_name", "-last_name"]

        return super().get_ordering()

    def get_serializer_class(self):
        """Return serializer class based on action."""
        if self.action == "create":
            return StudentRegistrationSerializer
        if self.action in ("list", "retrieve"):
            return UserProfileSerializer
        return StudentProfileUpdateSerializer

    def get_permissions(self):
        return [IsAdmin()]

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        try:
            instance = self.get_object()
            data = UserProfileSerializer(instance, context={"request": request}).data
        except Exception:
            data = getattr(response, "data", {})
        return api_response(True, "Student updated successfully.", data)

    def partial_update(self, request, *args, **kwargs):
        response = super().partial_update(request, *args, **kwargs)
        try:
            instance = self.get_object()
            data = UserProfileSerializer(instance, context={"request": request}).data
        except Exception:
            data = getattr(response, "data", {})
        return api_response(True, "Student updated successfully.", data)


# Admin - Teachers
# ===========================
@extend_schema(
    tags=["Admin Management for Teachers"],
    summary="List teachers (paginated)",
)
class AdminTeacherViewSet(BaseAdminViewSet):
    """Admin viewset for managing teachers."""

    pagination_class = StandardResultsSetPagination
    queryset = CustomUser.objects.filter(role=CustomUser.Role.TEACHER).order_by("-date_joined")

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    filterset_class = UserFilter

    search_fields = ["email", "first_name", "last_name", "phone"]
    # Allow admins to explicitly order by common user fields
    ordering_fields = ["date_joined", "last_login", "email"]

    def get_serializer_class(self):
        """Return serializer class based on action."""
        if self.action == "create":
            return TeacherCreateSerializer
        if self.action in ("list", "retrieve"):
            return UserProfileSerializer
        return TeacherProfileUpdateSerializer

    def get_permissions(self):
        return [IsAdmin()]

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        try:
            instance = self.get_object()
            data = UserProfileSerializer(instance, context={"request": request}).data
        except Exception:
            data = getattr(response, "data", {})
        return api_response(True, "Teacher updated successfully.", data)

    def partial_update(self, request, *args, **kwargs):
        response = super().partial_update(request, *args, **kwargs)
        try:
            instance = self.get_object()
            data = UserProfileSerializer(instance, context={"request": request}).data
        except Exception:
            data = getattr(response, "data", {})
        return api_response(True, "Teacher partially updated successfully.", data)


@extend_schema(
    tags=["Admin Authentication"],
    summary="Admin login",
    request=LoginSerializer,
    responses={200: LoginSerializer, 401: {"detail": "string"}},
)
class AdminLoginView(SecureLoginView):
    """Login view for admin users only."""

    serializer_class = LoginSerializer
    role_allowed = CustomUser.Role.ADMIN


@extend_schema(
    tags=["Admin Authentication"],
    summary="Staff login",
    request=LoginSerializer,
    responses={200: LoginSerializer, 401: {"detail": "string"}},
)
class StaffLoginView(SecureLoginView):
    """Login view for staff users only."""

    serializer_class = LoginSerializer
    role_allowed = CustomUser.Role.STAFF


@extend_schema(
    tags=["Admin Authentication"],
    summary="Accountant login",
    request=LoginSerializer,
    responses={200: LoginSerializer, 401: {"detail": "string"}},
)
class AccountantLoginView(SecureLoginView):
    """Login view for accountant users only."""

    serializer_class = LoginSerializer
    role_allowed = CustomUser.Role.ACCOUNTANT


@extend_schema(
    tags=["Students"],
    summary="Verify email and activate account for students",
    description="Activates a student account when presented with a valid signed token.",
    responses=APIResponseSerializer,
)
class VerifyEmailView(GenericAPIView):
    """Activate user account with a valid signed token."""

    permission_classes = [permissions.AllowAny]
    serializer_class = VerifyEmailSerializer

    def get(self, request, *args, **kwargs):
        token = request.query_params.get("token")

        if not token:
            return api_response(
                False,
                "Token is required.",
                {},
                status.HTTP_400_BAD_REQUEST,
            )

        signer = TimestampSigner()

        try:
            unsigned = signer.unsign(token, max_age=60 * 60 * 24)
            user = CustomUser.objects.filter(pk=unsigned).first()

            if not user:
                return api_response(
                    False,
                    "User not found.",
                    {},
                    status.HTTP_400_BAD_REQUEST,
                )

            if user.is_active:
                return api_response(
                    True,
                    "Account already active.",
                    {"email": user.email},
                    status.HTTP_200_OK,
                )

            if user.is_enabled is False:
                return api_response(
                    False,
                    "Your account is disabled. Please contact the admin to enable your account.",
                    {},
                    status.HTTP_403_FORBIDDEN,
                )

            user.is_active = True
            user.save()

            # Merge guest cart to user cart if session has items
            from api.utils.cart_utils import merge_guest_cart_to_user

            session_key = request.session.session_key
            merged_items = 0
            if session_key:
                _, merged_items = merge_guest_cart_to_user(user, session_key)

            # Generate JWT tokens for auto-login
            refresh = RefreshToken.for_user(user)
            tokens = {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }

            response_data = {
                "email": user.email,
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "role": user.role,
                },
                "tokens": tokens,
            }

            # Add cart merge info if items were merged
            if merged_items and merged_items > 0:
                response_data["cart_merged"] = True
                response_data["cart_items_merged"] = merged_items

            return api_response(
                True,
                "Account activated and logged in successfully.",
                response_data,
                status.HTTP_200_OK,
            )

        except SignatureExpired:
            # Allow client to know they can request a resend
            return api_response(
                False,
                "Token expired.",
                {"can_resend": True, "resend_url": build_full_url("resend-verification")},
                status.HTTP_400_BAD_REQUEST,
            )

        except BadSignature:
            return api_response(
                False,
                "Invalid token.",
                {"can_resend": True, "resend_url": build_full_url("resend-verification")},
                status.HTTP_400_BAD_REQUEST,
            )


@extend_schema(
    tags=["Students"],
    summary="Resend email verification link",
    request=ResendVerificationEmailSerializer,
    responses=APIResponseSerializer,
)
class ResendVerificationEmailView(GenericAPIView):
    """Resend email verification link to inactive students."""

    serializer_class = ResendVerificationEmailSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "resend"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.context["user"]

        # Generate signed token
        signer = TimestampSigner()
        token = signer.sign(user.pk)

        # Prefer sending a frontend link (so users click and finish the action from the app)
        frontend_base = getattr(settings, "FRONTEND_URL", None)
        if frontend_base:
            fb = frontend_base.rstrip("/")
            # If the provided FRONTEND_VERIFY_URL already looks like a full
            # verification path (contains 'verify' or has a query), use it as
            # supplied. Otherwise treat it as a base URL and append the
            # standard '/verify-email' path.
            if "verify" in fb or "?" in fb or fb.endswith("/"):
                verification_link = f"{fb}?token={token}"
            else:
                verification_link = f"{fb}/verify-student?token={token}"
        else:
            verification_link = build_full_url("verify-student", query_params={"token": token})

        # Send email with template
        try:
            send_system_email(
                subject="Verify your Prime Academy account",
                template_name="emails/verify_email",
                context={"first_name": user.first_name, "verify_url": verification_link},
                recipient_list=[user.email],
            )
        except Exception as e:
            logger.error(f"Failed to send verification email to {user.email}: {str(e)}")
            # You can choose to return error or success for security
            return api_response(
                False, "Failed to send verification email. Please try again later.", {}, status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return api_response(True, "Verification email sent.", {})


@extend_schema(
    tags=["Students"],
    summary="Password reset request send email",
    request=PasswordResetSerializer,
    responses=APIResponseSerializer,
)
class PasswordResetView(APIView):
    """Send password reset email to user."""

    serializer_class = PasswordResetSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            # To avoid user enumeration, return success even if email not found
            return api_response(True, "Password reset email sent to your registered email.", {})

        # Generate signed token
        signer = TimestampSigner()
        token = signer.sign(str(user.pk))

        # Build password reset URL
        reset_url = build_full_url("password-reset-confirm", query_params={"token": token})

        # Send email with template
        try:
            send_system_email(
                subject="Reset your Prime Academy password",
                template_name="emails/password_reset",
                context={
                    "first_name": user.first_name,
                    "reset_url": reset_url,
                },
                recipient_list=[user.email],
            )
        except Exception as e:
            logger.error(f"Failed to send password reset email to {user.email}: {str(e)}")
            # Still return success for security (don't reveal email failure)
            return api_response(True, "Password reset email sent to your registered email.", {})

        return api_response(True, "Password reset email sent to your registered email.", {})


@extend_schema(
    tags=["Students"],
    summary="Confirm password reset with token",
    description="Reset user password using a valid token sent via email. Token is one-time use only.",
    request=PasswordResetConfirmSerializer,
    responses=PasswordResetConfirmSerializer,
)
class PasswordResetConfirmView(APIView):
    """Reset user password with valid token - one-time use only."""

    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        token = request.query_params.get("token")
        if not token:
            return api_response(
                False,
                "This password reset link has expired or is invalid. Please request a new one.",
                {},
                status.HTTP_400_BAD_REQUEST,
            )

        # Validate token
        signer = TimestampSigner()
        try:
            # Unsigned value gives the user PK if token is valid and not expired
            user_pk = signer.unsign(token, max_age=60 * 60 * 24)  # 1 day expiry
            user = CustomUser.objects.get(pk=user_pk)
            # Attempt to extract token creation timestamp. TimestampSigner embeds
            # a base36 timestamp as part of the signature. We try to parse it
            # by splitting from the right and converting base36 -> int.
            token_timestamp = None
            try:
                # TimestampSigner produces tokens with format: "<value>:<ts_b62>:<signature>"
                # Use Django's b62 decoder to get the original timestamp seconds.
                parts = token.split(":")
                ts_part = parts[1] if len(parts) >= 2 else None
                if ts_part:
                    token_ts_int = signing.b62_decode(ts_part)
                    # make timezone-aware datetime
                    token_timestamp = datetime.datetime.fromtimestamp(token_ts_int, tz=datetime.timezone.utc)
            except Exception as e:
                # If extraction fails, leave token_timestamp as None and fall back to
                # conservative behavior (don't allow reuse if last_password_reset is recent)
                logger.warning("Failed to parse timestamp from password reset token: %s", str(e))
                token_timestamp = None
        except SignatureExpired:
            logger.info("Password reset token expired for request path=%s", request.path)
            return api_response(
                False,
                "This password reset link has expired or is invalid. Please request a new one.",
                {},
                status.HTTP_400_BAD_REQUEST,
            )

        except BadSignature:
            logger.info("Password reset token bad signature for request path=%s", request.path)
            return api_response(
                False,
                "This password reset link has expired or is invalid. Please request a new one.",
                {},
                status.HTTP_400_BAD_REQUEST,
            )

        except Exception as e:
            logger.warning("Unexpected error while validating password reset token: %s", str(e))
            return api_response(
                False,
                "This password reset link has expired or is invalid. Please request a new one.",
                {},
                status.HTTP_400_BAD_REQUEST,
            )

        # Check if password was already reset AFTER the token was generated. If
        # we could extract token_timestamp, deny the request only when
        # user.last_password_reset is >= token_timestamp. Otherwise fall back to
        # the previous conservative check (last 24 hours) to avoid accidental reuse.
        if user.last_password_reset:
            if token_timestamp:
                # Use a small tolerance window to avoid rejecting tokens due to
                # second-granularity differences between the token timestamp and
                # the stored `last_password_reset` which has sub-second precision.
                try:
                    last_reset_seconds = int(user.last_password_reset.timestamp())
                    token_seconds = int(token_timestamp.timestamp())
                    # If last_password_reset is at least 2 seconds after token, treat token as stale
                    if last_reset_seconds - token_seconds >= 2:
                        logger.info(
                            "Stale password reset token: user=%s last_password_reset=%s token_ts=%s",
                            user.pk,
                            user.last_password_reset,
                            token_timestamp,
                        )
                        return api_response(
                            False,
                            "This password reset link has already been used. Please request a new one.",
                            {},
                            status.HTTP_400_BAD_REQUEST,
                        )
                except Exception:
                    # Fallback to direct comparison if timestamp extraction fails
                    if user.last_password_reset > token_timestamp:
                        logger.info(
                            "Stale password reset token (fallback): user=%s last_password_reset=%s token_ts=%s",
                            user.pk,
                            user.last_password_reset,
                            token_timestamp,
                        )
                        return api_response(
                            False,
                            "This password reset link has already been used. Please request a new one.",
                            {},
                            status.HTTP_400_BAD_REQUEST,
                        )
            else:
                # Fallback to previous behavior when we couldn't parse token timestamp
                if user.last_password_reset > timezone.now() - timedelta(days=1):
                    return api_response(
                        False,
                        "This password reset link has already been used. Please request a new one.",
                        {},
                        status.HTTP_400_BAD_REQUEST,
                    )

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Reset password and update timestamp
        user.set_password(serializer.validated_data["new_password"])
        user.last_password_reset = timezone.now()
        user.save()

        return api_response(True, "Password has been reset successfully.", {})


@extend_schema(
    tags=["Shared Authentication"],
    summary="Password change for authenticated users",
    responses=APIResponseSerializer,
    request=ChangePasswordSerializer,
)
class PasswordChangeView(APIView):
    """Allow authenticated user to change their password."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # Provide request in context so serializers can access the current user
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            return api_response(False, "Old password is incorrect.", {}, status.HTTP_400_BAD_REQUEST)

        user.set_password(serializer.validated_data["new_password"])
        user.last_password_reset = timezone.now()
        user.save()

        # Return user role in response
        return api_response(
            True,
            "Password updated successfully.",
            {
                "role": user.role,
            },
        )


@extend_schema(
    tags=["Students"],
    summary="Request phone number change for authenticated students",
    request=RequestPhoneChangeSerializer,
    responses=APIResponseSerializer,
)
class RequestPhoneChangeView(GenericAPIView):
    """Allow authenticated students to change their phone number directly."""

    serializer_class = RequestPhoneChangeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        if user.role != CustomUser.Role.STUDENT:
            return api_response(False, "Only students can change their phone number.")

        new_phone = serializer.validated_data["new_phone"]
        user.phone = new_phone
        user.save(update_fields=["phone"])

        return api_response(True, "Phone number updated successfully.", {"phone": user.phone})


@extend_schema_view(
    list=extend_schema(summary="List all skills", responses={200: SkillSerializer}, tags=["Skill"]),
    retrieve=extend_schema(summary="Retrieve a skill by slug", responses={200: SkillSerializer}, tags=["Skill"]),
    create=extend_schema(summary="Create a skill", responses={201: SkillSerializer}, tags=["Skill"]),
    update=extend_schema(summary="Update a skill", responses={200: SkillSerializer}, tags=["Skill"]),
    partial_update=extend_schema(summary="Partially update a skill", responses={200: SkillSerializer}, tags=["Skill"]),
    destroy=extend_schema(summary="Delete a skill", responses={204: None}, tags=["Skill"]),
)
class SkillViewSet(BaseAdminViewSet):
    """
    CRUD for Skills.

    Permissions:
    - List/Retrieve: All authenticated users
    - Create: All authenticated users (students can add skills)
    - Update/Delete: Staff only
    """

    queryset = Skill.objects.all()
    serializer_class = SkillSerializer

    # Add filtering, searching and pagination to the skill admin viewset
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["is_active"]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]

    def get_permissions(self):
        """
        Allow all authenticated users to list, retrieve, and create skills.
        Only staff can update or delete.
        """
        from rest_framework.permissions import IsAuthenticated

        if self.action in ["list", "retrieve", "create"]:
            # All authenticated users can list, view, and create skills
            return [IsAuthenticated()]

        # Update and delete require staff permissions
        return [IsStaff()]

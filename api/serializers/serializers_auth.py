"""All import here"""

import logging

from django.contrib.auth import authenticate
from django.core.signing import TimestampSigner

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from api.utils.url_utils import build_full_url

from ..models.models_auth import CustomUser, Profile, Skill
from ..utils.email_utils import send_system_email
from ..utils.password_utils import validate_password_strength

logger = logging.getLogger(__name__)


class StudentRegistrationSerializer(serializers.ModelSerializer):
    """Student Register Serializer"""

    password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"}, min_length=8)
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        label="Confirm Password",
        style={"input_type": "password"},
        min_length=8,
    )

    email = serializers.EmailField(
        validators=[
            UniqueValidator(
                queryset=CustomUser.objects.all(),
                message="This email is already registered. Please login.",
            )
        ]
    )
    phone = serializers.CharField(
        validators=[
            UniqueValidator(
                queryset=CustomUser.objects.all(),
                message="This phone number is already registered.",
            )
        ]
    )

    student_id = serializers.CharField(read_only=True)

    class Meta:
        """Model configuration for StudentRegistrationSerializer."""

        model = CustomUser
        fields = ["email", "student_id", "password", "password2", "first_name", "last_name", "phone", "is_enabled"]

    def validate_phone(self, value):
        """Validate phone number format."""
        # Remove any spaces, hyphens, etc.
        clean_phone = "".join(filter(str.isdigit, value))

        if len(clean_phone) <= 10:
            raise serializers.ValidationError("Phone number must be more than 10 digits.")
        return clean_phone

    def validate_first_name(self, value):
        """Validate first name."""
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError("First name must be at least 2 characters long.")
        if not cleaned.replace(" ", "").isalpha():
            raise serializers.ValidationError("First name can only contain letters and spaces.")
        return cleaned

    def validate_last_name(self, value):
        """Validate last name."""
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError("Last name must be at least 2 characters long.")
        if not cleaned.replace(" ", "").isalpha():
            raise serializers.ValidationError("Last name can only contain letters and spaces.")
        return cleaned

    def validate_password(self, value):
        """Validate password strength."""
        return validate_password_strength(value)

    def validate(self, attrs):
        """Validate password confirmation."""
        if attrs.get("password") != attrs.get("password2"):
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        """Create user, send verification email, and return user instance."""
        password = validated_data.pop("password")
        validated_data.pop("password2")

        user = CustomUser.objects.create_user(
            role=CustomUser.Role.STUDENT,
            password=password,
            is_active=False,
            **validated_data,
        )

        # Generate signed token and send verification email
        signer = TimestampSigner()
        token = signer.sign(str(user.pk))
        verify_url = build_full_url("verify-student", query_params={"token": token})

        try:
            send_system_email(
                subject="Verify your Prime Academy account",
                template_name="emails/verify_email",
                context={"first_name": user.first_name, "verify_url": verify_url},
                recipient_list=[user.email],
            )
        except Exception as e:
            logger.error(f"Failed to send verification email to {user.email}: {str(e)}")

        return user


class TeacherCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating teacher accounts."""

    class Meta:
        """Meta options for TeacherCreateSerializer."""

        model = CustomUser
        fields = ["email", "password", "first_name", "last_name", "phone"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        """Create an active teacher user (no email verification)."""
        password = validated_data.pop("password", None)
        validated_data.setdefault("is_active", True)
        user = CustomUser.objects.create_user(role=CustomUser.Role.TEACHER, password=password, **validated_data)
        return user


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login. Validates credentials and allowed roles.
    """

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    allowed_roles = None

    def validate(self, attrs):
        """
        Authenticate user and check if active and allowed role.
        """
        email = attrs.get("email")
        password = attrs.get("password")
        user = authenticate(username=email, password=password)

        if not user:
            raise serializers.ValidationError({"detail": "Invalid credentials."})
        # Block login if user is inactive (unverified) or explicitly disabled by admin
        if not user.is_active or not getattr(user, "is_enabled", True):
            raise serializers.ValidationError({"detail": "User account is disabled."})

        allowed = self.allowed_roles
        if allowed is not None:
            roles = allowed if isinstance(allowed, (list, tuple, set)) else [allowed]
            if getattr(user, "role", None) not in roles:
                raise serializers.ValidationError({"detail": "User does not have permission to login here."})

        attrs["user"] = user
        return attrs


class LogoutSerializer(serializers.Serializer):
    """Serializer for logout requests (expects refresh token)."""

    refresh = serializers.CharField(help_text="The refresh token to blacklist", write_only=True)


class SkillSerializer(serializers.ModelSerializer):
    """Serializer for Skill model (id + name)."""

    class Meta:
        model = Skill
        fields = ["id", "name", "is_active"]


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for READ operations - includes nested skills"""

    skills = SkillSerializer(many=True, read_only=True)
    image = serializers.SerializerMethodField(read_only=True)

    class Meta:
        """Configuration for ProfileSerializer fields."""

        model = Profile
        fields = ["title", "image", "bio", "education", "skills"]

    def get_image(self, obj):
        """Return absolute URL for the profile image when available.

        Uses the serializer context 'request' to build an absolute URI if present.
        """
        if obj.image:
            from django.conf import settings

            url = obj.image.url
            site_base = getattr(settings, "SITE_BASE_URL", None)
            if site_base:
                return site_base.rstrip("/") + url
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(url)
            return url
        return None

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Request may be None; absolutize_media_urls will use SITE_BASE_URL
        request = self.context.get("request") if hasattr(self, "context") else None
        if rep.get("bio"):
            from api.utils.ckeditor_paths import absolutize_media_urls

            try:
                rep["bio"] = absolutize_media_urls(rep["bio"], request)
            except Exception:
                pass
        return rep


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for UPDATE operations - accepts skill names with auto-creation"""

    skills = serializers.ListField(
        child=serializers.CharField(max_length=50), write_only=True, required=False, allow_empty=True
    )

    class Meta:
        """Configuration for ProfileUpdateSerializer fields."""

        model = Profile
        fields = ["title", "image", "bio", "education", "skills"]
        extra_kwargs = {
            "image": {"required": False, "allow_null": True},
            "title": {"required": False, "allow_blank": True},
        }

    def update(self, instance, validated_data):
        """Update the Profile instance and attach Skill objects by IDs."""
        skill_ids = validated_data.pop("skills", None)
        instance = super().update(instance, validated_data)

        if skill_ids is not None:
            # Remove duplicates while preserving order
            unique_skill_ids = list(dict.fromkeys(skill_ids))

            # Validate that all skill IDs exist
            skill_objects = Skill.objects.filter(id__in=unique_skill_ids, is_active=True)

            # Check if all provided IDs were found
            if len(skill_objects) != len(unique_skill_ids):
                found_ids = set(skill_objects.values_list("id", flat=True))
                missing_ids = set(unique_skill_ids) - found_ids
                raise serializers.ValidationError(
                    {"skills": f"Skills with IDs {sorted(missing_ids)} do not exist or are inactive."}
                )

            instance.skills.set(skill_objects)

        return instance

    def to_representation(self, instance):
        """Convert back to read format with nested skills"""
        representation = super().to_representation(instance)
        representation["skills"] = SkillSerializer(instance.skills.all(), many=True).data
        return representation


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile with full name and role display."""

    profile = ProfileSerializer(read_only=True)
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    role = serializers.SerializerMethodField(read_only=True)

    class Meta:
        """Configuration for UserProfileSerializer fields."""

        model = CustomUser
        # Expose `phone` as read-only because all phone changes are performed
        # via a dedicated, email-confirmed flow to protect account security.
        fields = [
            "id",
            "email",
            "phone",
            "first_name",
            "last_name",
            "full_name",
            "is_enabled",
            "student_id",
            "role",
            "profile",
            "date_joined",
        ]
        # Prevent direct editing of sensitive identity fields through the
        # generic user profile serializer. Email and student_id changes must
        # go through their dedicated flows. Also make admin-controlled flags
        # read-only here so the frontend and future code cannot accidentally
        # write them via the generic profile endpoint.
        read_only_fields = ["phone", "student_id", "email", "is_active"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_role(self, obj):
        """Return display value for user role."""
        return obj.get_role_display()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.role == "teacher":
            data.pop("student_id", None)
        return data


class StudentProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating student profile with simple skill names"""

    profile = ProfileUpdateSerializer(required=False)

    class Meta:
        """Configuration for StudentProfileUpdateSerializer fields.

        Note: `phone` is intentionally excluded from writable fields. Phone
        changes must go through the email-confirmed change flow implemented
        via `RequestPhoneChangeSerializer` and `ConfirmPhoneChangeSerializer`.
        """

        model = CustomUser
        fields = ["first_name", "last_name", "is_enabled", "profile"]

    def update(self, instance, validated_data):
        """Update the CustomUser instance and optionally its nested profile."""
        # Defensive: ensure protected fields cannot be updated through this
        # serializer even if a client includes them in the payload.
        for protected in ("phone", "is_active"):
            if protected in validated_data:
                validated_data.pop(protected)

        profile_data = validated_data.pop("profile", None)

        # Update user fields
        instance.first_name = validated_data.get("first_name", instance.first_name)
        instance.last_name = validated_data.get("last_name", instance.last_name)
        instance.is_enabled = validated_data.get("is_enabled", instance.is_enabled)
        # Phone updates are disabled here. Use the email-confirmed phone
        # change flow (request -> confirm) to safely update this field.
        instance.save()

        # Update profile if provided
        if profile_data:
            profile, created = Profile.objects.get_or_create(user=instance)
            profile_serializer = ProfileUpdateSerializer(
                instance=profile, data=profile_data, partial=True, context=self.context
            )
            profile_serializer.is_valid(raise_exception=True)
            profile_serializer.save()

        return instance


class TeacherProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating teacher profile (with nested profile)."""

    profile = ProfileUpdateSerializer(required=False)

    class Meta:
        """Meta options for TeacherProfileUpdateSerializer."""

        model = CustomUser
        fields = ["first_name", "last_name", "is_enabled", "profile"]

    def update(self, instance, validated_data):
        """Update user and nested profile fields."""
        # Defensive: ensure protected fields cannot be updated through this
        # serializer even if a client includes them in the payload.
        for protected in ("phone", "is_active"):
            if protected in validated_data:
                validated_data.pop(protected)

        # Update user fields
        instance.first_name = validated_data.get("first_name", instance.first_name)
        instance.last_name = validated_data.get("last_name", instance.last_name)
        instance.is_enabled = validated_data.get("is_enabled", instance.is_enabled)
        instance.save()

        # Update profile
        profile_data = validated_data.get("profile")
        if profile_data:
            profile, _ = Profile.objects.get_or_create(user=instance)
            for attr, value in profile_data.items():
                if attr == "skills":
                    profile.skills.set(value)
                else:
                    setattr(profile, attr, value)
            profile.save()

        return instance


class ResendVerificationEmailSerializer(serializers.Serializer):
    """Serializer for resending verification email to inactive students."""

    email = serializers.EmailField()

    def validate_email(self, value):
        """Ensure the email belongs to an inactive student account."""
        """
        Ensure the email belongs to an inactive student account.
        """

        user = CustomUser.objects.filter(email=value, role=CustomUser.Role.STUDENT).first()

        if not user:
            raise serializers.ValidationError("Student with this email not found.")
        if user.is_active:
            raise serializers.ValidationError("Account already active.")

        # Do not allow resending verification for explicitly disabled accounts
        if not getattr(user, "is_enabled", True):
            raise serializers.ValidationError("Account is disabled. Please contact the admin to enable your account.")

        self.context["user"] = user
        return value


class PasswordResetSerializer(serializers.Serializer):
    """Serializer for initiating password reset by email."""

    email = serializers.EmailField()

    def validate_email(self, value):
        """Ensure the email belongs to an active user account.
        Ensure the email belongs to an active user account.
        """
        user = CustomUser.objects.filter(email=value).first()
        if not user:
            raise serializers.ValidationError("User with this email not found.")
        # Block password reset for inactive (unverified) or admin-disabled accounts
        if not user.is_active or not getattr(user, "is_enabled", True):
            raise serializers.ValidationError("User account is disabled.")

        self.context["user"] = user
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for confirming password reset with token."""

    new_password = serializers.CharField(write_only=True)
    new_password2 = serializers.CharField(write_only=True)

    def validate(self, attrs):
        """Check that new passwords match."""
        if attrs["new_password"] != attrs["new_password2"]:
            raise serializers.ValidationError({"new_password2": "Password confirmation does not match."})
        return attrs

    def validate_new_password(self, value):
        # If serializer context included a user (e.g., during reset-confirm or change-password),
        # pass it to Django's validators so similarity checks can run.
        user = self.context.get("user") if hasattr(self, "context") else None
        # Also support passing request in context
        if not user and hasattr(self, "context"):
            req = self.context.get("request")
            if req:
                user = getattr(req, "user", None)
        return validate_password_strength(value, user=user)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)
    new_password2 = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        """Validate old and new passwords for change operation."""
        old_password = attrs.get("old_password")
        new_password = attrs.get("new_password")
        new_password2 = attrs.get("new_password2")

        # Check if new passwords match
        if new_password != new_password2:
            raise serializers.ValidationError({"new_password2": "New passwords do not match."})

        # Check if new password is same as old password
        if old_password == new_password:
            raise serializers.ValidationError({"new_password": "New password cannot be the same as old password."})

        return attrs

    def validate_new_password(self, value):
        """Validate password strength using centralized helper."""
        user = self.context.get("user") if hasattr(self, "context") else None
        if not user and hasattr(self, "context"):
            req = self.context.get("request")
            if req:
                user = getattr(req, "user", None)
        return validate_password_strength(value, user=user)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom Token serializer referenced by SIMPLE_JWT setting.

    Adds a `role` claim to the token payload. Kept minimal so drf-simplejwt
    can import it for the token view.
    """

    @classmethod
    def get_token(cls, user):
        """Return a token with an added 'role' claim for the given user."""
        token = super().get_token(user)
        try:
            token["role"] = getattr(user, "role", None)
        except Exception:
            pass
        return token


class VerifyEmailSerializer(serializers.Serializer):
    """Serializer used to document the verify-email query parameter."""

    token = serializers.CharField(required=True, help_text="Signed verification token")


class RequestPhoneChangeSerializer(serializers.Serializer):
    """Allow an authenticated student to change their phone number directly."""

    new_phone = serializers.CharField()

    def validate_new_phone(self, value):
        clean_phone = "".join(filter(str.isdigit, value))
        if len(clean_phone) <= 10:
            raise serializers.ValidationError("Phone number must be more than 10 digits.")
        if CustomUser.objects.filter(phone=clean_phone).exists():
            raise serializers.ValidationError("This phone number is already in use.")
        return clean_phone

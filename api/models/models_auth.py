"""Authentication-related models: CustomUser, Profile and Skill.

This module defines the project's user model, profile, and related utilities
such as image handling and a custom user manager.
"""

import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _

from django_ckeditor_5.fields import CKEditor5Field

from api.models.images_base_class import OptimizedImageModel
from api.utils.helper_models import TimeStampedModel

# -----------------------------------------------------------
# Custom Manager
# -----------------------------------------------------------


class CustomUserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifier.
    """

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_("The Email field must be set"))

        email = self.normalize_email(email)
        role = extra_fields.get("role", None)

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)  # Save FIRST to get date_joined and pk

        # Auto-generate student_id only for students AFTER saving
        if role == CustomUser.Role.STUDENT and not user.student_id:
            user.student_id = self._generate_unique_student_id(user)
            user.save(update_fields=["student_id"])

        return user

    def _generate_unique_student_id(self, user):
        """Generate a unique student ID in format PA-YYYY-XXX using user's registration year"""
        if not user.date_joined:
            # Fallback to current year if date_joined is somehow not set
            from django.utils import timezone

            year = timezone.now().year
        else:
            year = user.date_joined.year

        prefix = f"PA-{year}-"

        # Count existing students from the same year (exclude current user)
        existing_count = (
            CustomUser.objects.filter(role=CustomUser.Role.STUDENT, date_joined__year=year, student_id__isnull=False)
            .exclude(pk=user.pk)
            .count()
        )

        counter = existing_count + 1

        # Ensure uniqueness
        max_attempts = 1000  # Prevent infinite loop
        attempts = 0
        while attempts < max_attempts:
            student_id = f"{prefix}{counter:03d}"
            if not CustomUser.objects.filter(student_id=student_id).exists():
                return student_id
            counter += 1
            attempts += 1

        return f"{prefix}{str(uuid.uuid4())[:8].upper()}"

    def create_superuser(self, email, password, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        Ensures the superuser has the correct flags and the SUPERADMIN role.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", CustomUser.Role.SUPERADMIN)

        if extra_fields.get("role") != CustomUser.Role.SUPERADMIN:
            raise ValueError("Superuser must have role of Super Admin.")
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


# -----------------------------------------------------------
# CustomUser Model
# -----------------------------------------------------------


class CustomUser(AbstractBaseUser, PermissionsMixin):
    """Custom user model with email authentication and role-based access."""

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, help_text="Unique UUID identifier for this user."
    )

    student_id = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Custom student ID in format PA-YEAR-01. Only for students.",
    )

    class Role(models.TextChoices):
        SUPERADMIN = "superadmin", _("Super Admin")
        ADMIN = "admin", _("Admin")
        STAFF = "staf", _("Staff")
        ACCOUNTANT = "accountant", _("Accountant")
        TEACHER = "teacher", _("Teacher")
        STUDENT = "student", _("Student")

    first_name = models.CharField(_("first name"), max_length=150, help_text="User's first name (max 150 chars).")
    last_name = models.CharField(_("last name"), max_length=150, help_text="User's last name (max 150 chars).")
    email = models.EmailField(
        _("email address"),
        unique=True,
        db_index=True,
        help_text="Unique email address used for login. Must be valid email format.",
    )
    phone = models.CharField(
        _("phone number"), max_length=15, unique=True, help_text="Unique phone number (max 15 chars). Include country code."
    )
    last_password_reset = models.DateTimeField(
        null=True, blank=True, help_text="Timestamp of the last password reset. Auto-managed by system."
    )

    role = models.CharField(
        max_length=15,
        choices=Role.choices,
        default=Role.STUDENT,
        help_text="User's role in the system (max 15 chars). Determines access permissions.",
    )

    is_staff = models.BooleanField(
        default=False, help_text=_("Check to allow admin site access. Staff can log into admin panel.")
    )
    is_active = models.BooleanField(default=True, help_text=_("Uncheck to disable account. Inactive users cannot log in."))

    is_enabled = models.BooleanField(
        default=True, help_text="Uncheck to disable this profile. Disabled profiles cannot be accessed."
    )

    date_joined = models.DateTimeField(auto_now_add=True, help_text="Date and time when the user account was created.")

    USERNAME_FIELD = "email"

    # Required fields
    REQUIRED_FIELDS = ["first_name", "last_name", "phone"]

    objects = CustomUserManager()

    class Meta:
        verbose_name = "Prime Academy User"
        verbose_name_plural = "All Users"

    def __str__(self):
        return self.first_name + " " + self.last_name

    def regenerate_student_id(self):
        """
        Utility method to regenerate student ID if needed.
        Use with caution - only call this if student_id needs to be changed.
        """
        if self.role != self.Role.STUDENT:
            return None

        self.student_id = CustomUser.objects._generate_unique_student_id(self)
        self.save(update_fields=["student_id"])
        return self.student_id

    @property
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"


# -----------------------------------------------------------
# Profile & Skill Models
# -----------------------------------------------------------


class Skill(models.Model):
    """Skills that can be associated with user profiles."""

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, help_text="Unique UUID identifier for this skill."
    )
    name = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Skill name (max 50 chars). Must be unique. Example: 'Python', 'Web Design'.",
    )
    is_active = models.BooleanField(default=True, help_text="Uncheck to hide this skill from selection options.")

    class Meta:
        verbose_name = "Skill"
        verbose_name_plural = "Skills"

    def __str__(self):
        return self.name


class Profile(TimeStampedModel, OptimizedImageModel):
    """Extended user profile information with image optimization."""

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, help_text="Unique UUID identifier for this profile."
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        help_text="Select the user this profile belongs to. Each user can have only one profile.",
    )
    title = models.CharField(
        _("Title"),
        max_length=100,
        null=True,
        blank=True,
        help_text="Professional title or position (max 100 chars). Example: 'Senior Developer'.",
    )
    image = models.ImageField(
        upload_to="profile_pics/",
        null=True,
        blank=True,
        help_text="Profile picture. Recommended size: 300x300px. Will be automatically optimized.",
    )

    bio = CKEditor5Field(
        _("Biography"),
        blank=True,
        null=True,
        help_text="Write your Biography here.",
    )

    education = models.CharField(
        _("Education"),
        max_length=255,
        blank=True,
        help_text="Educational background (max 255 chars). Example: 'BSc Computer Science'.",
    )
    skills = models.ManyToManyField(
        Skill, blank=True, help_text="Select skills associated with this user. Hold Ctrl/Cmd to select multiple."
    )

    IMAGE_FIELDS_OPTIMIZATION = {
        "image": {
            "max_size": (300, 300),  # Maximum dimensions
            "min_size": (100, 100),  # Minimum dimensions (optional)
            "max_bytes": 300 * 1024,  # Maximum: 300KB
            "min_bytes": 50 * 1024,  # NEW: Minimum: 50KB - skip if already smaller
            "max_upload_mb": 1,  # Maximum upload before processing
        }
    }

    class Meta:
        verbose_name = "Prime Academy User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} Profile"

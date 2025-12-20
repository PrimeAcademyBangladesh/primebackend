"""
Employee management models: Department and Employee.

Includes full employee demographic, employment, payroll, and emergency info
with UUID primary keys and image optimization.
"""

import uuid

from django.db import models

from api.models.images_base_class import OptimizedImageModel
from api.utils.helper_models import TimeStampedModel


class Department(models.Model):
    """Company departments for organizing employees."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier for this department.",
    )
    name = models.CharField(
        max_length=150,
        unique=True,
        help_text="Department name (max 150 chars). Must be unique.",
    )
    is_active = models.BooleanField(default=True, help_text="Uncheck to hide this department from the system.")

    class Meta:
        verbose_name = "Department"
        verbose_name_plural = "Departments"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Employee(TimeStampedModel, OptimizedImageModel):
    """Employee records with full HR data and UUID primary keys."""

    CHOOSE_GENDER = (
        ("male", "Male"),
        ("female", "Female"),
    )

    EMPLOYEE_TYPE = (
        ("full-time", "Full Time"),
        ("part-time", "Part Time"),
        ("contractual", "Contract"),
        ("internship", "Internship"),
        ("temporary", "Temporary"),
        ("seasonal", "Seasonal"),
        ("casual", "Casual / On-Call"),
        ("hourly", "Hourly"),
        ("freelance", "Freelance"),
        ("consultant", "Consultant"),
        ("apprentice", "Apprenticeship"),
        ("trainee", "Trainee"),
    )

    MARITAL_STATUS = (
        ("single", "Single"),
        ("married", "Married"),
        ("divorced", "Divorced"),
        ("widowed", "Widowed"),
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier for this employee.",
    )

    # -----------------------------
    # Basic Identity
    # -----------------------------
    employee_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique Employee ID. Example: EMP001, DEV-2024-001",
    )

    first_name = models.CharField(max_length=50, help_text="Employee first name.")
    middle_name = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Employee middle name (optional).",
    )
    last_name = models.CharField(max_length=50, help_text="Employee last name.")

    date_of_birth = models.DateField(blank=True, null=True, help_text="Employee’s date of birth.")
    gender = models.CharField(
        choices=CHOOSE_GENDER,
        max_length=20,
        default="male",
        help_text="Gender of the employee (Male, Female, Other).",
    )
    nationality = models.CharField(max_length=50, blank=True, null=True, help_text="Nationality of the employee.")
    qualification = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text="Highest qualification of the employee.",
    )
    experience_years = models.PositiveIntegerField(blank=True, null=True, help_text="Years of previous work experience.")
    # -----------------------------
    # Contact Information
    # -----------------------------
    email = models.EmailField(
        max_length=254,
        blank=True,
        null=True,
        help_text="Employee's work email address.",
    )
    phone_number = models.CharField(max_length=20, blank=True, null=True, help_text="Primary contact phone number.")
    address = models.TextField(blank=True, null=True, help_text="Current residential address.")
    blood_group = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        help_text="Employee blood group (e.g., A+, O-).",
    )

    # -----------------------------
    # Employment Information
    # -----------------------------
    job_title = models.CharField(max_length=150, help_text="Job title or position of the employee.")
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="employees",
        help_text="Select the department this employee belongs to.",
    )
    employment_type = models.CharField(
        choices=EMPLOYEE_TYPE,
        max_length=50,
        default="full-time",
        help_text="Type of employment (e.g., Full-time, Part-time, Contract, Internship).",
    )
    joining_date = models.DateField(blank=True, null=True, help_text="Date when the employee joined the company.")
    salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Employee monthly or annual salary.",
    )

    # -----------------------------
    # Compliance & Documents
    # -----------------------------
    nid_no = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="National ID (NID) number of the employee.",
    )
    marital_status = models.CharField(
        max_length=20,
        choices=MARITAL_STATUS,
        blank=True,
        null=True,
        help_text="Marital status of the employee.",
    )
    # -----------------------------
    # Family & Emergency Contacts
    # -----------------------------
    spouse_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Name of employee’s spouse (optional).",
    )
    spouse_contact_phone = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Spouse Contact name.",
    )
    emergency_contact_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Emergency contact person’s name.",
    )
    alternative_contact_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Alternative emergency contact phone number.",
    )

    # -----------------------------
    # Images
    # -----------------------------
    resume = models.FileField(
        upload_to="resumes/",
        blank=True,
        null=True,
        help_text="Employee resume/CV file.",
    )
    employee_image = models.ImageField(
        upload_to="employee_images/",
        blank=True,
        null=True,
        help_text="Employee profile photo. Recommended size 400×400.",
    )

    IMAGE_FIELDS_OPTIMIZATION = {
        "employee_image": {
            "max_size": (400, 400),
            "min_size": (100, 100),
            "max_bytes": 100 * 1024,
            "min_bytes": 50 * 1024,
            "max_upload_mb": 1,
        }
    }

    # -----------------------------
    # System Fields
    # -----------------------------
    is_active = models.BooleanField(default=True, help_text="Uncheck to deactivate employee (resigned/terminated).")

    is_enabled = models.BooleanField(
        default=True,
        help_text="Uncheck to disable this profile. Disabled profiles cannot be accessed.",
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.job_title}"

    class Meta:
        verbose_name = "Employee"
        verbose_name_plural = "Employees"


# """Employee management models: Department and Employee.

# This module defines models for managing company employees and departments
# with UUID primary keys and image optimization for employee photos.
# """

# import uuid

# from django.db import models

# from api.models.images_base_class import OptimizedImageModel
# from api.utils.helper_models import TimeStampedModel


# class Department(models.Model):
#     """Company departments for organizing employees."""

#     id = models.UUIDField(
#         primary_key=True,
#         default=uuid.uuid4,
#         editable=False,
#         help_text="Unique UUID identifier for this department."
#     )
#     name = models.CharField(
#         max_length=150,
#         unique=True,
#         help_text="Department name (max 150 chars). Must be unique."
#     )
#     is_active = models.BooleanField(
#         default=True,
#         help_text="Uncheck to hide this department from the system."
#     )

#     class Meta:
#         verbose_name = "Department"
#         verbose_name_plural = "Departments"
#         ordering = ["name"]

#     def __str__(self):
#         return self.name


# class Employee(TimeStampedModel, OptimizedImageModel):
#     """Employee records with automatic image optimization and UUID primary keys."""

#     id = models.UUIDField(
#         primary_key=True,
#         default=uuid.uuid4,
#         editable=False,
#         help_text="Unique UUID identifier for this employee."
#     )
#     employee_id = models.CharField(
#         max_length=50,
#         unique=True,
#         db_index=True,
#         help_text="Unique Employee ID (max 50 chars). Example: EMP001, DEV-2024-001",
#     )
#     employee_name = models.CharField(
#         max_length=50,
#         help_text="Full name of the employee (max 50 chars)."
#     )
#     employee_image = models.ImageField(
#         upload_to="employee_images/",
#         blank=True,
#         null=True,
#         help_text="Employee profile photo. Recommended size: 400x400px."
#     )
#     job_title = models.CharField(
#         max_length=150,
#         help_text="Employee's job title or position (max 150 chars)."
#     )
#     department = models.ForeignKey(
#         Department,
#         on_delete=models.CASCADE,
#         related_name="employees",
#         help_text="Select the department this employee belongs to."
#     )
#     phone_number = models.CharField(
#         max_length=20,
#         help_text="Contact phone number (max 20 chars).",
#         blank=True,
#         null=True
#     )
#     email = models.EmailField(
#         max_length=254,
#         help_text="Employee's email address (max 254 chars).",
#         blank=True,
#         null=True
#     )
#     joining_date = models.DateField(
#         blank=True,
#         null=True,
#         help_text="Date when the employee joined the company."
#     )
#     is_active = models.BooleanField(
#         default=True,
#         help_text="Uncheck to mark employee as inactive (resigned/terminated)."
#     )

#     IMAGE_FIELDS_OPTIMIZATION = {
#         'employee_image': {
#             'max_size': (400, 400),
#             'min_size': (100, 100),
#             'max_bytes': 100*1024,
#             'min_bytes': 50*1024,
#             'max_upload_mb': 1
#         }
#     }

#     def __str__(self):
#         return f"{self.employee_name} - {self.job_title}"

#     class Meta:
#         verbose_name = "Employee"
#         verbose_name_plural = "Employees"

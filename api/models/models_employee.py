"""Employee management models: Department and Employee.

This module defines models for managing company employees and departments
with UUID primary keys and image optimization for employee photos.
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
        help_text="Unique UUID identifier for this department."
    )
    name = models.CharField(
        max_length=150, 
        unique=True, 
        help_text="Department name (max 150 chars). Must be unique."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck to hide this department from the system."
    )

    class Meta:
        verbose_name = "Department"
        verbose_name_plural = "Departments"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Employee(TimeStampedModel, OptimizedImageModel):
    """Employee records with automatic image optimization and UUID primary keys."""
    
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        help_text="Unique UUID identifier for this employee."
    )
    employee_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique Employee ID (max 50 chars). Example: EMP001, DEV-2024-001",
    )
    employee_name = models.CharField(
        max_length=50, 
        help_text="Full name of the employee (max 50 chars)."
    )
    employee_image = models.ImageField(
        upload_to="employee_images/", 
        blank=True, 
        null=True,
        help_text="Employee profile photo. Recommended size: 400x400px."
    )
    job_title = models.CharField(
        max_length=150, 
        help_text="Employee's job title or position (max 150 chars)."
    )
    department = models.ForeignKey(
        Department, 
        on_delete=models.CASCADE, 
        related_name="employees",
        help_text="Select the department this employee belongs to."
    )
    phone_number = models.CharField(
        max_length=20, 
        help_text="Contact phone number (max 20 chars).", 
        blank=True, 
        null=True
    )
    email = models.EmailField(
        max_length=254, 
        help_text="Employee's email address (max 254 chars).", 
        blank=True, 
        null=True
    )
    joining_date = models.DateField(
        blank=True, 
        null=True,
        help_text="Date when the employee joined the company."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck to mark employee as inactive (resigned/terminated)."
    )
    
    IMAGE_FIELDS_OPTIMIZATION = {
        'employee_image': {
            'max_size': (400, 400),
            'min_size': (100, 100),
            'max_bytes': 100*1024,
            'min_bytes': 50*1024,
            'max_upload_mb': 1
        }
    }

    def __str__(self):
        return f"{self.employee_name} - {self.job_title}"

    class Meta:
        verbose_name = "Employee"
        verbose_name_plural = "Employees"
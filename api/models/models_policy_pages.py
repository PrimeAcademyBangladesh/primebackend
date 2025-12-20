import uuid

from django.db import models
from django.utils.text import slugify

from django_ckeditor_5.fields import CKEditor5Field

from api.utils.helper_models import TimeStampedModel


class PolicyPage(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_index=True)
    PAGE_CHOICES = [
        ("privacy", "Privacy Policy"),
        ("terms", "Terms and Conditions"),
        ("refund", "Refund Policy"),
        ("cookie", "Cookie Policy"),
        ("data", "Data Protection Policy"),
        ("disclaimer", "Disclaimer"),
        ("instructor", "Instructor Agreement"),
        ("student", "Student Code of Conduct"),
        ("copyright", "Copyright Policy"),
        ("accessibility", "Accessibility Policy"),
        ("payment", "Payment & Subscription Policy"),
    ]
    page_name = models.SlugField(unique=True, choices=PAGE_CHOICES)
    title = models.CharField(max_length=150)
    content = CKEditor5Field(
        blank=True,
        null=True,
        help_text="Privacy Policy Content",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Policy Related Page"
        verbose_name_plural = "Policy Related Pages"

    def save(self, *args, **kwargs):
        if not self.page_name:
            self.page_name = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

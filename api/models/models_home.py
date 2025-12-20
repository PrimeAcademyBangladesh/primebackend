"""Home page models: HeroSection, HeroSlideText, and Brand.

This module defines models for managing home page content including
hero sections, sliding text animations, and brand/partner logos.
"""

import uuid

from django.db import models
from django.utils.text import slugify

from api.models.images_base_class import OptimizedImageModel
from api.utils.helper_models import TimeStampedModel


class HeroSection(TimeStampedModel, OptimizedImageModel):
    """Hero section content for home page with banner image and call-to-action buttons."""

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, help_text="Unique UUID identifier for this hero section."
    )
    page_name = models.CharField(
        max_length=100,
        unique=True,
        help_text="✅ Unique page identifier (max 100 chars). Use lowercase like 'home', 'about-us', 'contact'.",
    )
    title = models.CharField(
        max_length=255, blank=True, null=True, help_text="Main headline text (max 255 chars) displayed in the hero section."
    )

    description = models.TextField(blank=True, null=True, help_text="Subtitle or description text below the main title.")

    button1_text = models.CharField(
        max_length=100, blank=True, null=True, help_text="Text for the primary call-to-action button (max 100 chars)."
    )
    button1_url = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="URL/link for the primary button (max 255 chars). Can be relative (/about) or absolute (https://...).",
    )

    button2_text = models.CharField(
        max_length=100, blank=True, null=True, help_text="Text for the secondary call-to-action button (max 100 chars)."
    )
    button2_url = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="URL/link for the secondary button (max 255 chars). Can be relative (/contact) or absolute.",
    )

    banner_image = models.ImageField(
        upload_to="hero_banners/",
        blank=True,
        null=True,
        help_text="Hero background image. Recommended size: 1920x1080px for best quality.",
    )
    is_active = models.BooleanField(default=True, help_text="Uncheck to hide this hero section from the website.")

    IMAGE_FIELDS_OPTIMIZATION = {
        "banner_image": {
            "max_size": (1920, 1080),
            "min_size": (1280, 720),
            "max_bytes": 500 * 1024,
            "min_bytes": 300 * 1024,
            "max_upload_mb": 5,
        }
    }

    class Meta:
        verbose_name = "Hero Section"
        verbose_name_plural = "Hero Sections"
        ordering = ["page_name"]

    def __str__(self):
        return self.title or f"Hero Section: {self.page_name}"

    def clean(self):
        if self.page_name:
            self.page_name = slugify(self.page_name)
        super().clean()


class HeroSlideText(TimeStampedModel):
    """Animated text slides for hero sections."""

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, help_text="Unique UUID identifier for this slide text."
    )
    hero_section = models.ForeignKey(
        HeroSection,
        on_delete=models.CASCADE,
        related_name="slides",
        help_text="Select which hero section this text belongs to.",
    )
    text = models.CharField(max_length=255, help_text="Text to display in the animated slide (max 255 chars).")
    order = models.PositiveIntegerField(
        default=0, help_text="Display order (0=first, 1=second, etc.). Lower numbers show first."
    )

    class Meta:
        ordering = ["order"]
        verbose_name = "Hero Slide Text"
        verbose_name_plural = "Hero Slide Texts"

    def __str__(self):
        return self.text


# ===============================end hero section models===============================


# ===============================start brand section models===============================


class Brand(TimeStampedModel, OptimizedImageModel):
    """Partner brands and organizations we collaborate with."""

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, help_text="Unique UUID identifier for this brand."
    )
    logo = models.ImageField(
        upload_to="brands_logo/", help_text="Brand logo image. Recommended size: 400x400px with transparent background."
    )
    is_active = models.BooleanField(default=True, help_text="Uncheck to hide this brand from the website display.")

    IMAGE_FIELDS_OPTIMIZATION = {
        "logo": {
            "max_size": (400, 400),
            "min_size": (100, 100),
            "max_bytes": 150 * 1024,
            "min_bytes": 50 * 1024,
            "max_upload_mb": 1,
        }
    }

    class Meta:
        verbose_name = "Brand"
        verbose_name_plural = "Brands"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Brand Logo #{self.id}" if self.id else "New Brand Logo"

    def logo_url(self):
        """Return the absolute URL of the logo image."""
        if self.logo and hasattr(self.logo, "url"):
            return self.logo.url
        return None


# ===============================end brand section models===============================

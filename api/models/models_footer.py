"""
Footer models

This module defines the small set of models used to render the site's
public footer. The project expects a single `Footer` instance (enforced
by a `singleton_guard` boolean) and related `LinkGroup`, `QuickLink`,
and `SocialLink` items for flexible link columns and social icons.

These models are intentionally simple and include helpful __str__
representations for admin readability.
"""

import uuid

from django.db import models

from api.models.images_base_class import OptimizedImageModel
from api.utils.helper_models import TimeStampedModel


class Footer(TimeStampedModel, OptimizedImageModel):
    """Website footer content including logo, contact info, and links."""
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier for this footer."
    )
    singleton_guard = models.BooleanField(
        default=True, 
        unique=True,
        help_text="System field - ensures only one footer exists. Do not modify."
    )
    logo = models.ImageField(
        upload_to="footer/", 
        blank=True, 
        null=True,
        help_text="Company logo for footer. Recommended size: 400x400px with transparent background."
    )
    description = models.CharField(
        max_length=280, 
        blank=True,
        help_text="Brief company description (max 280 chars) displayed in footer."
    )
    address = models.CharField(
        max_length=255, 
        blank=True,
        help_text="Company physical address (max 255 chars)."
    )
    email = models.EmailField(
        blank=True,
        help_text="Contact email address displayed in footer."
    )
    phone = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Contact phone number (max 50 chars). Include country code."
    )
    copyright_name = models.CharField(
        max_length=120,
        help_text="Company name for copyright notice (max 120 chars). Example: 'Prime Academy'."
    )
    
    IMAGE_FIELDS_OPTIMIZATION = {
        'logo': {
            'max_size': (400, 400),         # Maximum dimensions
            'min_size': (100, 100),         # Minimum dimensions (optional)
            'max_bytes': 250*1024,          # Maximum: 250KB
            'min_bytes': 90*1024,           # NEW: Minimum: 90KB - skip if already smaller
            'max_upload_mb': 1              # Maximum upload before processing
        }
    }

    class Meta:
        verbose_name = "Footer"
        verbose_name_plural = "Footers"

    def __str__(self):
        return "Footer"


class LinkGroup(models.Model):
    """Footer link column groups for organizing navigation links."""
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier for this link group."
    )
    footer = models.ForeignKey(
        Footer, 
        on_delete=models.CASCADE, 
        related_name="link_groups",
        help_text="Footer this link group belongs to."
    )
    title = models.CharField(
        max_length=100,
        help_text="Column header title (max 100 chars). Example: 'Quick Links', 'Services'."
    )
    order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Display order (0=first column, 1=second, etc.). Lower numbers appear first."
    )

    class Meta:
        ordering = ["order", "title"]
        verbose_name = "Footer Column Group"
        verbose_name_plural = "Footer Column Groups"
    
    def __str__(self):
        if self.title:
            return f"Footer Column Group: {self.title}"
        # fallback numbering when title is empty
        return f"Footer Column Group {self.pk or 'New'}"



class QuickLink(models.Model):
    """Individual navigation links within footer link groups."""
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier for this quick link."
    )
    group = models.ForeignKey(
        LinkGroup, 
        on_delete=models.CASCADE, 
        related_name="links",
        help_text="Link group this link belongs to."
    )
    label = models.CharField(
        max_length=80,
        help_text="Link text displayed to users (max 80 chars). Example: 'About Us', 'Contact'."
    )
    url = models.CharField(
        max_length=300,
        help_text="Link destination (max 300 chars). Use relative URLs (/about) or absolute (https://...)."
    )
    is_external = models.BooleanField(
        default=False,
        help_text="Check if link goes to external website (opens in new tab)."
    )
    order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Display order within the group (0=first, 1=second, etc.)."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck to hide this link from footer display."
    )

    class Meta:
        ordering = ["order", "label"]

    def __str__(self):
        return f"{self.label or 'Footer Link'}"


class SocialLink(models.Model):
    """Social media links for footer social icons."""
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier for this social link."
    )
    
    class Platform(models.TextChoices):
        X = "x", "X/Twitter"
        FACEBOOK = "facebook", "Facebook"
        LINKEDIN = "linkedin", "LinkedIn"
        INSTAGRAM = "instagram", "Instagram"
        YOUTUBE = "youtube", "YouTube"
        TIKTOK = "tiktok", "TikTok"
        SNAPCHAT = "snapchat", "Snapchat"
        SPOTIFY = "spotify", "Spotify"
        THREAD = "thread", "Thread"
        PINTEREST = "pinterest", "Pinterest"
        DISCORD = "discord", "Discord"
        TELEGRAM = "telegram", "Telegram"

    footer = models.ForeignKey(
        Footer, 
        on_delete=models.CASCADE, 
        related_name="social_links",
        help_text="Footer this social link belongs to."
    )
    platform = models.CharField(
        max_length=20, 
        choices=Platform.choices,
        help_text="Select the social media platform."
    )
    url = models.URLField(
        help_text="Full URL to your social media profile. Example: https://facebook.com/primeacademy"
    )
    order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Display order (0=first icon, 1=second, etc.). Lower numbers appear first."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck to hide this social link from footer display."
    )

    class Meta:
        ordering = ["order", "platform"]

    def __str__(self):
        return self.platform

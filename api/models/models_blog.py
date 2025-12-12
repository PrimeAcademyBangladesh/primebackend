"""Blog-related models: BlogCategory and Blog.

This module defines models for managing blog content including categories
and blog posts with automatic slug generation and image optimization.
"""

import uuid

from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django_ckeditor_5.fields import CKEditor5Field

from api.models.images_base_class import OptimizedImageModel
from api.utils.helper_models import TimeStampedModel


class BlogCategory(TimeStampedModel):
    """Categories for organizing blog posts."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier for this blog category.",
    )
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Category name (max 100 chars). Must be unique.",
    )
    slug = models.SlugField(
        max_length=120,
        unique=True,
        db_index=True,
        help_text="Auto-generated URL-friendly version of the name.",
    )
    is_active = models.BooleanField(
        default=True, help_text="Uncheck to hide this category from the website."
    )

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Blog(TimeStampedModel, OptimizedImageModel):
    """Blog post model with automatic slug generation and image optimization."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier for this blog post.",
    )

    slug_source_field = "title"

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("published", "Published"),
    )

    category = models.ForeignKey(
        BlogCategory,
        on_delete=models.CASCADE,
        related_name="blogs",
        help_text="Select the category for this blog post.",
    )
    
    title = models.CharField(
        max_length=255,
        unique=True,
        help_text="Blog post title (max 255 chars). Must be unique.",
    )
    slug = models.SlugField(
        max_length=300,
        unique=True,
        db_index=True,
        help_text="Auto-generated URL-friendly version of the title.",
    )

    excerpt = models.TextField(
        blank=True,
        null=True,
        help_text="Short description/summary (max 500 chars). Used in previews.",
    )

    content = CKEditor5Field (
        blank=True,
        null=True,
        help_text="Full blog post content. Supports HTML and markdown.",
    )

    featured_image = models.ImageField(
        upload_to="blog_images/",
        blank=True,
        null=True,
        help_text="Main image for the blog post. Recommended size: 1920x1080px.",
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="draft",
        help_text="Publication status (max 10 chars). Draft: Not visible to public. Published: Live on website.",
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Auto-set when status changes to published. Leave empty for drafts.",
    )
    show_in_home_latest = models.BooleanField(
        default=True,
        help_text="Show this blog in the 'Latest Blogs' section on the home page. Only applies to published blogs.",
    )

    IMAGE_FIELDS_OPTIMIZATION = {
        "featured_image": {
            "max_size": (1920, 1080),
            "min_size": (1280, 720),
            "max_bytes": 500 * 1024,
            "min_bytes": 250 * 1024,
            "max_upload_mb": 5,
        }
    }

    # Allow editors to override or store generated JSON-LD for this post
    structured_data = models.JSONField(
        blank=True,
        null=True,
        help_text="Optional JSON-LD for this blog post. Leave empty to auto-generate.",
    )

    class Meta:
        verbose_name = "Blog"
        verbose_name_plural = "Blogs"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.slug = slugify(self.title)

        # Auto-generate structured_data when not provided so editors can override
        if not self.structured_data:
            try:
                # generate using request=None (FRONTEND_URL fallback)
                self.structured_data = self.get_structured_data(request=None)
            except Exception:
                # Be defensive: don't block save on structured data generation errors
                self.structured_data = None

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        """Return relative absolute path for this blog post.

        Frontend can combine this with FRONTEND_URL to build full URL.
        """
        return f"/blog/{self.slug}/"

    def get_structured_data(self, request=None):
        """Generate JSON-LD (BlogPosting) for this blog post.

        Uses request to build absolute image and page URLs when available,
        otherwise falls back to settings.FRONTEND_URL.
        """
        from django.conf import settings

        def build_absolute(url_path):
            if not url_path:
                return None
            if request:
                try:
                    return request.build_absolute_uri(url_path)
                except Exception:
                    pass
            return f"{settings.FRONTEND_URL.rstrip('/')}" + (url_path if url_path.startswith('/') else '/' + url_path)

        image_url = build_absolute(self.featured_image.url) if self.featured_image else None
        page_url = build_absolute(self.get_absolute_url())

        data = {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": self.title,
            "description": self.excerpt or "",
            "url": page_url,
            "datePublished": self.published_at.isoformat() if self.published_at else None,
            "image": image_url,
            "publisher": {
                "@type": "Organization",
                "name": settings.SEO_CONFIG.get("SITE_NAME"),
                "logo": {
                    "@type": "ImageObject",
                    "url": settings.SEO_CONFIG.get("ORGANIZATION_LOGO_URL"),
                },
            },
        }

        return data

import re
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from django_ckeditor_5.fields import CKEditor5Field

from api.models.images_base_class import OptimizedImageModel
from api.models.models_service import PageService  # Add this import
from api.utils.helper_models import TimeStampedModel
from api.utils.video_utils import extract_video_id as utils_extract_video_id
from api.utils.video_utils import \
    validate_video_url as utils_validate_video_url


class ValueTabSection(TimeStampedModel):
    """Main section like 'OUR VALUES' that contains multiple value tabs"""

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, unique=True, db_index=True
    )
    title = models.CharField(
        max_length=100, help_text="Section title (e.g., 'OUR VALUES')"
    )
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    subtitle = models.CharField(
        max_length=255, blank=True, help_text="Optional subtitle"
    )
    page = models.ForeignKey(
        PageService,  # Direct reference instead of string
        on_delete=models.CASCADE,
        related_name="value_tab_sections",
        help_text="Page this section belongs to",
    )
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["page", "order"]
        verbose_name = "Value Tab Section"
        verbose_name_plural = "Value Tab Sections"

    def __str__(self):
        return f"{self.page.name} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class ValueTab(TimeStampedModel):
    """Individual value tabs like 'Be The Expert', 'Be The Customer', 'Be The Future'"""

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, unique=True, db_index=True
    )
    value_section = models.ForeignKey(
        ValueTabSection, on_delete=models.CASCADE, related_name="value_tabs"
    )
    title = models.CharField(
        max_length=100, help_text="Tab name (e.g., 'Be The Expert')"
    )
    slug = models.SlugField(max_length=100, db_index=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["value_section", "order"]
        verbose_name = "Value Tab"
        verbose_name_plural = "Value Tabs"
        unique_together = ["value_section", "slug"]

    def __str__(self):
        return f"{self.value_section.title} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class ValueTabContent(TimeStampedModel, OptimizedImageModel):
    """Content for each value tab - left side media, right side text"""

    MEDIA_TYPES = (
        ("image", "Image"),
        ("video", "Video"),
    )

    VIDEO_PROVIDERS = (
        ("youtube", "YouTube"),
        ("vimeo", "Vimeo"),
    )

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, unique=True, db_index=True
    )
    value_tab = models.OneToOneField(
        ValueTab,
        on_delete=models.CASCADE,
        related_name="content",
        help_text="Each value tab has one content section",
    )

    # Media fields (left side)
    media_type = models.CharField(
        max_length=10,
        choices=MEDIA_TYPES,
        default="image",
        help_text="Choose between image or video",
    )

    # Image option
    image = models.ImageField(
        upload_to="value_tabs/images/",
        blank=True,
        null=True,
        help_text="Image for left side",
    )

    # Video option
    video_provider = models.CharField(
        max_length=10,
        choices=VIDEO_PROVIDERS,
        blank=True,
        null=True,
        help_text="Video provider (YouTube or Vimeo)",
    )
    video_url = models.URLField(
        max_length=500, blank=True, null=True, help_text="Full video URL"
    )
    video_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        editable=False,
        help_text="Automatically extracted video ID",
    )
    video_thumbnail = models.ImageField(
        upload_to="value_tabs/video_thumbnails/",
        blank=True,
        null=True,
        help_text="Video thumbnail",
    )

    # Content fields (right side)
    title = models.CharField(
        max_length=255, help_text="Content title (e.g., 'BE THE EXPERT')"
    )
    description = CKEditor5Field(help_text="Main content text")

    # Optional button
    button_text = models.CharField(
        max_length=100, blank=True, help_text="Optional button text"
    )
    button_url = models.CharField(
        max_length=255, blank=True, null=True, help_text="Optional button URL"
    )

    is_active = models.BooleanField(default=True)

    # Image optimization settings
    IMAGE_FIELDS_OPTIMIZATION = {
        "image": {
            "default": {
                "max_size": (800, 800),
                "min_size": (400, 400),
                "max_bytes": 400 * 1024,
                "min_bytes": 150 * 1024,
                "max_upload_mb": 2,
            }
        },
        "video_thumbnail": {
            "default": {
                "max_size": (1280, 720),
                "min_size": (640, 360),
                "max_bytes": 400 * 1024,
                "min_bytes": 100 * 1024,
                "max_upload_mb": 2,
            }
        },
    }

    class Meta:
        verbose_name = "Value Tab Content"
        verbose_name_plural = "Value Tab Contents"

    def __str__(self):
        return f"{self.value_tab.title} - {self.title}"

    def clean(self):
        """Validate media fields based on media type"""
        super().clean()

        if self.media_type == "video":
            if not self.video_url:
                raise ValidationError(
                    {"video_url": "Video URL is required when media type is video."}
                )
            if not self.video_provider:
                raise ValidationError(
                    {
                        "video_provider": "Video provider is required when media type is video."
                    }
                )
            if not self.video_thumbnail:
                raise ValidationError(
                    {
                        "video_thumbnail": "Video thumbnail is required when media type is video."
                    }
                )
            if not self.validate_video_url():
                raise ValidationError(
                    {"video_url": f"Invalid {self.video_provider} URL format."}
                )

        if self.media_type == "image" and not self.image:
            raise ValidationError(
                {"image": "Image is required when media type is image."}
            )

        if self.button_text and not self.button_url:
            raise ValidationError(
                {"button_url": "Button URL is required when button text is provided."}
            )

    def validate_video_url(self):
        """Validate video URL based on provider"""
        return utils_validate_video_url(self.video_provider, self.video_url)

    def extract_video_id(self):
        """Extract video ID from URL based on provider"""
        return utils_extract_video_id(self.video_provider, self.video_url)

    def save(self, *args, **kwargs):
        # Extract video ID if video URL is provided
        if self.video_url and self.video_provider:
            self.video_id = self.extract_video_id()
        else:
            self.video_id = None

        # Clear video fields if media type is image
        if self.media_type == "image":
            self.video_url = None
            self.video_provider = None
            self.video_id = None
            self.video_thumbnail = None

        # Clear image if media type is video
        if self.media_type == "video":
            self.image = None

        super().save(*args, **kwargs)

    def get_image_optimization_config(self):
        """Get optimization settings"""
        return self.IMAGE_FIELDS_OPTIMIZATION.get("image", {}).get("default", {})

    @property
    def has_video(self):
        return self.media_type == "video" and self.video_id is not None

    @property
    def has_button(self):
        return bool(self.button_text and self.button_url)
import re
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from django_ckeditor_5.fields import CKEditor5Field

from api.models.images_base_class import OptimizedImageModel
from api.utils.helper_models import TimeStampedModel
from api.utils.video_utils import extract_video_id as utils_extract_video_id
from api.utils.video_utils import validate_video_url as utils_validate_video_url


class PageService(TimeStampedModel):
    """Defines logical site pages to group reusable sections."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True, db_index=True)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Page"
        verbose_name_plural = "Pages"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ContentSection(TimeStampedModel, OptimizedImageModel):
    """Unified content section that can be either Info Section or Icon Section."""

    SECTION_TYPES = (("info", "Info Section"), ("icon", "Icon Section"), ("cta", "Call To Action"))

    MEDIA_TYPES = (
        ("image", "Image"),
        ("video", "Video"),
    )

    VIDEO_PROVIDERS = (
        ("youtube", "YouTube"),
        ("vimeo", "Vimeo"),
    )

    Position_Choices = (
        ("top", "Top"),
        ("middle", "Middle"),
        ("bottom", "Bottom"),
        ("extra1", "Extra 1"),
        ("extra2", "Extra 2"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True, db_index=True)
    page = models.ForeignKey(PageService, on_delete=models.CASCADE, related_name="content_sections")

    section_type = models.CharField(
        max_length=10,
        choices=SECTION_TYPES,
        default="info",
        help_text="Info Section: Large image with text. Icon Section: Small icon with compact layout.",
    )

    position_choice = models.CharField(
        max_length=10, choices=Position_Choices, default="top", help_text="Position of the section on the page."
    )

    media_type = models.CharField(
        max_length=10, choices=MEDIA_TYPES, default="image", help_text="Choose between image or video for Info Sections"
    )

    title = models.CharField(max_length=255)
    content = CKEditor5Field(blank=True, help_text="Description/text content")
    button_text = models.CharField(max_length=100, blank=True)
    button_link = models.CharField(max_length=255, blank=True, null=True)

    image = models.ImageField(
        upload_to="content_sections/",
        blank=True,
        null=True,
        help_text="Large image for Info Sections, small icon for Icon Sections",
    )

    # Video fields (only for info sections with media_type='video')
    video_provider = models.CharField(
        max_length=10, choices=VIDEO_PROVIDERS, blank=True, null=True, help_text="Select video provider (YouTube or Vimeo)"
    )
    video_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Full video URL (e.g., https://www.youtube.com/watch?v=VIDEO_ID or https://vimeo.com/VIDEO_ID)",
    )
    video_id = models.CharField(
        max_length=100, blank=True, null=True, editable=False, help_text="Automatically extracted video ID"
    )

    # Video thumbnail
    video_thumbnail = models.ImageField(
        upload_to="content_sections/video_thumbnails/",
        blank=True,
        null=True,
        help_text="Thumbnail for video (required when media type is video)",
    )

    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    # Image optimization settings based on type
    IMAGE_FIELDS_OPTIMIZATION = {
        "image": {
            "info": {  # Settings for Info Sections
                "max_size": (1000, 1000),
                "min_size": (400, 400),
                "max_bytes": 450 * 1024,
                "min_bytes": 250 * 1024,
                "max_upload_mb": 3,
            },
            "icon": {  # Settings for Icon Sections
                "max_size": (200, 200),
                "min_size": (50, 50),
                "max_bytes": 100 * 1024,
                "min_bytes": 10 * 1024,
                "max_upload_mb": 2,
            },
        },
        "video_thumbnail": {
            "info": {
                "max_size": (1280, 720),
                "min_size": (640, 360),
                "max_bytes": 400 * 1024,
                "min_bytes": 100 * 1024,
                "max_upload_mb": 2,
            }
        },
    }

    class Meta:
        ordering = ["page", "order", "section_type"]
        verbose_name = "Content Section"
        verbose_name_plural = "Content Sections"

    def __str__(self):
        return f"{self.page.name} - {self.get_section_type_display()} - {self.title}"

    def clean(self):
        """Validate media fields based on section and media type"""
        super().clean()

        # Icon sections can only use images
        if self.section_type == "icon" and self.media_type == "video":
            raise ValidationError({"media_type": "Icon sections can only use images."})

        # If media type is video, validate video fields
        if self.media_type == "video" and self.section_type == "info":
            if not self.video_url:
                raise ValidationError({"video_url": "Video URL is required when media type is video."})
            if not self.video_provider:
                raise ValidationError({"video_provider": "Video provider is required when media type is video."})
            if not self.video_thumbnail:
                raise ValidationError({"video_thumbnail": "Video thumbnail is required when media type is video."})

            # Validate video URL format
            if not self.validate_video_url():
                raise ValidationError({"video_url": f"Invalid {self.video_provider} URL format."})

        # If media type is image, validate image field
        if self.media_type == "image" and not self.image:
            raise ValidationError({"image": "Image is required when media type is image."})

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

        # Clear image if media type is video and section is info
        if self.media_type == "video" and self.section_type == "info":
            self.image = None

        super().save(*args, **kwargs)

    def get_image_optimization_config(self):
        """Get optimization settings based on section type and field"""
        # For video thumbnails, return thumbnail config
        base_config = self.IMAGE_FIELDS_OPTIMIZATION.get("image", {})
        return base_config.get(self.section_type, base_config.get("info", {}))

    @property
    def is_info_section(self):
        return self.section_type == "info"

    @property
    def is_icon_section(self):
        return self.section_type == "icon"

    @property
    def has_video(self):
        return self.media_type == "video" and self.video_id is not None

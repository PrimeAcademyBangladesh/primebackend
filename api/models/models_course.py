import uuid

from django.db import models
from django.utils.text import slugify
from django_ckeditor_5.fields import CKEditor5Field

from api.models.images_base_class import OptimizedImageModel
from api.utils.helper_models import TimeStampedModel


class Category(TimeStampedModel):
    """Course categories for organizing courses by subject or type."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=100, unique=True, db_index=True, help_text="Unique category name"
    )
    slug = models.SlugField(
        unique=True, db_index=True, help_text="URL-friendly version of the name"
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this category is active"
    )
    show_in_megamenu = models.BooleanField(
        default=False,
        help_text="Whether this category should appear in the site megamenu",
    )

    class Meta(TimeStampedModel.Meta):
        verbose_name = "Course Category"
        verbose_name_plural = "Course Categories"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active"]),
        ]

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Course(TimeStampedModel, OptimizedImageModel):
    """Main course model containing basic course information."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("archived", "Archived"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    category = models.ForeignKey(
        Category, related_name="courses", on_delete=models.CASCADE
    )

    title = models.CharField(
        max_length=200, unique=True, db_index=True, help_text="Unique course title"
    )
    slug = models.SlugField(
        max_length=250,
        unique=True,
        db_index=True,
        help_text="Auto-generated URL-friendly version of the title",
    )
    short_description = models.TextField(help_text="Brief description of the course")
    full_description = CKEditor5Field(
        blank=True,
        null=True,
        help_text="Detailed course description with rich text formatting",
    )
    header_image = models.ImageField(
        upload_to="courses/headers/",
        null=True,
        blank=True,
        help_text="Course header image",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        help_text="Publication status of the course",
    )

    show_in_megamenu = models.BooleanField(
        default=False, help_text="Whether to display this course in the megamenu"
    )

    show_in_home_tab = models.BooleanField(
        default=False,
        help_text="Whether to display this course in the home tab (homepage category blocks)",
    )

    is_active = models.BooleanField(
        default=True, help_text="Whether this course is active and visible"
    )

    # Image optimization configuration
    IMAGE_FIELDS_OPTIMIZATION = {
        "header_image": {
            "max_size": (1920, 1080),
            "min_size": (800, 600),
            "max_bytes": 500 * 1024,
            "max_upload_mb": 5,
        }
    }

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    class Meta(TimeStampedModel.Meta, OptimizedImageModel.Meta):
        verbose_name = "Course"
        verbose_name_plural = "Courses"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["title"]),
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return self.title


class CourseDetail(TimeStampedModel):
    """Extended course details including hero section and additional content."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.OneToOneField(
        Course, related_name="detail", on_delete=models.CASCADE
    )
    hero_button = models.CharField(
        max_length=100, help_text="Text for the hero section button"
    )
    hero_text = models.TextField(help_text="Hero section text content")
    hero_description = models.TextField(
        blank=True,
        null=True,
        help_text="Rich text content for detailed hero description",
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this course detail is active"
    )

    class Meta(TimeStampedModel.Meta):
        verbose_name = "Course Detail"
        verbose_name_plural = "Course Details"

    def __str__(self):
        return f"Details for {self.course.title}"


# Section 2: Course Content Sections (Replaces CourseTab and CourseMediaTab)
class CourseContentSection(models.Model):
    """Main section container for course detail page. Each section can have up to 2 sub-tabs."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        CourseDetail, related_name="content_sections", on_delete=models.CASCADE
    )
    section_name = models.CharField(
        max_length=100,
        help_text="Name of this section (e.g., 'Overview', 'Curriculum', 'Features')",
    )
    order = models.PositiveIntegerField(
        default=0, help_text="Display order of sections"
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this section is active and visible"
    )

    class Meta:
        verbose_name = "Course Content Section"
        verbose_name_plural = "Course Content Sections"
        ordering = ["course", "order"]
        unique_together = ["course", "order"]

    def __str__(self):
        return f"{self.course.course.title} - {self.section_name}"


class CourseSectionTab(models.Model):
    """Sub-tabs within a course content section."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    section = models.ForeignKey(
        CourseContentSection, related_name="tabs", on_delete=models.CASCADE
    )
    tab_name = models.CharField(
        max_length=100, help_text="Name of this tab (shown as tab header)"
    )
    order = models.PositiveIntegerField(
        default=0, help_text="Tab order such as 1 , 2, 3 ..."
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this tab is active and visible"
    )

    class Meta:
        verbose_name = "Course Section Tab"
        verbose_name_plural = "Course Section Tabs"
        ordering = ["section", "order"]
        unique_together = ["section", "order"]

    def __str__(self):
        return f"{self.section.section_name} - {self.tab_name}"


class CourseTabbedContent(TimeStampedModel, OptimizedImageModel):
    """Content items within a section tab. Supports image/video media."""

    MEDIA_TYPES = (
        ("image", "Image"),
        ("video", "Video"),
    )

    VIDEO_PROVIDERS = (
        ("youtube", "YouTube"),
        ("vimeo", "Vimeo"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tab = models.ForeignKey(
        CourseSectionTab, related_name="contents", on_delete=models.CASCADE
    )

    media_type = models.CharField(
        max_length=10,
        choices=MEDIA_TYPES,
        default="image",
        help_text="Choose between image or video",
    )

    title = models.CharField(
        max_length=255, blank=True, help_text="Title of this content item"
    )
    description = CKEditor5Field(blank=True, help_text="Rich text description/content")
    button_text = models.CharField(
        max_length=100, blank=True, help_text="Optional button text"
    )
    button_link = models.CharField(
        max_length=255, blank=True, null=True, help_text="Optional button link"
    )

    # Image field
    image = models.ImageField(
        upload_to="courses/content/images/",
        blank=True,
        null=True,
        help_text="Image for this content item (required for image type, optional for video as poster)",
    )

    # Video fields (for media_type='video' OR as popup link when media_type='image')
    video_provider = models.CharField(
        max_length=10,
        choices=VIDEO_PROVIDERS,
        blank=True,
        null=True,
        help_text="Video provider: YouTube or Vimeo (for video type OR image with video popup)",
    )
    video_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Full video URL - auto-extracts ID (for video type OR image with video popup)",
    )
    video_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        editable=False,
        help_text="Automatically extracted video ID",
    )
    video_thumbnail = models.ImageField(
        upload_to="courses/content/video_thumbnails/",
        blank=True,
        null=True,
        help_text="Video thumbnail (required only when media_type is video)",
    )

    order = models.PositiveIntegerField(
        default=0, help_text="Display order within the tab"
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this content is active and visible"
    )

    # Image optimization settings
    IMAGE_FIELDS_OPTIMIZATION = {
        "image": {
            "max_size": (1000, 1000),
            "min_size": (400, 400),
            "max_bytes": 450 * 1024,
            "max_upload_mb": 3,
        },
        "video_thumbnail": {
            "max_size": (1280, 720),
            "min_size": (640, 360),
            "max_bytes": 400 * 1024,
            "max_upload_mb": 2,
        },
    }

    class Meta(TimeStampedModel.Meta, OptimizedImageModel.Meta):
        verbose_name = "Course Tabbed Content"
        verbose_name_plural = "Course Tabbed Contents"
        ordering = ["tab", "order"]
        unique_together = ["tab", "order"]

    def __str__(self):
        return f"{self.tab.tab_name} - {self.title}"

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError

        errors = {}

        if self.media_type == "video":
            if not self.video_url:
                errors["video_url"] = "Video URL is required"
            if not self.video_provider:
                errors["video_provider"] = "Video provider is required"
            if not self.video_thumbnail:
                errors["video_thumbnail"] = "Video thumbnail is required"

            if self.video_url and self.video_provider:
                if not self.validate_video_url():
                    errors["video_url"] = f"Invalid {self.video_provider} URL format."

        if self.media_type == "image":
            if not self.image:
                errors["image"] = "Image is required"

            if self.video_url and not self.video_provider:
                errors["video_provider"] = (
                    "Video provider is required when video URL is set"
                )

        if errors:
            raise ValidationError(errors)

    def validate_video_url(self):
        """Validate video URL based on provider"""
        from api.utils.video_utils import validate_video_url

        return validate_video_url(self.video_provider, self.video_url)

    def extract_video_id(self):
        """Extract video ID from URL based on provider"""
        from api.utils.video_utils import extract_video_id

        return extract_video_id(self.video_provider, self.video_url)

    def save(self, *args, **kwargs):
        self.full_clean()

        if self.video_url and self.video_provider:
            try:
                self.video_id = self.extract_video_id()
            except Exception:
                self.video_id = None
        else:
            self.video_id = None

        if self.media_type == "image":
            self.video_thumbnail = None

            if not self.video_url:
                self.video_provider = None
                self.video_id = None

        super().save(*args, **kwargs)

    @property
    def has_video(self):
        return self.media_type == "video" and self.video_id is not None


# Section 4: Why Enrol
class WhyEnrol(OptimizedImageModel):
    """Reasons why students should enroll in the course."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        CourseDetail, related_name="why_enrol", on_delete=models.CASCADE
    )
    icon = models.ImageField(upload_to="courses/icons/")
    title = models.CharField(max_length=100)
    text = CKEditor5Field(help_text="Rich text content explaining why to enroll")

    is_active = models.BooleanField(
        default=True, help_text="Whether this why enrol section is active and visible"
    )

    # Image optimization configuration
    IMAGE_FIELDS_OPTIMIZATION = {
        "icon": {
            "max_size": (200, 200),
            "min_size": (50, 50),
            "max_bytes": 100 * 1024,  # 100KB
            "max_upload_mb": 2,
        }
    }

    class Meta(OptimizedImageModel.Meta):
        verbose_name = "Course Why Enrol Section"
        verbose_name_plural = "Course Why Enrol Sections"

    def __str__(self):
        return self.title


class CourseModule(models.Model):
    """Individual modules/chapters within a course."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    course = models.ForeignKey(
        "CourseDetail",
        related_name="modules",
        on_delete=models.CASCADE,
    )

    title = models.CharField(max_length=100)

    slug = models.SlugField(
        max_length=120,
        help_text="URL-friendly module identifier",
    )

    short_description = CKEditor5Field(help_text="Rich text description of the module")

    order = models.PositiveIntegerField()

    is_active = models.BooleanField(
        default=True, help_text="Whether this module is active and visible"
    )

    class Meta:
        verbose_name = "Course Module/Chapter"
        verbose_name_plural = "Course Modules/Chapters"
        ordering = ["order"]

        # Slug must be unique within a course
        unique_together = [
            ("course", "order"),
            ("course", "slug"),
        ]

        indexes = [
            models.Index(fields=["course", "order"]),
            models.Index(fields=["course", "slug"]),
        ]

    def __str__(self):
        return f"{self.order}. {self.title}"

    def save(self, *args, **kwargs):
        """
        Auto-generate unique slug per course.
        """
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1

            while (
                CourseModule.objects.filter(
                    course=self.course,
                    slug=slug,
                )
                .exclude(pk=self.pk)
                .exists()
            ):
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)


class CourseInstructor(models.Model):
    """Assigns teachers to specific course modules as instructors."""

    INSTRUCTOR_TYPE_CHOICES = [
        ("lead", "Lead Instructor"),
        ("support", "Support Instructor"),
        ("assistant", "Assistant Instructor"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        Course,
        related_name="instructors",
        on_delete=models.CASCADE,
        help_text="The course this instructor teaches",
    )
    teacher = models.ForeignKey(
        "api.CustomUser",
        related_name="teaching_courses",
        on_delete=models.CASCADE,
        limit_choices_to={"role": "teacher"},
        help_text="Teacher assigned as instructor (must have teacher role)",
    )
    modules = models.ManyToManyField(
        CourseModule,
        related_name="assigned_instructors",
        blank=True,
        help_text="Specific modules this instructor teaches (leave empty if teaching entire course)",
    )
    instructor_type = models.CharField(
        max_length=20,
        choices=INSTRUCTOR_TYPE_CHOICES,
        default="lead",
        help_text="Type of instructor role (lead, support, or assistant)",
    )
    is_lead_instructor = models.BooleanField(
        default=False,
        help_text="Mark as lead/primary instructor for this course (deprecated: use instructor_type)",
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this instructor assignment is currently active"
    )
    assigned_date = models.DateTimeField(
        auto_now_add=True, help_text="Date when instructor was assigned to this course"
    )

    class Meta:
        verbose_name = "Course Instructor"
        verbose_name_plural = "Course Instructors"
        unique_together = ["course", "teacher"]  # Prevent duplicate assignments
        indexes = [
            models.Index(fields=["course", "is_active"]),
            models.Index(fields=["teacher", "is_active"]),
            models.Index(fields=["is_lead_instructor"]),
            models.Index(fields=["instructor_type"]),
        ]

    def clean(self):
        """Validate that assigned user is a teacher."""
        from django.core.exceptions import ValidationError

        if self.teacher_id and self.teacher.role != "teacher":
            raise ValidationError(
                {
                    "teacher": "Only users with teacher role can be assigned as instructors."
                }
            )

    def save(self, *args, **kwargs):
        """Auto-sync is_lead_instructor with instructor_type."""
        if self.instructor_type == "lead":
            self.is_lead_instructor = True
        else:
            self.is_lead_instructor = False
        super().save(*args, **kwargs)

    def get_assigned_modules(self):
        """Get modules this instructor teaches or all course modules if none specified."""
        if self.modules.exists():
            return self.modules.all()
        # Return all modules from the course's detail
        return self.course.detail.modules.all()

    def __str__(self):
        module_count = self.modules.count() if self.pk else 0
        type_display = f" ({self.get_instructor_type_display()})"
        if module_count > 0:
            return f"{self.teacher.get_full_name}{type_display} - {self.course.title} ({module_count} modules)"
        return f"{self.teacher.get_full_name}{type_display} - {self.course.title} (All modules)"


class CourseBatch(TimeStampedModel):
    """Time-bound instances of a course (e.g., Jan 2025 batch, April 2025 batch).

    This model represents scheduled offerings of a course with specific:
    - Start and end dates
    - Enrollment capacity
    - Batch-specific pricing (if needed)
    - Enrollment tracking

    Students enroll in batches, not directly in courses.
    """

    BATCH_STATUS_CHOICES = [
        ("upcoming", "Upcoming"),
        ("enrollment_open", "Enrollment Open"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    course = models.ForeignKey(
        Course,
        related_name="batches",
        on_delete=models.CASCADE,
        help_text="The course this batch is running for",
    )

    batch_number = models.PositiveIntegerField(
        help_text="Batch sequence number (1, 2, 3, etc.)"
    )

    batch_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional custom batch name (e.g., 'Winter 2025', 'Weekend Batch')",
    )

    slug = models.SlugField(
        max_length=300,
        unique=True,
        db_index=True,
        help_text="URL-friendly slug (auto-generated from course + batch number)",
    )

    # Scheduling
    start_date = models.DateField(help_text="When this batch starts")
    end_date = models.DateField(help_text="When this batch ends")
    enrollment_start_date = models.DateField(
        null=True,
        blank=True,
        help_text="When enrollment opens (optional, defaults to now)",
    )
    enrollment_end_date = models.DateField(
        null=True,
        blank=True,
        help_text="When enrollment closes (optional, defaults to start_date)",
    )

    # Capacity
    max_students = models.PositiveIntegerField(
        default=30, help_text="Maximum number of students allowed in this batch"
    )
    enrolled_students = models.PositiveIntegerField(
        default=0,
        editable=False,
        help_text="Current number of enrolled students (auto-calculated)",
    )

    # Pricing (optional override - if not set, uses course default pricing)
    custom_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Custom price for this batch (optional, overrides course price)",
    )

    # Installment options per batch (override course defaults)
    installment_available = models.BooleanField(
        null=True,
        blank=True,
        help_text="Override course installment setting (None = use course default, True = enable, False = disable)",
    )
    installment_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Batch-specific installment count (overrides course setting if installment_available=True)",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=BATCH_STATUS_CHOICES,
        default="upcoming",
        db_index=True,
        help_text="Current status of this batch",
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this batch is active and visible",
    )

    # Additional info
    description = models.TextField(
        blank=True, help_text="Batch-specific description or notes (optional)"
    )

    class Meta(TimeStampedModel.Meta):
        verbose_name = "Course Batch"
        verbose_name_plural = "Course Batches"
        ordering = ["-start_date", "batch_number"]
        unique_together = ["course", "batch_number"]

        indexes = [
            models.Index(fields=["course", "status", "is_active"]),
            models.Index(fields=["start_date", "status"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["status", "is_active"]),
        ]

    def save(self, *args, **kwargs):
        """Auto-generate slug and update status based on dates."""
        if not self.pk or "status" not in kwargs.get("update_fields", []):
            self._update_status()

        if not self.slug:
            base_slug = f"{self.course.slug}-batch-{self.batch_number}"
            self.slug = base_slug

            # Ensure uniqueness
            counter = 1
            while (
                CourseBatch.objects.filter(slug=self.slug).exclude(pk=self.pk).exists()
            ):
                self.slug = f"{base_slug}-{counter}"
                counter += 1

        # Auto-update status based on dates
        self._update_status()

        super().save(*args, **kwargs)

    def _update_status(self):
        """Update batch status based on current date and enrollment status."""
        from django.utils import timezone

        now = timezone.now().date()

        # Don't auto-update if manually set to cancelled
        if self.status == "cancelled":
            return

        # Check if completed
        if self.end_date and now > self.end_date:
            self.status = "completed"
        # Check if running
        elif self.start_date and now >= self.start_date and now <= self.end_date:
            self.status = "running"
        # Check if enrollment is open
        elif self.is_active and self._check_enrollment_open(now):
            self.status = "enrollment_open"
        # Otherwise upcoming
        else:
            self.status = "upcoming"

    def _check_enrollment_open(self, now):
        """Helper to check if enrollment is open for a given date."""
        enrollment_start = (
            self.enrollment_start_date or self.created_at.date()
            if self.created_at
            else now
        )
        enrollment_end = self.enrollment_end_date or self.start_date

        return (
            now >= enrollment_start
            and now <= enrollment_end
            and self.enrolled_students < self.max_students
        )

    def clean(self):
        """Validate batch dates."""
        from django.core.exceptions import ValidationError

        if self.start_date and self.end_date:
            if self.end_date <= self.start_date:
                raise ValidationError(
                    {"end_date": "End date must be after start date."}
                )

        if self.enrollment_end_date and self.start_date:
            if self.enrollment_end_date > self.start_date:
                raise ValidationError(
                    {
                        "enrollment_end_date": "Enrollment must close before or on the start date."
                    }
                )

    @property
    def is_enrollment_open(self):
        """Check if enrollment is currently open for this batch."""
        from django.utils import timezone

        now = timezone.now().date()

        if not self.is_active or self.status in ["cancelled", "completed"]:
            return False

        # Check enrollment window
        enrollment_start = self.enrollment_start_date or self.created_at.date()
        enrollment_end = self.enrollment_end_date or self.start_date

        if now < enrollment_start or now > enrollment_end:
            return False

        # Check capacity
        if self.enrolled_students >= self.max_students:
            return False

        return True

    @property
    def available_seats(self):
        """Calculate remaining available seats."""
        return max(0, self.max_students - self.enrolled_students)

    @property
    def is_full(self):
        """Check if batch is at capacity."""
        return self.enrolled_students >= self.max_students

    def get_display_name(self):
        """Get display name for this batch (batch info only, without course title)."""
        if self.batch_name:
            return self.batch_name
        return f"Batch {self.batch_number}"

    def update_enrolled_count(self):
        """Update enrolled_students count from actual enrollments."""
        from api.models.models_order import Enrollment

        self.enrolled_students = Enrollment.objects.filter(
            batch=self, is_active=True
        ).count()
        self.save(update_fields=["enrolled_students"])

    def __str__(self):
        return self.get_display_name()


# Section 7: Key Benefits
class KeyBenefit(OptimizedImageModel):
    """Key benefits students will gain from taking the course."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        CourseDetail, related_name="benefits", on_delete=models.CASCADE
    )
    icon = models.ImageField(upload_to="courses/benefits/")
    title = models.CharField(max_length=100)
    text = CKEditor5Field(help_text="Rich text description of the benefit")
    is_active = models.BooleanField(
        default=True, help_text="Whether this benefit is active and visible"
    )

    # Image optimization configuration
    IMAGE_FIELDS_OPTIMIZATION = {
        "icon": {
            "max_size": (200, 200),
            "min_size": (50, 50),
            "max_bytes": 100 * 1024,  # 100KB
            "max_upload_mb": 2,
        }
    }

    class Meta(OptimizedImageModel.Meta):
        verbose_name = "Course Key Benefit"
        verbose_name_plural = "Course Key Benefits"

    def __str__(self):
        return self.title


# Section 9 – Left Image / Right Text + Button
class SideImageSection(OptimizedImageModel):
    """Side image sections with text and call-to-action buttons."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        CourseDetail, related_name="side_image_sections", on_delete=models.CASCADE
    )
    image = models.ImageField(upload_to="courses/side_sections/")
    title = models.CharField(max_length=200)
    text = CKEditor5Field(help_text="Rich text content for the side section")
    button_text = models.CharField(max_length=100, blank=True)
    button_url = models.URLField(blank=True)
    is_active = models.BooleanField(
        default=True, help_text="Whether this side image section is active and visible"
    )

    # Image optimization configuration
    IMAGE_FIELDS_OPTIMIZATION = {
        "image": {
            "max_size": (1200, 800),
            "min_size": (600, 400),
            "max_bytes": 400 * 1024,  # 400KB
            "max_upload_mb": 3,
        }
    }

    class Meta(OptimizedImageModel.Meta):
        verbose_name = "Course Side Image Section"
        verbose_name_plural = "Course Side Image Sections"

    def __str__(self):
        return f"Side section: {self.title}"


# Section 10: Success Stories
class SuccessStory(OptimizedImageModel):
    """Student success stories and testimonials for the course."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        CourseDetail, related_name="success_stories", on_delete=models.CASCADE
    )
    icon = models.ImageField(upload_to="courses/stories/")
    description = CKEditor5Field(help_text="Rich text description of the success story")
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(
        default=True, help_text="Whether this success story is active and visible"
    )

    # Image optimization configuration
    IMAGE_FIELDS_OPTIMIZATION = {
        "icon": {
            "max_size": (300, 300),
            "min_size": (100, 100),
            "max_bytes": 150 * 1024,  # 150KB
            "max_upload_mb": 2,
        }
    }

    class Meta(OptimizedImageModel.Meta):
        verbose_name = "Course Success Story"
        verbose_name_plural = "Course Success Stories"

    def __str__(self):
        return self.name

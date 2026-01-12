"""
Course Administration Configuration

This admin uses a clean, flat structure with one admin per model.
All relations are managed via ForeignKey / OneToOne fields.

Admin Order:
- Categories
- Courses
- Course Details
- Course Modules
- Course Batches
- Course Instructors
- Pricing & Coupons

"""

from django.contrib import admin
from django.db.models import Count

from api.admin.base_admin import BaseModelAdmin
from api.models.models_course import (
    Category,
    Course,
    CourseDetail,
    CourseContentSection,
    CourseSectionTab,
    CourseTabbedContent,
    CourseModule,
    CourseInstructor,
    CourseBatch,
    SuccessStory,
    WhyEnrol,
    KeyBenefit,
    SideImageSection
)
from api.models.models_pricing import CoursePrice, Coupon
from api.models.models_module import CourseResource, CourseResourceFile
import nested_admin

# ============================================================
# CORE COURSE STRUCTURE
# ============================================================

@admin.register(Category)
class CategoryAdmin(BaseModelAdmin):
    search_fields = ("name",)
    list_display = ("name", "is_active", "show_in_megamenu")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Course)
class CourseAdmin(BaseModelAdmin):
    search_fields = ("title", "slug")
    list_display = ("title", "category", "status", "is_active", "modules_count")
    list_filter = ("category", "status", "is_active")
    prepopulated_fields = {"slug": ("title",)}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            modules_count=Count("modules")
        )

    def modules_count(self, obj):
        return obj.modules_count

    modules_count.short_description = "Modules"
    modules_count.admin_order_field = "modules_count"


# ==============================================================================
# COURSE DETAIL ADMIN - NESTED STRUCTURE
# ==============================================================================
# This creates a 3-level nested admin interface:
# Course Detail → Content Sections → Section Tabs → Tabbed Content
# ==============================================================================


# LEVEL 3: Individual content items (deepest level)
# Each tab can have multiple content items (images, videos, etc.)
class CourseTabbedContentInline(nested_admin.NestedStackedInline):
    """
    Individual content items within a tab.
    Examples: an image with description, a video with button, etc.
    """
    model = CourseTabbedContent
    extra = 0  # Don't show empty forms by default
    min_num = 0  # Allow zero content items
    ordering = ("order",)
    classes = ("collapse",)  # Collapsed by default to reduce clutter

    fieldsets = (
        (
            "📝 Basic Content",
            {
                "fields": (
                    "media_type",  # Choose: image, video, etc.
                    "title",
                    "description",
                )
            },
        ),
        (
            "🖼️ Image Settings",
            {
                "fields": ("image",),
                "classes": ("collapse",),  # Hidden unless opened
            },
        ),
        (
            "🎥 Video Settings",
            {
                "fields": (
                    "video_provider",  # YouTube, Vimeo, etc.
                    "video_url",
                    "video_thumbnail",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "🔘 Actions & Order",
            {
                "fields": (
                    "button_text",
                    "button_link",
                    "order",  # Display order
                    "is_active",  # Show/hide this content
                )
            },
        ),
    )


# LEVEL 2: Tabs within each section
# Each section can have multiple tabs (like browser tabs)
class CourseSectionTabInline(nested_admin.NestedStackedInline):
    """
    Tabs within a content section.
    Example: "Overview" tab, "Curriculum" tab, "Instructor" tab
    """
    model = CourseSectionTab
    extra = 0
    min_num = 0
    ordering = ("order",)
    classes = ("collapse",)

    # Each tab contains multiple content items
    inlines = [CourseTabbedContentInline]


# LEVEL 1: Main content sections
# The top-level container for organizing course content
class CourseContentSectionInline(nested_admin.NestedStackedInline):
    """
    Main content sections of the course detail page.
    Example: "What You'll Learn", "Course Features", "Requirements"
    """
    model = CourseContentSection
    extra = 0
    min_num = 0
    ordering = ("order",)
    classes = ("collapse",)

    # Each section contains multiple tabs
    inlines = [CourseSectionTabInline]


# MAIN ADMIN: Course Detail page configuration
@admin.register(CourseDetail)
class CourseDetailAdmin(nested_admin.NestedModelAdmin, BaseModelAdmin):
    """
    Admin interface for managing detailed course information.

    Structure:
    CourseDetail
      └── Content Section (e.g., "What You'll Learn")
            └── Section Tab (e.g., "Overview")
                  └── Tabbed Content (e.g., Video, Image, Text)
    """
    search_fields = ("course__title",)  # Search by course name
    autocomplete_fields = ("course",)  # Dropdown with search
    list_display = ("course", "hero_button", "is_active")

    # Start with content sections
    inlines = [CourseContentSectionInline]


@admin.register(CourseModule)
class CourseModuleAdmin(BaseModelAdmin):
    search_fields = ("title", "course__title")
    autocomplete_fields = ("course",)
    list_display = ("title", "course", "order", "is_active")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(CourseInstructor)
class CourseInstructorAdmin(BaseModelAdmin):
    search_fields = ("teacher__first_name", "teacher__last_name", "course__title")
    autocomplete_fields = ("teacher", "course")
    list_display = ("teacher", "course", "instructor_type", "is_active")


@admin.register(CourseBatch)
class CourseBatchAdmin(BaseModelAdmin):
    search_fields = ("batch_name", "course__title")
    autocomplete_fields = ("course",)
    list_display = ("course", "batch_number", "start_date", "status", "is_active")
    prepopulated_fields = {"slug": ("batch_name",)}


@admin.register(SuccessStory)
class SuccessStoryAdmin(BaseModelAdmin):
    search_fields = ("name", "description", "course_detail__course__title")
    autocomplete_fields = ("course_detail",)
    list_display = ("name", "course_detail", "is_active")


@admin.register(WhyEnrol)
class WhyEnrolAdmin(BaseModelAdmin):
    search_fields = ('title', 'text')
    list_display = ('title', 'icon', 'text', 'is_active')
    autocomplete_fields = ("course_detail",)


@admin.register(KeyBenefit)
class KeyBenefitAdmin(BaseModelAdmin):
    search_fields = ('title', 'text')
    list_display = ('title', 'icon', 'text', 'is_active')
    autocomplete_fields = ("course_detail",)


@admin.register(SideImageSection)
class SideImageAdmin(admin.ModelAdmin):
    search_fields = ('title', 'text')
    list_display = ('title', 'text', 'image', 'button_text', 'button_url', 'is_active')
    autocomplete_fields = ("course_detail",)

# ============================================================
# PRICING & PROMOTIONS
# ============================================================

@admin.register(CoursePrice)
class CoursePriceAdmin(BaseModelAdmin):
    search_fields = ("course__title",)
    autocomplete_fields = ("course",)
    list_display = ("course", "base_price", "currency", "is_free", "is_active")


@admin.register(Coupon)
class CouponAdmin(BaseModelAdmin):
    search_fields = ("code",)
    filter_horizontal = ("courses",)
    list_display = ("code", "discount_type", "discount_value", "is_active")


# ============================================================
# CourseResourceFile
# ============================================================


# ============================================================
# INLINE: CourseResourceFile (INLINE ONLY)
# ============================================================

class CourseResourceFileInline(admin.TabularInline):
    model = CourseResourceFile
    extra = 0
    ordering = ("order",)
    fields = ("file", "order", "file_size", "created_at")
    readonly_fields = ("file_size", "created_at")


# ============================================================
# MAIN ADMIN: CourseResource
# ============================================================

@admin.register(CourseResource)
class CourseResourceAdmin(BaseModelAdmin):
    search_fields = (
        "title",
        "module__title",
        "module__course__title",
    )
    autocomplete_fields = (
        "module",
        "batch",
        "live_class",
        "uploaded_by",
    )
    list_display = (
        "title",
        "module",
        "batch",
        "resource_type",
        "is_active",
        "order",
    )
    list_filter = (
        "resource_type",
        "is_active",
        "module__course",
    )
    ordering = ("order",)
    inlines = [CourseResourceFileInline]

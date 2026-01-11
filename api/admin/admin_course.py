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
    CourseBatch, SuccessStory,
)
from api.models.models_pricing import CoursePrice, Coupon
from api.models.models_module import CourseResource, CourseResourceFile

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


@admin.register(CourseDetail)
class CourseDetailAdmin(BaseModelAdmin):
    search_fields = ("course__title",)
    autocomplete_fields = ("course",)
    list_display = ("course", "hero_button", "is_active")


@admin.register(CourseContentSection)
class CourseContentSectionAdmin(BaseModelAdmin):
    search_fields = ("section_name", "course_detail__course__title")
    autocomplete_fields = ("course_detail",)
    list_display = ("section_name", "course_detail", "order", "is_active")


@admin.register(CourseSectionTab)
class CourseSectionTabAdmin(BaseModelAdmin):
    search_fields = ("tab_name", "section__section_name")
    autocomplete_fields = ("section",)
    list_display = ("tab_name", "section", "order", "is_active")


@admin.register(CourseTabbedContent)
class CourseTabbedContentAdmin(BaseModelAdmin):
    search_fields = ("title", "tab__tab_name")
    autocomplete_fields = ("tab",)
    list_display = ("title", "tab", "media_type", "order", "is_active")


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
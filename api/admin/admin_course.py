"""
Course Administration Configuration

This module configures Django admin interfaces for course-related models.
All course-related admin classes are prefixed with "Course" for easy identification.

Admin Structure:
- Course Category: Organize courses into categories
- Course: Main course management with nested details
- Course Price: Standalone pricing management
- Course Coupon: Discount codes and promotions
- Course Instructor: Teacher assignments
- Course Detail & Related: Nested components (tabs, modules, benefits, etc.)
"""

import nested_admin
from django.contrib import admin
from django.forms import BaseInlineFormSet
from django.utils import timezone
from django.utils.html import format_html
from django.template.response import TemplateResponse
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.db import models as dj_models

from api.admin.base_admin import BaseModelAdmin
from api.models.models_course import (Category, Course, CourseDetail,
                                      CourseInstructor, CourseModule, KeyBenefit,
                                      SideImageSection, SuccessStory, WhyEnrol,
                                      CourseContentSection, CourseSectionTab, CourseTabbedContent)
from api.models.models_pricing import Coupon, CoursePrice
from api.models.models_module import LiveClass, Assignment, Quiz
# OLD: from api.models.models_progress import ModuleQuiz, ModuleAssignment
# Use NEW system: Quiz, Assignment, LiveClass from models_module.py

# ========== Custom Formsets ==========

class RequireOneFormSet(BaseInlineFormSet):
    """Formset that ignores empty forms - allows saving without filling all inlines."""
    
    def clean(self):
        """Skip validation for empty forms."""
        super().clean()
        # Don't require any minimum number of forms
        # This allows saving the parent without filling nested inlines
    
    def is_valid(self):
        """Check validity but don't require filled forms."""
        return super().is_valid()


# ========== Nested Inlines for CourseDetail ==========

# Triple-nested structure: Section -> Tab -> Content
class CourseTabbedContentInline(nested_admin.NestedStackedInline):
    """Inline for content items within a section tab (supports image with optional video popup)."""
    model = CourseTabbedContent
    formset = RequireOneFormSet
    extra = 0 
    fields = [
        'order', 'media_type', 'is_active',
        'title', 'description',
        'image', 'video_provider', 'video_url', 'video_thumbnail',
        'button_text', 'button_link'
    ]
    show_change_link = False
    verbose_name = "Content Item"
    verbose_name_plural = "Content Items (Image can have video popup link)"
    ordering = ['order']


class CourseSectionTabInline(nested_admin.NestedStackedInline):
    """Inline for sub-tabs within a content section (max 2 tabs per section)."""
    model = CourseSectionTab
    formset = RequireOneFormSet
    extra = 0  # Don't show extra empty forms - use "Add another" button instead
    max_num = 2  # Maximum 2 tabs per section
    fields = ['order', 'tab_name', 'is_active']
    show_change_link = False
    verbose_name = "Tab"
    verbose_name_plural = "Tabs (Maximum 2 per section)"
    ordering = ['order']
    inlines = [CourseTabbedContentInline]


class CourseContentSectionInline(nested_admin.NestedStackedInline):
    """Inline for main content sections (each can have up to 2 tabs)."""
    model = CourseContentSection
    formset = RequireOneFormSet
    extra = 0  # Don't show extra empty forms - use "Add another" button instead
    fields = ['order', 'section_name', 'is_active']
    show_change_link = False
    verbose_name = "Content Section"
    verbose_name_plural = "Content Sections (Add unlimited sections, each with up to 2 tabs)"
    ordering = ['order']
    inlines = [CourseSectionTabInline]


class WhyEnrolInline(nested_admin.NestedStackedInline):
    """Inline for why enrol sections."""
    model = WhyEnrol
    extra = 0
    fields = ['icon', 'title', 'text', 'is_active']
    show_change_link = False
    verbose_name = "Why Enrol Section"
    verbose_name_plural = "Why Enrol Sections (Add as many as needed)"



class CourseModuleInline(nested_admin.NestedStackedInline):
    """Inline for course modules (frontend display only).
    
    Note: Module content (LiveClass, Assignment, Quiz) is managed separately
    from the admin left navigation, not nested here.
    """
    model = CourseModule
    extra = 0
    fields = ['order', 'title', 'short_description', 'is_active']
    ordering = ['order']
    show_change_link = False
    verbose_name = "Module/Chapter"
    verbose_name_plural = "Modules/Chapters (Add unlimited modules)"
    inlines = []  # Module content managed separately from left nav


class KeyBenefitInline(nested_admin.NestedStackedInline):
    """Inline for key benefits."""
    model = KeyBenefit
    extra = 0
    fields = ['icon', 'title', 'text', 'is_active']
    show_change_link = False
    verbose_name = "Key Benefit"
    verbose_name_plural = "Key Benefits (Add as many as needed)"


class SideImageSectionInline(nested_admin.NestedStackedInline):
    """Inline for side image sections."""
    model = SideImageSection
    extra = 0
    fields = ['image', 'title', 'text', 'button_text', 'button_url', 'is_active']
    show_change_link = False
    verbose_name = "Side Image Section"
    verbose_name_plural = "Side Image Sections (Add as many as needed)"


class SuccessStoryInline(nested_admin.NestedStackedInline):
    """Inline for success stories."""
    model = SuccessStory
    extra = 0
    fields = ['icon', 'name', 'description', 'is_active']
    show_change_link = False
    verbose_name = "Success Story"
    verbose_name_plural = "Success Stories (Add as many as needed)"


class CoursePriceInline(nested_admin.NestedStackedInline):
    """Inline for course pricing (one per course)."""
    model = CoursePrice
    extra = 0
    max_num = 1  # Only one price per course (OneToOne relationship)
    fields = [
        'base_price',
        'currency',
        'is_free',
        'discount_percentage',
        'discount_amount',
        'discount_start_date',
        'discount_end_date',
        'effective_price_display',
        'savings_display',
        'installment_available',
        'installment_count',
        'installment_display',
        'is_active',
    ]
    show_change_link = False
    verbose_name = "Course Pricing"
    verbose_name_plural = "Course Pricing (One per course)"
    
    readonly_fields = ['effective_price_display', 'savings_display', 'installment_display']
    
    def effective_price_display(self, obj):
        if obj.pk:
            price = obj.get_discounted_price()
            currency = obj.currency if obj.currency else 'BDT'
            return f"{price} {currency}"
        return "-"
    effective_price_display.short_description = "Current Price"
    
    def savings_display(self, obj):
        if obj.pk and obj.base_price:
            savings = obj.get_savings()
            currency = obj.currency if obj.currency else 'BDT'
            if savings > 0:
                return format_html(
                    '<span style="color: #2e7d32; font-weight: bold;">{} {} saved</span>',
                    savings,
                    currency
                )
            return "No savings"
        return "-"
    savings_display.short_description = "Savings"
    
    def installment_display(self, obj):
        if obj.pk and obj.installment_available and obj.installment_count:
            amount = obj.get_installment_amount()
            currency = obj.currency if obj.currency else 'BDT'
            if amount:
                return f"{amount} {currency} x {obj.installment_count} installments"
        return "Not available"
    installment_display.short_description = "Installment Plan"


class CourseInstructorInline(nested_admin.NestedStackedInline):
    """Inline for assigning teachers to courses."""
    model = CourseInstructor
    extra = 0
    fields = ['teacher', 'instructor_type', 'is_active', 'assigned_date']
    readonly_fields = ['assigned_date']
    autocomplete_fields = ['teacher']
    show_change_link = False
    sortable_field_name = None  # Disable sorting for nested inline compatibility
    verbose_name = "Instructor"
    verbose_name_plural = "Instructors (Add multiple instructors)"
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter teacher choices to only show users with teacher role."""
        if db_field.name == "teacher":
            from api.models.models_auth import CustomUser
            kwargs["queryset"] = CustomUser.objects.filter(role='teacher', is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class CourseDetailInline(nested_admin.NestedStackedInline):
    """Nested inline for course details under Course (one per course with unlimited nested items)."""
    model = CourseDetail
    extra = 0
    max_num = 1  # Only one detail section per course (OneToOne relationship)
    fields = ['hero_text', 'hero_description', 'hero_button', 'is_active']
    inlines = [
        CourseContentSectionInline,  # New: Replaces CourseTabInline, CourseMediaTabInline
        WhyEnrolInline,
        CourseModuleInline,
        KeyBenefitInline,
        SideImageSectionInline,
        SuccessStoryInline,
    ]
    show_change_link = True
    verbose_name = "Course Detail Page"
    verbose_name_plural = "Course Detail Page (Contains unlimited nested content)"


# ========== Top-Level Admin Models ==========

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'show_in_megamenu', 'courses_count', 'created_at')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ('is_active', 'show_in_megamenu', 'created_at')
    list_editable = ('is_active', 'show_in_megamenu')
    readonly_fields = ('created_at', 'updated_at', 'courses_count')
    
    fieldsets = (
        ("Category Info", {
            "fields": ("name", "slug", "is_active", "show_in_megamenu")
        }),
        ("Statistics", {
            "fields": ("courses_count",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
    
    def courses_count(self, obj):
        if obj.pk:
            return obj.courses.count()
        return 0
    courses_count.short_description = "Number of Courses"
    
    def has_module_permission(self, request):
        return True

    actions = ['make_category_show_in_megamenu', 'remove_category_show_in_megamenu']

    def make_category_show_in_megamenu(self, request, queryset):
        updated = queryset.update(show_in_megamenu=True)
        self.message_user(request, f"{updated} category(ies) marked to show in megamenu.")
    make_category_show_in_megamenu.short_description = "Mark selected categories to show in megamenu"

    def remove_category_show_in_megamenu(self, request, queryset):
        updated = queryset.update(show_in_megamenu=False)
        self.message_user(request, f"{updated} category(ies) removed from megamenu.")
    remove_category_show_in_megamenu.short_description = "Remove selected categories from megamenu"


@admin.register(Course)
class CourseAdmin(nested_admin.NestedModelAdmin, BaseModelAdmin):
    """Main course admin with nested details and pricing."""
    list_display = (
        'title',
        'category',
        'status',
        'price_display',
        'is_active',
        'show_in_megamenu',
        'show_in_home_tab',
        'created_at',
    )
    list_filter = ('category', 'status', 'is_active', 'show_in_megamenu', 'show_in_home_tab', 'created_at')
    search_fields = ('title', 'short_description')
    prepopulated_fields = {'slug': ('title',)}
    list_editable = ('is_active', 'status', 'show_in_megamenu', 'show_in_home_tab')
    readonly_fields = ('id', 'created_at', 'updated_at', 'header_image_display')
    
    inlines = [CoursePriceInline, CourseInstructorInline, CourseDetailInline]
    
    fieldsets = (
        ("Basic Information", {
            "fields": (
                ("id",),
                ("category",),
                ("title",),
                ("slug",),
                ("status",),
                ("is_active",),
                ("show_in_megamenu",),
                ("show_in_home_tab",)
            )
        }),
        ("Content", {
            "fields": (
                ("short_description",),
                ("full_description",)
            )
        }),
        ("Media", {
            "fields": (
                ("header_image",),
                ("header_image_display",)
            )
        }),
        ("Timestamps", {
            "fields": (
                ("created_at",),
                ("updated_at",)
            ),
            "classes": ("collapse",)
        }),
    )
    
    def header_image_display(self, obj):
        if obj.header_image:
            return format_html(
                '<img src="{}" style="max-height: 200px; max-width: 400px;" />',
                obj.header_image.url
            )
        return "No header image"
    header_image_display.short_description = "Current Header Image"
    
    def price_display(self, obj):
        try:
            pricing = obj.pricing
            if pricing.is_free:
                return format_html('<span style="color: #2e7d32; font-weight: bold;">FREE</span>')
            
            current_price = pricing.get_discounted_price()
            if pricing.is_currently_discounted():
                return format_html(
                    '<span style="text-decoration: line-through; color: #999;">{} {}</span> '
                    '<span style="color: #d32f2f; font-weight: bold;">{} {}</span>',
                    pricing.base_price,
                    pricing.currency,
                    current_price,
                    pricing.currency
                )
            return f"{pricing.base_price} {pricing.currency}"
        except CoursePrice.DoesNotExist:
            return format_html('<span style="color: #999;">Not set</span>')
    price_display.short_description = "Price"
    
    def has_module_permission(self, request):
        return True

    # Admin actions to toggle megamenu visibility for multiple courses
    actions = ['make_show_in_megamenu', 'remove_show_in_megamenu', 'make_show_in_home_tab', 'remove_show_in_home_tab']

    def bulk_add_modules(self, request, queryset):
        """
        Admin action to bulk-create modules for selected courses.

        Presents a textarea where admin can paste one module title per line.
        Creates CourseModule instances under each course's CourseDetail.
        """
        if 'apply' in request.POST:
            modules_text = request.POST.get('modules_text', '')
            lines = [l.strip() for l in modules_text.splitlines() if l.strip()]
            created = 0
            skipped = []
            for course in queryset:
                # Need CourseDetail to attach modules
                detail = getattr(course, 'detail', None)
                if not detail:
                    skipped.append(course.title)
                    continue
                # Determine starting order
                existing_max = CourseModule.objects.filter(course=detail).aggregate(dj_models.Max('order'))['order__max'] or 0
                order = existing_max + 1
                for title in lines:
                    CourseModule.objects.create(course=detail, title=title, short_description='', order=order, is_active=True)
                    created += 1
                    order += 1

            msg = f"Created {created} module(s)."
            if skipped:
                msg += " Skipped courses without CourseDetail: " + ", ".join(skipped)
            self.message_user(request, msg)
            return HttpResponseRedirect(request.get_full_path())

        # show intermediate form
        context = dict(
            self.admin_site.each_context(request),
            courses=queryset,
            action='bulk_add_modules',
        )
        return TemplateResponse(request, "admin/bulk_add_modules.html", context)

    bulk_add_modules.short_description = "Bulk add modules (paste one title per line)"
    actions.append('bulk_add_modules')

    def make_show_in_megamenu(self, request, queryset):
        updated = queryset.update(show_in_megamenu=True)
        self.message_user(request, f"{updated} course(s) marked to show in megamenu.")
    make_show_in_megamenu.short_description = "Mark selected courses to show in megamenu"

    def remove_show_in_megamenu(self, request, queryset):
        updated = queryset.update(show_in_megamenu=False)
        self.message_user(request, f"{updated} course(s) removed from megamenu.")
    remove_show_in_megamenu.short_description = "Remove selected courses from megamenu"
    
    def make_show_in_home_tab(self, request, queryset):
        updated = queryset.update(show_in_home_tab=True)
        self.message_user(request, f"{updated} course(s) marked to show in home tab.")
    make_show_in_home_tab.short_description = "Mark selected courses to show in home tab"

    def remove_show_in_home_tab(self, request, queryset):
        updated = queryset.update(show_in_home_tab=False)
        self.message_user(request, f"{updated} course(s) removed from home tab.")
    remove_show_in_home_tab.short_description = "Remove selected courses from home tab"


@admin.register(CourseDetail)
class CourseDetailAdmin(BaseModelAdmin):
    """Course detail pages - usually managed via nested admin within Course."""
    list_display = ('course', 'hero_button', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('course__title', 'hero_text')
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    fieldsets = (
        ("Course Link", {
            "fields": ("id", "course", "is_active")
        }),
        ("Hero Section", {
            "fields": ("hero_text", "hero_description", "hero_button")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
    
    def has_module_permission(self, request):
        # Hidden - use nested admin in Course instead
        return False


@admin.register(CoursePrice)
class CoursePriceAdmin(BaseModelAdmin):
    """Standalone pricing admin for advanced management."""
    list_display = (
        'course',
        'base_price_display',
        'current_price_display',
        'discount_status',
        'is_free',
        'is_active',
    )
    list_filter = ('currency', 'is_free', 'is_active', 'installment_available')
    search_fields = ('course__title',)
    readonly_fields = (
        'created_at',
        'updated_at',
        'effective_price_display',
        'savings_display',
        'installment_display_detailed',
    )
    
    fieldsets = (
        ("Course & Currency", {
            "fields": ("course", "currency", "is_active")
        }),
        ("Base Pricing", {
            "fields": ("base_price", "is_free")
        }),
        ("Discount Settings", {
            "fields": (
                "discount_percentage",
                "discount_amount",
                "discount_start_date",
                "discount_end_date",
            )
        }),
        ("Current Pricing (Read-only)", {
            "fields": ("effective_price_display", "savings_display"),
            "classes": ("collapse",)
        }),
        ("Installment Options", {
            "fields": ("installment_available", "installment_count", "installment_display_detailed"),
            "classes": ("collapse",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
    
    def base_price_display(self, obj):
        return f"{obj.base_price} {obj.currency}"
    base_price_display.short_description = "Base Price"
    
    def current_price_display(self, obj):
        if obj.is_free:
            return format_html('<span style="color: #2e7d32; font-weight: bold;">FREE</span>')
        
        current = obj.get_discounted_price()
        if obj.is_currently_discounted():
            return format_html(
                '<span style="color: #d32f2f; font-weight: bold;">{} {}</span>',
                current,
                obj.currency
            )
        return f"{current} {obj.currency}"
    current_price_display.short_description = "Current Price"
    
    def discount_status(self, obj):
        if obj.is_currently_discounted():
            savings = obj.get_savings()
            return format_html(
                '<span style="color: #2e7d32;">✓ Active (Save {} {})</span>',
                savings,
                obj.currency
            )
        
        now = timezone.now()
        if obj.discount_start_date and now < obj.discount_start_date:
            return format_html('<span style="color: #ff9800;">⏳ Scheduled</span>')
        if obj.discount_end_date and now > obj.discount_end_date:
            return format_html('<span style="color: #999;">⏹ Expired</span>')
        
        return format_html('<span style="color: #999;">-</span>')
    discount_status.short_description = "Discount Status"
    
    def effective_price_display(self, obj):
        return f"{obj.get_discounted_price()} {obj.currency}"
    effective_price_display.short_description = "Effective Price"
    
    def savings_display(self, obj):
        savings = obj.get_savings()
        if savings > 0:
            return format_html(
                '<span style="color: #2e7d32; font-weight: bold;">{} {} saved</span>',
                savings,
                obj.currency
            )
        return "No savings"
    savings_display.short_description = "Total Savings"
    
    def installment_display_detailed(self, obj):
        if obj.installment_available:
            amount = obj.get_installment_amount()
            total = obj.get_discounted_price()
            return format_html(
                '<strong>{} {} x {} installments</strong><br>Total: {} {}',
                amount,
                obj.currency,
                obj.installment_count,
                total,
                obj.currency
            )
        return "Not available"
    installment_display_detailed.short_description = "Installment Plan"
    
    def has_module_permission(self, request):
        # Allow all staff to view pricing
        return True


@admin.register(Coupon)
class CouponAdmin(BaseModelAdmin):
    """Coupon management admin."""
    list_display = (
        'code',
        'discount_type',
        'discount_value',
        'validity_status',
        'usage_display',
        'is_active',
    )
    list_filter = ('discount_type', 'is_active', 'apply_to_all', 'valid_from', 'valid_until')
    search_fields = ('code', 'courses__title')
    filter_horizontal = ('courses',)
    readonly_fields = ('id', 'used_count', 'created_at', 'updated_at', 'validity_display')
    
    fieldsets = (
        ("Coupon Code", {
            "fields": ("id", "code", "is_active")
        }),
        ("Discount Configuration", {
            "fields": ("discount_type", "discount_value")
        }),
        ("Applicability", {
            "fields": ("apply_to_all", "courses")
        }),
        ("Usage Limits", {
            "fields": ("max_uses", "used_count", "max_uses_per_user")
        }),
        ("Validity Period", {
            "fields": ("valid_from", "valid_until", "validity_display")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
    
    def validity_status(self, obj):
        is_valid, message = obj.is_valid()
        if is_valid:
            return format_html('<span style="color: #2e7d32;">✓ Valid</span>')
        return format_html('<span style="color: #d32f2f;">✗ {}</span>', message)
    validity_status.short_description = "Status"
    
    def usage_display(self, obj):
        if obj.max_uses:
            percentage = (obj.used_count / obj.max_uses) * 100
            color = "#2e7d32" if percentage < 80 else "#ff9800" if percentage < 100 else "#d32f2f"
            return format_html(
                '<span style="color: {};">{} / {} ({}%)</span>',
                color,
                obj.used_count,
                obj.max_uses,
                int(percentage)
            )
        return f"{obj.used_count} / ∞"
    usage_display.short_description = "Usage"
    
    def validity_display(self, obj):
        # Return empty for new objects (not yet saved)
        if not obj.pk or not obj.valid_from or not obj.valid_until:
            return "-"
        
        now = timezone.now()
        if now < obj.valid_from:
            delta = obj.valid_from - now
            return format_html(
                '<span style="color: #ff9800;">Starts in {} days</span>',
                delta.days
            )
        elif now > obj.valid_until:
            delta = now - obj.valid_until
            return format_html(
                '<span style="color: #999;">Expired {} days ago</span>',
                delta.days
            )
        else:
            delta = obj.valid_until - now
            return format_html(
                '<span style="color: #2e7d32;">Valid for {} more days</span>',
                delta.days
            )
    validity_display.short_description = "Validity Info"
    
    def has_module_permission(self, request):
        return True


# ========== Hidden Nested Models ==========

@admin.register(CourseContentSection)
class CourseContentSectionAdmin(BaseModelAdmin):
    """Course content sections - usually managed via nested admin."""
    list_display = ('section_name', 'course', 'order', 'is_active', 'tab_count')
    list_filter = ('is_active',)
    search_fields = ('section_name', 'course__course__title')
    list_editable = ('is_active', 'order')
    ordering = ('course', 'order')
    
    def tab_count(self, obj):
        return obj.tabs.count()
    tab_count.short_description = "Tabs"
    
    def has_module_permission(self, request):
        # Hidden - use nested admin in Course instead
        return False


@admin.register(CourseSectionTab)
class CourseSectionTabAdmin(BaseModelAdmin):
    """Course section tabs - usually managed via nested admin."""
    list_display = ('tab_name', 'section', 'order', 'is_active', 'content_count')
    list_filter = ('is_active',)
    search_fields = ('tab_name', 'section__section_name', 'section__course__course__title')
    list_editable = ('is_active', 'order')
    ordering = ('section', 'order')
    
    def content_count(self, obj):
        return obj.contents.count()
    content_count.short_description = "Content Items"
    
    def has_module_permission(self, request):
        # Hidden - use nested admin in Course instead
        return False


@admin.register(CourseTabbedContent)
class CourseTabbedContentAdmin(BaseModelAdmin):
    """Course tabbed content - usually managed via nested admin."""
    list_display = ('title', 'tab', 'media_type', 'order', 'is_active', 'created_at')
    list_filter = ('media_type', 'video_provider', 'is_active', 'created_at')
    search_fields = ('title', 'description', 'tab__tab_name', 'tab__section__course__course__title')
    list_editable = ('is_active', 'order')
    ordering = ('tab', 'order')
    readonly_fields = ('video_id', 'created_at', 'updated_at')
    
    fieldsets = (
        ("Basic Info", {
            "fields": ("tab", "order", "media_type", "is_active")
        }),
        ("Media", {
            "fields": ("image", "video_provider", "video_url", "video_id", "video_thumbnail"),
            "description": "Image type: image required, video optional (popup). Video type: video required, image optional (poster)"
        }),
        ("Content", {
            "fields": ("title", "description", "button_text", "button_link")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
    
    def has_module_permission(self, request):
        # Hidden - use nested admin in Course instead
        return False


@admin.register(WhyEnrol)
class WhyEnrolAdmin(BaseModelAdmin):
    """Why enrol sections - usually managed via nested admin."""
    list_display = ('title', 'course', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title', 'course__course__title')
    list_editable = ('is_active',)
    
    def has_module_permission(self, request):
        # Hidden - use nested admin in Course instead
        return False


@admin.register(CourseModule)
class CourseModuleAdmin(BaseModelAdmin):
    """Course modules/chapters - usually managed via nested admin."""
    list_display = ('order', 'title', 'course', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title', 'course__course__title')
    list_editable = ('is_active',)
    ordering = ('course', 'order')
    
    def has_module_permission(self, request):
        # Allow access via left admin navigation
        return True


@admin.register(KeyBenefit)
class KeyBenefitAdmin(BaseModelAdmin):
    """Course key benefits - usually managed via nested admin."""
    list_display = ('title', 'course', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title', 'course__course__title')
    list_editable = ('is_active',)
    
    def has_module_permission(self, request):
        # Hidden - use nested admin in Course instead
        return False


@admin.register(SideImageSection)
class SideImageSectionAdmin(BaseModelAdmin):
    """Course side image sections - usually managed via nested admin."""
    list_display = ('title', 'course', 'button_text', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title', 'course__course__title')
    list_editable = ('is_active',)
    
    def has_module_permission(self, request):
        # Hidden - use nested admin in Course instead
        return False


@admin.register(SuccessStory)
class SuccessStoryAdmin(BaseModelAdmin):
    """Course success stories - usually managed via nested admin."""
    list_display = ('name', 'course', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'course__course__title')
    list_editable = ('is_active',)
    
    def has_module_permission(self, request):
        # Hidden - use nested admin in Course instead
        return False


@admin.register(CourseInstructor)
class CourseInstructorAdmin(BaseModelAdmin):
    """Standalone admin for managing course instructor assignments."""
    list_display = (
        'teacher_name',
        'course',
        'instructor_type_display',
        'modules_count',
        'is_active',
        'assigned_date',
    )
    list_filter = ('instructor_type', 'is_active', 'assigned_date', 'course__category')
    search_fields = ('teacher__first_name', 'teacher__last_name', 'course__title')
    readonly_fields = ('assigned_date', 'is_lead_instructor')
    autocomplete_fields = ['teacher', 'course']
    filter_horizontal = ('modules',)
    
    fieldsets = (
        ("Assignment Info", {
            "fields": ("course", "teacher", "instructor_type", "is_active")
        }),
        ("Module Assignment", {
            "fields": ("modules",),
            "description": "Select specific modules this instructor teaches (leave empty for entire course)"
        }),
        ("Metadata", {
            "fields": ("assigned_date", "is_lead_instructor"),
            "classes": ("collapse",)
        }),
    )
    
    def teacher_name(self, obj):
        return obj.teacher.get_full_name
    teacher_name.short_description = "Instructor"
    teacher_name.admin_order_field = 'teacher__first_name'
    
    def instructor_type_display(self, obj):
        colors = {
            'lead': '#2e7d32',
            'support': '#1976d2',
            'assistant': '#f57c00'
        }
        color = colors.get(obj.instructor_type, '#666')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_instructor_type_display()
        )
    instructor_type_display.short_description = "Type"
    instructor_type_display.admin_order_field = 'instructor_type'
    
    def modules_count(self, obj):
        count = obj.modules.count()
        if count == 0:
            return format_html('<span style="color: #2e7d32;">All modules</span>')
        return format_html('<span>{} modules</span>', count)
    modules_count.short_description = "Teaching"
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter teacher choices to only show users with teacher role."""
        if db_field.name == "teacher":
            from api.models.models_auth import CustomUser
            kwargs["queryset"] = CustomUser.objects.filter(role='teacher', is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def has_module_permission(self, request):
        return True

from django.contrib import admin
from django.utils.html import format_html

from api.admin.base_admin import BaseModelAdmin
from api.models.models_home import Brand, HeroSection, HeroSlideText


class HeroSlideTextInline(admin.TabularInline):
    model = HeroSlideText
    extra = 1
    fields = ("text", "order")
    ordering = ("order",)


@admin.register(HeroSection)
class HeroSectionAdmin(BaseModelAdmin):
    list_display = ("page_name", "title", "is_active", "created_at", "updated_at")
    list_filter = ("is_active", "page_name", "created_at")
    search_fields = ("title", "description")
    list_editable = ("is_active",)
    inlines = [HeroSlideTextInline]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = (
        (None, {"fields": ("page_name", "title", "description", "is_active")}),
        (
            "Buttons",
            {
                "fields": (
                    ("button1_text", "button1_url"),
                    ("button2_text", "button2_url"),
                )
            },
        ),
        ("Media", {"fields": ("banner_image",)}),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        """Make page_name readonly after creation"""
        if obj:  # editing an existing object
            return self.readonly_fields + ["page_name"]
        return self.readonly_fields


# ===============================end hero section admin===============================

# ===============================start brand section admin===============================


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("logo_preview", "is_active", "created_at")
    list_editable = ("is_active",)
    search_fields = ("logo_url",)
    list_filter = ("is_active",)
    ordering = ("created_at",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Basic Information", {"fields": ("logo",)}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def logo_preview(self, obj):
        if obj.logo and hasattr(obj.logo, "url"):
            return format_html(
                '<img src="{}" width="60" height="60" style="object-fit:contain;border-radius:8px;" />',
                obj.logo.url,
            )
        return "—"

    logo_preview.short_description = "Brands Preview"


# ===============================end brand section admin===============================

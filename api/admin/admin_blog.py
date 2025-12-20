from django.contrib import admin

from api.admin.base_admin import BaseModelAdmin
from api.models.models_blog import Blog, BlogCategory


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at", "updated_at")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")

    def has_module_permission(self, request):
        return False

    fieldsets = (
        ("Category Info", {"fields": ("name", "slug")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(Blog)
class BlogAdmin(BaseModelAdmin):
    list_display = ("title", "category", "status", "show_in_home_latest", "created_at", "updated_at")
    list_filter = ("category", "status", "show_in_home_latest", "created_at", "updated_at")
    search_fields = ("title", "excerpt", "content")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Basic Info", {"fields": ("title", "slug", "category", "status", "excerpt")}),
        (
            "Display Settings",
            {"fields": ("show_in_home_latest",), "description": "Control where this blog appears on the website"},
        ),
        ("Content", {"fields": ("content", "featured_image")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

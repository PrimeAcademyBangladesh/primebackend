"""Admin configuration for footer and nested link models.

Provides nested inlines and a singleton-like Footer admin to manage the
public site footer content.
"""

import nested_admin
from django.contrib import admin

from api.models.models_footer import Footer, LinkGroup, QuickLink, SocialLink


# -----------------------------
# QuickLink Inline
# -----------------------------
class QuickLinkInline(nested_admin.NestedStackedInline):
    model = QuickLink
    extra = 1
    fields = ("label", "url", "is_external", "order", "is_active")
    ordering = ("order",)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)

        def add_fields(form, index):
            super(form.__class__, form).add_fields(form, index)
            form.form_title = f"Footer Link {index + 1}"
        formset.form.add_fields = add_fields
        return formset


# -----------------------------
# LinkGroup Inline
# -----------------------------
class LinkGroupInline(nested_admin.NestedStackedInline):
    model = LinkGroup
    extra = 1
    fields = ("title", "order")
    ordering = ("order",)
    inlines = [QuickLinkInline]
    verbose_name_plural = "Footer Column Groups (maximum columns: 3, if you need more, show first 3 columns)"

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)

        def add_fields(form, index):
            super(form.__class__, form).add_fields(form, index)
            form.form_title = f"Footer Column Group {index + 1}"
        formset.form.add_fields = add_fields
        return formset
    
    def has_add_permission(self, request, obj=None):
        """Restrict maximum of 3 Link Groups per Footer"""
        if obj and obj.pk and obj.link_groups.count() >= 3:
            return False
        return super().has_add_permission(request, obj)


# -----------------------------
# SocialLink Inline
# -----------------------------
class SocialLinkInline(nested_admin.NestedStackedInline):
    model = SocialLink
    extra = 1
    fields = ("platform", "url", "order", "is_active")
    ordering = ("order",)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)

        def add_fields(form, index):
            super(form.__class__, form).add_fields(form, index)
            form.form_title = f"Social Link {index + 1}"
        formset.form.add_fields = add_fields
        return formset


# -----------------------------
# Footer Admin
# -----------------------------
@admin.register(Footer)
class FooterAdmin(nested_admin.NestedModelAdmin):
    list_display = ("id", "copyright_name", "email", "phone", "updated_at")
    search_fields = ("copyright_name", "email", "phone")
    inlines = [LinkGroupInline, SocialLinkInline]
    readonly_fields = ("singleton_guard",)

    def has_add_permission(self, request):
        """Prevent adding more than one footer"""
        if Footer.objects.exists():
            return False
        return super().has_add_permission(request)

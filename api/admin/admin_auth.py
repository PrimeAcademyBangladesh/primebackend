"""Admin forms and model registrations for user and profile models.

Contains ModelAdmin and form classes to manage CustomUser, Profile and
related models in the Django admin.
"""

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.core.files.storage import default_storage
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from api.admin.base_admin import BaseModelAdmin

from ..models.models_auth import CustomUser, Profile, Skill

# Branding for the site admin
admin.site.site_header = "Prime Academy Admin"
admin.site.site_title = "Prime Academy Portal"
admin.site.index_title = "Welcome to Prime Academy Admin"



# -----------------------------
# User Forms
# -----------------------------
class CustomUserCreationForm(forms.ModelForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Password confirmation", widget=forms.PasswordInput)

    class Meta:
        model = CustomUser
        fields = ("email", "first_name", "last_name", "phone", "role", "is_enabled", "student_id")

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords don't match")
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.is_active = True
        if commit:
            user.save()
        return user


class CustomUserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(label=_("Password"))

    class Meta:
        model = CustomUser
        fields = (
            "email", "first_name", "last_name", "phone",
            "password", "is_active", "is_staff", "is_superuser", "role"
        )

    def clean_password(self):
        return self.initial["password"]


# -----------------------------
# Profile Inline
# -----------------------------
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = "Profile"
    verbose_name = "Background Information"
    autocomplete_fields = ("skills",)
    
    extra = 1

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")


# -----------------------------
# Custom User Admin
# -----------------------------

@admin.register(CustomUser)
class CustomUserAdmin(DjangoUserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    inlines = (ProfileInline,)

    list_display = ("email", "student_id", "first_name", "last_name", "role", "is_active", "is_enabled", "date_joined")
    list_filter = ("role", "is_active", "is_enabled", "is_staff", "is_superuser")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("-date_joined",)
    readonly_fields = ("last_login", "date_joined", "student_id")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "phone", "student_id")}),
        (_("Permissions"), {
            "fields": (
                "role", "is_active", "is_staff", "is_enabled", "is_superuser",
                "groups", "user_permissions"
            )
        }),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "first_name", "last_name", "phone", "role", "password1", "password2"),
        }),
    )

    def save_model(self, request, obj, form, change):
        # mark as admin-created to skip signals
        obj._created_from_admin = True
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        """
        Returns a list of readonly fields for the model admin.

        If obj is provided, it appends the "role" and "email" fields to
        the list of readonly fields, otherwise it just returns the list
        of readonly fields as is.
        """
        if obj:
            return self.readonly_fields + ("role", "email")
        return self.readonly_fields
    
    class Media:
        css = {'all': ('admin/css/ckeditor-custom.css',)}

# -----------------------------
# Hidden Admins
# -----------------------------
@admin.register(Profile)
class HiddenProfileAdmin(BaseModelAdmin):
    def has_module_permission(self, request):
        return False


@admin.register(Skill)
class HiddenSkillAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)

    def has_module_permission(self, request):
        return False


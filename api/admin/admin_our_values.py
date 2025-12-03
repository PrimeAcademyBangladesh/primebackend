import nested_admin
from django.contrib import admin

from api.admin.base_admin import BaseModelAdmin
from api.models.models_our_values import (ValueTab, ValueTabContent,
                                          ValueTabSection)


class ValueTabContentInline(nested_admin.NestedStackedInline):
    """Deepest inline: content inside a tab."""
    model = ValueTabContent
    extra = 0
    fields = [
        'title',
        'media_type',
        'image',
        'video_provider',
        'video_url',
        'video_thumbnail',
        'description',
        'button_text',
        'button_url',
        'is_active',
    ]
    readonly_fields = ['video_id']
    show_change_link = False


class ValueTabInline(nested_admin.NestedStackedInline):
    """Middle inline: tabs inside a section."""
    model = ValueTab
    extra = 0
    fields = ['title', 'slug', 'order', 'is_active']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ValueTabContentInline]
    show_change_link = True


@admin.register(ValueTabSection)
class ValueTabSectionAdmin(nested_admin.NestedModelAdmin, BaseModelAdmin):
    """Top-level model shown in admin."""
    list_display = ['title', 'page', 'order', 'is_active', 'created_at']
    list_filter = ['page', 'is_active']
    search_fields = ['title', 'subtitle']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ValueTabInline]
    list_editable = ('is_active',)
    readonly_fields = ('created_at', 'updated_at')

    # only this model appears in the admin menu
    def has_module_permission(self, request):
        return True


@admin.register(ValueTab)
class ValueTabAdmin(BaseModelAdmin):
    """Hidden: managed via nested admin."""
    def has_module_permission(self, request):
        return False


@admin.register(ValueTabContent)
class ValueTabContentAdmin(BaseModelAdmin):
    """Hidden: managed via nested admin."""
    def has_module_permission(self, request):
        return False

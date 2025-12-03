from django.contrib import admin
from django.utils.html import strip_tags

from api.admin.base_admin import BaseModelAdmin
from api.models.models_faq import FAQ, FAQItem


class FAQInline(admin.StackedInline):
    """
    Inline FAQs under their navigation item (FAQItem),
    showing Question (plain text) and Answer (CKEditor) inline.
    """
    model = FAQ
    extra = 0
    fields = ('question', 'answer', 'order', 'is_active')
    ordering = ('order',)
    show_change_link = True


@admin.register(FAQItem)
class FAQItemAdmin(BaseModelAdmin):
    """
    Admin configuration for FAQ navigation items.
    Each item can contain multiple FAQs (via inline).
    """
    list_display = ('title', 'faq_nav', 'faq_nav_slug', 'order', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('title', 'faq_nav')
    ordering = ('order', 'created_at')
    prepopulated_fields = {"faq_nav_slug": ("faq_nav",)}
    inlines = [FAQInline]


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    """
    Individual FAQ admin form — shows question preview and answer.
    """
    list_display = ('get_question_preview', 'item', 'order', 'is_active', 'created_at')
    list_filter = ('is_active', 'item__faq_nav')
    search_fields = ('question', 'answer', 'item__title')
    ordering = ('item__order', 'order', 'created_at')

    fieldsets = (
        (None, {
            'fields': ('item', 'question', 'answer')
        }),
        ('Settings', {
            'fields': ('order', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('created_at', 'updated_at')

    def get_question_preview(self, obj):
        """Show first 100 chars of question in admin list"""
        return strip_tags(obj.question)[:100]
    get_question_preview.short_description = "Question Preview"

    # Hide FAQ as separate module if editing only via FAQItem inline
    def has_module_permission(self, request):
        return False



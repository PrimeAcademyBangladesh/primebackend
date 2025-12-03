# admin.py
from django.contrib import admin

from api.models.models_seo import PageSEO


@admin.register(PageSEO)
class PageSEOAdmin(admin.ModelAdmin):
    list_display = ['page_name', 'is_active', 'meta_title', 'og_type', 'twitter_card', 'robots_meta', 'updated_at']  # Added is_active
    list_filter = ['is_active', 'og_type', 'twitter_card', 'robots_meta', 'created_at']  # Added is_active
    search_fields = ['page_name', 'meta_title', 'meta_description']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['is_active']  # Quick edit from list view
    
    fieldsets = (
        ('Page Identification', {
            'fields': ('page_name', 'is_active')  # Added is_active
        }),
        ('Basic SEO Meta', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords')
        }),
        ('Open Graph (Facebook & LinkedIn)', {
            'fields': ('og_title', 'og_description', 'og_image', 'og_type', 'og_url')
        }),
        ('Twitter Card', {
            'fields': (
                'twitter_card', 'twitter_title', 'twitter_description', 
                'twitter_image', 'twitter_site', 'twitter_creator'
            )
        }),
        ('Advanced SEO', {
            'fields': ('canonical_url', 'robots_meta', 'structured_data')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Make page_name readonly after creation"""
        if obj:  # editing an existing object
            return self.readonly_fields + ['page_name']
        return self.readonly_fields
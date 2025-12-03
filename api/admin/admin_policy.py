from django.contrib import admin

from api.admin.base_admin import BaseModelAdmin
from api.views.views_policy import PolicyPage


@admin.register(PolicyPage)
class PolicyPageAdmin(BaseModelAdmin):
    """Admin interface for managing policy-related pages."""
    list_display = ('title', 'page_name', 'id')
    
    list_display_links = ('title',)
    
    search_fields = ('title', 'page_name', 'content')
    
    list_filter = ('page_name',)
    
    readonly_fields = ('id',)
    
    ordering = ('title',)
    
    fieldsets = (
        (None, {
            'fields': ('title', 'page_name', 'content')
        }),
        ('Meta', {
            'fields': ('id',),
            'classes': ('collapse',)
        }),
    )


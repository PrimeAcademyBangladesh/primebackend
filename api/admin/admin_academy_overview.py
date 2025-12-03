from django.contrib import admin
from django.utils.html import format_html

from api.admin.base_admin import BaseModelAdmin
from api.models.models_academy_overview import AcademyOverview


@admin.register(AcademyOverview)
class AcademyOverviewAdmin(BaseModelAdmin):
    list_display = (
        'title',
        'learners_count',
        'partners_count',
        'outstanding_title',
        'partnerships_title',
        'button_text',
        'created_at',
    )

    list_editable = (
        'learners_count',
        'partners_count',
        'button_text',
    )

    search_fields = ('title', 'description', 'outstanding_title', 'partnerships_title')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'created_at', 'updated_at')

    fieldsets = (
        ('Basic', {
            'fields': (
                'id',
                'title',
                'description',
            )
        }),
        ('Counters', {
            'fields': (
                ('learners_count', 'learners_short'),
                ('partners_count', 'partners_short'),
                ('outstanding_title', 'outstanding_short'),
                ('partnerships_title', 'partnerships_short'),
            )
        }),
        ('Button', {
            'fields': (
                ('button_text', 'button_url'),
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def title_preview(self, obj):
        return obj.title if len(obj.title) < 100 else obj.title[:97] + '...'

    title_preview.short_description = 'Title'

from django.contrib import admin

from api.models.models_contact import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'full_name', 'email', 'phone', 'was_agreed')
    list_display_links = ('created_at', 'full_name')
    list_filter = ('agree_to_policy', 'created_at')
    search_fields = ('first_name', 'last_name', 'email', 'phone', 'message')
    readonly_fields = ('first_name', 'last_name', 'email', 'phone', 'message', 'agree_to_policy','created_at')

    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    full_name.short_description = 'Name'

    def was_agreed(self, obj):
        return "Yes" if obj.agree_to_policy else "No"
    was_agreed.short_description = 'Privacy Policy Agreed'

    def has_add_permission(self, request):
        return False  # Prevent manual add in admin

    fieldsets = (
        (None, {
            'fields': ('created_at', 'first_name', 'last_name', 'email', 'phone', 'agree_to_policy', ),
        }),
        ('Message Content', {
            'fields': ('message',),
            'classes': ('collapse',),
        }),
    )

"""Admin configuration for CustomPayment and EventRegistration."""

from django.contrib import admin
from django.utils.html import format_html

from api.models.models_custom_payment import CustomPayment, EventRegistration


@admin.register(CustomPayment)
class CustomPaymentAdmin(admin.ModelAdmin):
    """Admin interface for Custom Payments."""
    
    list_display = [
        'payment_number',
        'student_link',
        'course_link',
        'amount_display',
        'status_display',
        'created_by_link',
        'enrollment_link',
        'created_at',
    ]
    list_filter = [
        'status',
        'payment_method',
        'created_at',
        'completed_at',
    ]
    search_fields = [
        'payment_number',
        'student__email',
        'student__first_name',
        'student__last_name',
        'course__title',
        'title',
        'created_by__email',
    ]
    readonly_fields = [
        'id',
        'payment_number',
        'enrollment',
        'completed_at',
        'cancelled_at',
        'created_at',
        'updated_at',
    ]
    fieldsets = (
        ('Payment Information', {
            'fields': (
                'id',
                'payment_number',
                'status',
                'created_by',
            )
        }),
        ('Student & Course', {
            'fields': (
                'student',
                'course',
                'enrollment',
            )
        }),
        ('Details', {
            'fields': (
                'title',
                'description',
            )
        }),
        ('Pricing', {
            'fields': (
                'amount',
                'original_price',
                'currency',
            )
        }),
        ('Payment Details', {
            'fields': (
                'payment_method',
                'payment_id',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'completed_at',
                'cancelled_at',
            )
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    def student_link(self, obj):
        """Link to student."""
        if obj.student:
            return format_html(
                '<a href="/admin/api/customuser/{}/change/">{}</a>',
                obj.student.id,
                obj.student.email
            )
        return '-'
    student_link.short_description = 'Student'
    
    def course_link(self, obj):
        """Link to course."""
        if obj.course:
            return format_html(
                '<a href="/admin/api/course/{}/change/">{}</a>',
                obj.course.id,
                obj.course.title
            )
        return '(No Course)'
    course_link.short_description = 'Course'
    
    def created_by_link(self, obj):
        """Link to admin who created this."""
        if obj.created_by:
            return format_html(
                '<a href="/admin/api/customuser/{}/change/">{}</a>',
                obj.created_by.id,
                obj.created_by.email
            )
        return '-'
    created_by_link.short_description = 'Created By'
    
    def enrollment_link(self, obj):
        """Link to enrollment."""
        if obj.enrollment:
            return format_html(
                '<a href="/admin/api/enrollment/{}/change/">✓ View</a>',
                obj.enrollment.id
            )
        return '-'
    enrollment_link.short_description = 'Enrollment'
    
    def amount_display(self, obj):
        """Display amount with currency."""
        return f"{obj.amount} {obj.currency}"
    amount_display.short_description = 'Amount'
    
    def status_display(self, obj):
        """Display status with color."""
        colors = {
            'pending': 'orange',
            'completed': 'green',
            'failed': 'red',
            'refunded': 'blue',
            'cancelled': 'gray',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            colors.get(obj.status, 'black'),
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    actions = ['mark_as_completed']
    
    def mark_as_completed(self, request, queryset):
        """Mark selected payments as completed."""
        count = 0
        for payment in queryset:
            if payment.status != 'completed':
                payment.mark_as_completed()
                count += 1
        self.message_user(request, f'{count} payment(s) marked as completed.')
    mark_as_completed.short_description = 'Mark selected as completed'


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    """Admin interface for Event Registrations."""
    
    list_display = [
        'registration_number',
        'event_name',
        'event_type',
        'user_link',
        'tickets_display',
        'total_display',
        'status_display',
        'attended_display',
        'event_date',
    ]
    list_filter = [
        'status',
        'event_type',
        'payment_method',
        'is_attended',
        'event_date',
        'created_at',
    ]
    search_fields = [
        'registration_number',
        'event_name',
        'user__email',
        'user__first_name',
        'user__last_name',
        'contact_name',
        'contact_email',
    ]
    readonly_fields = [
        'id',
        'registration_number',
        'total_amount',
        'is_attended',
        'attended_at',
        'completed_at',
        'cancelled_at',
        'created_at',
        'updated_at',
    ]
    fieldsets = (
        ('Registration Information', {
            'fields': (
                'id',
                'registration_number',
                'status',
                'user',
                'created_by',
            )
        }),
        ('Event Details', {
            'fields': (
                'event_type',
                'event_name',
                'event_date',
                'event_location',
                'event_description',
            )
        }),
        ('Ticket Information', {
            'fields': (
                'ticket_type',
                'number_of_tickets',
                'price_per_ticket',
                'total_amount',
                'currency',
            )
        }),
        ('Payment Details', {
            'fields': (
                'payment_method',
                'payment_id',
            )
        }),
        ('Attendance', {
            'fields': (
                'is_attended',
                'attended_at',
            )
        }),
        ('Contact Information', {
            'fields': (
                'contact_name',
                'contact_email',
                'contact_phone',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'completed_at',
                'cancelled_at',
            )
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    def user_link(self, obj):
        """Link to user."""
        if obj.user:
            return format_html(
                '<a href="/admin/api/customuser/{}/change/">{}</a>',
                obj.user.id,
                obj.user.email
            )
        return '-'
    user_link.short_description = 'User'
    
    def tickets_display(self, obj):
        """Display number of tickets."""
        return f"{obj.number_of_tickets} × {obj.ticket_type}"
    tickets_display.short_description = 'Tickets'
    
    def total_display(self, obj):
        """Display total amount."""
        return f"{obj.total_amount} {obj.currency}"
    total_display.short_description = 'Total'
    
    def status_display(self, obj):
        """Display status with color."""
        colors = {
            'pending': 'orange',
            'completed': 'green',
            'failed': 'red',
            'refunded': 'blue',
            'cancelled': 'gray',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            colors.get(obj.status, 'black'),
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def attended_display(self, obj):
        """Display attendance status."""
        if obj.is_attended:
            return format_html('<span style="color: green;">✓ Attended</span>')
        return format_html('<span style="color: gray;">○ Not attended</span>')
    attended_display.short_description = 'Attendance'
    
    actions = ['mark_as_completed', 'mark_attendance']
    
    def mark_as_completed(self, request, queryset):
        """Mark selected registrations as completed."""
        count = 0
        for registration in queryset:
            if registration.status != 'completed':
                registration.mark_as_completed()
                count += 1
        self.message_user(request, f'{count} registration(s) marked as completed.')
    mark_as_completed.short_description = 'Mark selected as completed'
    
    def mark_attendance(self, request, queryset):
        """Mark selected registrations as attended."""
        count = 0
        for registration in queryset:
            if not registration.is_attended:
                registration.mark_attendance()
                count += 1
        self.message_user(request, f'{count} attendance(s) marked.')
    mark_attendance.short_description = 'Mark selected as attended'

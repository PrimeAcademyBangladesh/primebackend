"""Admin configuration for Order, OrderItem, and Enrollment models."""

from django.contrib import admin
from django.db.models import Count, Sum
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from api.admin.base_admin import BaseModelAdmin
from api.models.models_order import (Enrollment, Order, OrderInstallment,
                                     OrderItem)

# ========== Inline for OrderInstallments ==========

class OrderInstallmentInline(admin.TabularInline):
    """Inline for order installment payments."""
    model = OrderInstallment
    extra = 0
    fields = ['installment_number', 'amount', 'due_date', 'status', 'paid_at', 'payment_id', 'payment_method']
    readonly_fields = ['paid_at']
    ordering = ['installment_number']
    
    def has_add_permission(self, request, obj=None):
        """Only allow adding installments if order is_installment."""
        if obj and not obj.is_installment:
            return False
        return super().has_add_permission(request, obj)


# ========== Inline for OrderItems ==========

class OrderItemInline(admin.TabularInline):
    """Inline for order items."""
    model = OrderItem
    extra = 0
    fields = ['course', 'course_title', 'price', 'discount', 'currency', 'total_display']
    readonly_fields = ['course_title', 'total_display', 'created_at']
    
    def total_display(self, obj):
        """Display total for this item."""
        if obj.pk:
            total = obj.get_total()
            return format_html(
                '<strong>{} {}</strong>',
                obj.currency,
                total
            )
        return '-'
    total_display.short_description = 'Total'


# ========== Order Admin ==========

@admin.register(Order)
class OrderAdmin(BaseModelAdmin):
    """Admin for Order model."""
    
    list_display = [
        'order_number',
        'user_display',
        'order_type_display',
        'status_display',
        'total_amount_display',
        'payment_method',
        'items_count',
        'created_at',
    ]
    
    list_filter = [
        'status',
        'is_custom_payment',
        'is_installment',
        'payment_method',
        'currency',
        'created_at',
        'completed_at',
    ]
    
    search_fields = [
        'order_number',
        'user__email',
        'user__first_name',
        'user__last_name',
        'billing_email',
        'billing_name',
        'payment_id',
    ]
    
    readonly_fields = [
        'order_number',
        'created_at',
        'updated_at',
        'completed_at',
        'cancelled_at',
        'total_items_display',
        'status_badge',
    ]
    
    fieldsets = (
        ('Order Information', {
            'fields': (
                'order_number',
                'user',
                'status',
                'status_badge',
            )
        }),
        ('Pricing', {
            'fields': (
                'subtotal',
                'discount_amount',
                'tax_amount',
                'total_amount',
                'currency',
            )
        }),
        ('Coupon', {
            'fields': (
                'coupon',
                'coupon_code',
            ),
            'classes': ('collapse',)
        }),
        ('Payment Information', {
            'fields': (
                'payment_method',
                'payment_id',
                'payment_status',
            )
        }),
        ('Billing Information', {
            'fields': (
                'billing_name',
                'billing_email',
                'billing_phone',
                'billing_address',
            )
        }),
        ('Custom Payment', {
            'fields': (
                'is_custom_payment',
                'custom_payment_description',
            ),
            'classes': ('collapse',),
            'description': 'Enable for: 1) Non-course payments (workshops, consultations) OR 2) Manual course enrollment with custom pricing (scholarships, free access, special discounts)'
        }),
        ('Installment Payment', {
            'fields': (
                'is_installment',
                'installment_plan',
                'installments_paid',
                'next_installment_date',
            ),
            'classes': ('collapse',)
        }),
        ('Admin Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'completed_at',
                'cancelled_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [OrderItemInline, OrderInstallmentInline]
    
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    actions = ['mark_as_completed', 'mark_as_cancelled']
    
    def user_display(self, obj):
        """Display user with link."""
        if obj.user:
            url = reverse('admin:api_customuser_change', args=[obj.user.pk])
            name = obj.user.get_full_name or obj.user.email
            return format_html('<a href="{}">{}</a>', url, name)
        return '-'
    user_display.short_description = 'User'
    user_display.admin_order_field = 'user__email'
    
    def order_type_display(self, obj):
        """Display order type with icon."""
        if obj.is_custom_payment:
            items_count = obj.get_total_items()
            if items_count > 0:
                return format_html(
                    '<span style="color: #9c27b0;" title="{}">💰 Custom + {} Course(s)</span>',
                    obj.custom_payment_description[:50] if obj.custom_payment_description else 'Manual Enrollment',
                    items_count
                )
            else:
                return format_html(
                    '<span style="color: #9c27b0;" title="{}">💰 Custom</span>',
                    obj.custom_payment_description[:50] if obj.custom_payment_description else 'Custom Payment'
                )
        elif obj.is_installment:
            return format_html(
                '<span style="color: #ff9800;" title="Installment: {}/{}">📅 Installment</span>',
                obj.installments_paid,
                obj.installment_plan
            )
        else:
            return format_html('<span style="color: #2196f3;">🎓 Course</span>')
    order_type_display.short_description = 'Type'
    
    def status_display(self, obj):
        """Display status with color coding."""
        colors = {
            'pending': '#ff9800',      # Orange
            'processing': '#2196f3',   # Blue
            'completed': '#4caf50',    # Green
            'failed': '#f44336',       # Red
            'refunded': '#9c27b0',     # Purple
            'cancelled': '#757575',    # Gray
        }
        color = colors.get(obj.status, '#000')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'
    
    def status_badge(self, obj):
        """Display detailed status badge."""
        if not obj.pk:
            return '-'
        
        colors = {
            'pending': '#ff9800',
            'processing': '#2196f3',
            'completed': '#4caf50',
            'failed': '#f44336',
            'refunded': '#9c27b0',
            'cancelled': '#757575',
        }
        color = colors.get(obj.status, '#000')
        
        badge = f'<div style="padding: 10px; background: {color}20; border-left: 4px solid {color};">'
        badge += f'<strong style="color: {color};">Status: {obj.get_status_display()}</strong><br>'
        badge += f'Created: {obj.created_at.strftime("%Y-%m-%d %H:%M")}<br>'
        
        if obj.completed_at:
            badge += f'Completed: {obj.completed_at.strftime("%Y-%m-%d %H:%M")}<br>'
        if obj.cancelled_at:
            badge += f'Cancelled: {obj.cancelled_at.strftime("%Y-%m-%d %H:%M")}<br>'
        
        badge += f'Total Items: {obj.get_total_items()}'
        badge += '</div>'
        
        return format_html(badge)
    status_badge.short_description = 'Status Details'
    
    def total_amount_display(self, obj):
        """Display total amount with currency."""
        return f"{obj.currency} {obj.total_amount}"
    total_amount_display.short_description = 'Total'
    total_amount_display.admin_order_field = 'total_amount'
    
    def items_count(self, obj):
        """Display number of items."""
        return obj.get_total_items()
    items_count.short_description = 'Items'
    
    def total_items_display(self, obj):
        """Display total items count."""
        if obj.pk:
            return obj.get_total_items()
        return 0
    total_items_display.short_description = 'Total Items'
    
    def mark_as_completed(self, request, queryset):
        """Mark selected orders as completed and create enrollments."""
        count = 0
        for order in queryset:
            if order.can_be_cancelled():  # Only complete pending/processing orders
                order.mark_as_completed()
                count += 1
        
        self.message_user(
            request,
            f'{count} order(s) marked as completed and enrollments created.'
        )
    mark_as_completed.short_description = 'Mark selected orders as completed'
    
    def mark_as_cancelled(self, request, queryset):
        """Mark selected orders as cancelled."""
        count = 0
        for order in queryset:
            if order.can_be_cancelled():
                order.status = 'cancelled'
                order.cancelled_at = timezone.now()
                order.save()
                count += 1
        
        self.message_user(
            request,
            f'{count} order(s) marked as cancelled.'
        )
    mark_as_cancelled.short_description = 'Mark selected orders as cancelled'


# ========== OrderItem Admin ==========

@admin.register(OrderItem)
class OrderItemAdmin(BaseModelAdmin):
    """Admin for OrderItem model."""
    
    list_display = [
        'id',
        'order_display',
        'course_display',
        'price_display',
        'discount',
        'total_display',
        'created_at',
    ]
    
    list_filter = [
        'currency',
        'created_at',
    ]
    
    search_fields = [
        'order__order_number',
        'course__title',
        'course_title',
    ]
    
    readonly_fields = [
        'course_title',
        'created_at',
        'updated_at',
        'total_display',
    ]
    
    fieldsets = (
        ('Order Item Information', {
            'fields': (
                'order',
                'course',
                'course_title',
            )
        }),
        ('Pricing', {
            'fields': (
                'price',
                'discount',
                'currency',
                'total_display',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    def order_display(self, obj):
        """Display order with link."""
        url = reverse('admin:api_order_change', args=[obj.order.pk])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
    order_display.short_description = 'Order'
    order_display.admin_order_field = 'order__order_number'
    
    def course_display(self, obj):
        """Display course with link."""
        if obj.course:
            url = reverse('admin:api_course_change', args=[obj.course.pk])
            return format_html('<a href="{}">{}</a>', url, obj.course_title or obj.course.title)
        return obj.course_title or '-'
    course_display.short_description = 'Course'
    course_display.admin_order_field = 'course__title'
    
    def price_display(self, obj):
        """Display price with currency."""
        return f"{obj.currency} {obj.price}"
    price_display.short_description = 'Price'
    price_display.admin_order_field = 'price'
    
    def total_display(self, obj):
        """Display total."""
        if obj.pk:
            total = obj.get_total()
            return format_html(
                '<strong>{} {}</strong>',
                obj.currency,
                total
            )
        return '-'
    total_display.short_description = 'Total'


# ========== Enrollment Admin ==========

@admin.register(Enrollment)
class EnrollmentAdmin(BaseModelAdmin):
    """Admin for Enrollment model."""
    
    list_display = [
        'id',
        'user_display',
        'course_display',
        'progress_display',
        'status_display',
        'created_at',
        'last_accessed',
    ]
    
    list_filter = [
        'is_active',
        'certificate_issued',
        'created_at',
        'completed_at',
    ]
    
    search_fields = [
        'user__email',
        'user__first_name',
        'user__last_name',
        'course__title',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'progress_badge',
        'enrollment_duration',
    ]
    
    fieldsets = (
        ('Enrollment Information', {
            'fields': (
                'user',
                'course',
                'order',
                'is_active',
            )
        }),
        ('Progress', {
            'fields': (
                'progress_percentage',
                'progress_badge',
                'completed_at',
                'certificate_issued',
            )
        }),
        ('Activity', {
            'fields': (
                'last_accessed',
                'enrollment_duration',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    actions = ['mark_as_completed', 'issue_certificate', 'deactivate_enrollment']
    
    def user_display(self, obj):
        """Display user with link."""
        if obj.user:
            url = reverse('admin:api_customuser_change', args=[obj.user.pk])
            name = obj.user.get_full_name or obj.user.email
            return format_html('<a href="{}">{}</a>', url, name)
        return '-'
    user_display.short_description = 'Student'
    user_display.admin_order_field = 'user__email'
    
    def course_display(self, obj):
        """Display course with link."""
        if obj.course:
            url = reverse('admin:api_course_change', args=[obj.course.pk])
            return format_html('<a href="{}">{}</a>', url, obj.course.title)
        return '-'
    course_display.short_description = 'Course'
    course_display.admin_order_field = 'course__title'
    
    def progress_display(self, obj):
        """Display progress with visual indicator."""
        percentage = float(obj.progress_percentage)
        
        # Color based on progress
        if percentage == 100:
            color = '#4caf50'  # Green
        elif percentage >= 50:
            color = '#ff9800'  # Orange
        else:
            color = '#2196f3'  # Blue
        
        # Pre-format the displayed percentage string to avoid applying
        # numeric format codes to Django SafeString (which raises ValueError).
        percentage_text = f"{percentage:.0f}%"
        return format_html(
            '<div style="width: 100px; background: #eee; border-radius: 4px; overflow: hidden;">'
            '<div style="width: {}%; background: {}; color: white; text-align: center; '
            'padding: 2px 0; font-size: 11px; font-weight: bold;">{}</div></div>',
            percentage, color, percentage_text
        )
    progress_display.short_description = 'Progress'
    progress_display.admin_order_field = 'progress_percentage'
    
    def status_display(self, obj):
        """Display enrollment status."""
        if not obj.is_active:
            return format_html(
                '<span style="color: #f44336;">Inactive</span>'
            )
        elif obj.is_completed():
            return format_html(
                '<span style="color: #4caf50;">Completed</span>'
            )
        else:
            return format_html(
                '<span style="color: #2196f3;">Active</span>'
            )
    status_display.short_description = 'Status'
    
    def progress_badge(self, obj):
        """Display detailed progress badge."""
        if not obj.pk:
            return '-'
        
        percentage = float(obj.progress_percentage)
        
        if percentage == 100:
            color = '#4caf50'
            status = 'Completed'
        elif percentage >= 50:
            color = '#ff9800'
            status = 'In Progress'
        else:
            color = '#2196f3'
            status = 'Just Started'
        
        badge = f'<div style="padding: 10px; background: {color}20; border-left: 4px solid {color};">'
        badge += f'<strong style="color: {color};">Progress: {percentage:.1f}%</strong><br>'
        badge += f'Status: {status}<br>'
        
        if obj.completed_at:
            badge += f'Completed: {obj.completed_at.strftime("%Y-%m-%d")}<br>'
        
        if obj.certificate_issued:
            badge += '<span style="color: #4caf50;">🎓 Certificate Issued</span>'
        
        badge += '</div>'
        
        return format_html(badge)
    progress_badge.short_description = 'Progress Details'
    
    def enrollment_duration(self, obj):
        """Calculate and display enrollment duration."""
        if not obj.pk or not obj.created_at:
            return '-'
        
        now = timezone.now()
        delta = now - obj.created_at
        days = delta.days
        
        if days == 0:
            return 'Today'
        elif days == 1:
            return '1 day'
        elif days < 30:
            return f'{days} days'
        elif days < 365:
            months = days // 30
            return f'{months} month{"s" if months > 1 else ""}'
        else:
            years = days // 365
            return f'{years} year{"s" if years > 1 else ""}'
    enrollment_duration.short_description = 'Enrolled For'
    
    def mark_as_completed(self, request, queryset):
        """Mark selected enrollments as completed."""
        count = 0
        for enrollment in queryset:
            if not enrollment.is_completed():
                enrollment.mark_as_completed()
                count += 1
        
        self.message_user(
            request,
            f'{count} enrollment(s) marked as completed.'
        )
    mark_as_completed.short_description = 'Mark as completed (100%% progress)'
    
    def issue_certificate(self, request, queryset):
        """Issue certificates for selected enrollments."""
        count = queryset.filter(
            progress_percentage=100,
            certificate_issued=False
        ).update(certificate_issued=True)
        
        self.message_user(
            request,
            f'{count} certificate(s) issued.'
        )
    issue_certificate.short_description = 'Issue certificates'
    
    def deactivate_enrollment(self, request, queryset):
        """Deactivate selected enrollments."""
        count = queryset.update(is_active=False)
        
        self.message_user(
            request,
            f'{count} enrollment(s) deactivated.'
        )
    deactivate_enrollment.short_description = 'Deactivate enrollments'


# ========== OrderInstallment Admin ==========

@admin.register(OrderInstallment)
class OrderInstallmentAdmin(BaseModelAdmin):
    """Admin for Order Installment tracking."""
    
    list_display = [
        'id',
        'order_display',
        'installment_info',
        'amount',
        'due_date',
        'status_display',
        'paid_at',
    ]
    
    list_filter = [
        'status',
        'due_date',
        'created_at',
    ]
    
    search_fields = [
        'order__order_number',
        'order__user__email',
        'payment_id',
    ]
    
    readonly_fields = [
        'paid_at',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('Installment Information', {
            'fields': (
                'order',
                'installment_number',
                'amount',
                'due_date',
            )
        }),
        ('Payment Status', {
            'fields': (
                'status',
                'paid_at',
                'payment_id',
                'payment_method',
            )
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    ordering = ['order', 'installment_number']
    date_hierarchy = 'due_date'
    
    actions = ['mark_as_paid', 'check_overdue']
    
    def order_display(self, obj):
        """Display order with link."""
        url = reverse('admin:api_order_change', args=[obj.order.pk])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
    order_display.short_description = 'Order'
    order_display.admin_order_field = 'order__order_number'
    
    def installment_info(self, obj):
        """Display installment number info."""
        return format_html(
            '<strong>{} / {}</strong>',
            obj.installment_number,
            obj.order.installment_plan
        )
    installment_info.short_description = 'Installment'
    
    def status_display(self, obj):
        """Display status with color coding."""
        colors = {
            'pending': '#ff9800',   # Orange
            'paid': '#4caf50',      # Green
            'overdue': '#f44336',   # Red
            'failed': '#757575',    # Gray
        }
        color = colors.get(obj.status, '#000')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'
    
    def mark_as_paid(self, request, queryset):
        """Mark selected installments as paid."""
        count = 0
        for installment in queryset.filter(status__in=['pending', 'overdue']):
            installment.mark_as_paid()
            count += 1
        
        self.message_user(
            request,
            f'{count} installment(s) marked as paid and orders updated.'
        )
    mark_as_paid.short_description = 'Mark selected as paid'
    
    def check_overdue(self, request, queryset):
        """Check and update overdue status for installments."""
        count = 0
        for installment in queryset:
            if installment.check_overdue():
                count += 1
        
        self.message_user(
            request,
            f'{count} installment(s) marked as overdue.'
        )
    check_overdue.short_description = 'Check for overdue installments'

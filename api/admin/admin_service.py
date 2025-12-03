from django.contrib import admin
from django.utils.html import format_html

from api.admin.base_admin import BaseModelAdmin
from api.models.models_service import ContentSection, PageService


@admin.register(PageService)
class PageServiceAdmin(BaseModelAdmin):
    list_display = ("name", "slug", "is_active", "sections_count")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ['id', "sections_count"]
    
    def sections_count(self, obj):
        """Display the number of sections for this page"""
        return obj.content_sections.count()
    sections_count.short_description = "Sections Count"
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('content_sections')
    
    def has_module_permission(self, request):
        return False


@admin.register(ContentSection)
class ContentSectionAdmin(BaseModelAdmin):
    list_display = (
        "page",
        "section_type_display",
        "media_type_display",
        'position_choice',
        "title_preview",
        "content_preview",
        "order",
        "button_text",
        "media_preview",
        "is_active",
        "created_at",
    )
    
    list_display_links = ("page", "title_preview")
    list_editable = ("order", "is_active")
    # Add media_type and video_provider to filters
    list_filter = ("page", "section_type", "media_type", "video_provider", "position_choice", "is_active", "created_at")
    search_fields = ("title", "content", "page__name", "button_text", "video_url")
    ordering = ("page", "order", "section_type")
    readonly_fields = ("id", "video_id", "created_at", "updated_at", "image_display", "video_thumbnail_display", "section_type_display", "media_type_display_readonly")
    
    fieldsets = (
        ("Basic Information", {
            "fields": (
                "id",
                "page", 
                "section_type",
                "position_choice",
                "title", 
                "content",
            )
        }),
        ("Call to Action", {
            "fields": (
                "button_text",
                "button_link",
            )
        }),
        ("Media Type Selection", {
            "fields": (
                "media_type",
                "media_type_display_readonly",
            ),
            "description": "Choose between Image or Video. Icon sections can only use images."
        }),
        ("Image Media", {
            "fields": (
                "image",
                "image_display",
            ),
            "description": "Upload an image. Required when Media Type is 'Image'."
        }),
        ("Video Media", {
            "fields": (
                "video_provider",
                "video_url",
                "video_id",
                "video_thumbnail",
                "video_thumbnail_display",
            ),
            "description": "Video settings. Required when Media Type is 'Video' (Info sections only).",
            "classes": ("collapse",)
        }),
        ("Settings", {
            "fields": (
                "order",
                "is_active",
            )
        }),
        ("Timestamps", {
            "fields": (
                "created_at",
                "updated_at",
            ),
            "classes": ("collapse",) 
        }),
    )
    
    list_per_page = 20
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related("page")
    
    def section_type_display(self, obj):
        return obj.get_section_type_display()
    section_type_display.short_description = "Type"
    
    def media_type_display(self, obj):
        """Display media type with icon"""
        if obj.media_type == 'image':
            return format_html('<span style="color: #2e7d32;">🖼️ Image</span>')
        elif obj.media_type == 'video':
            provider = obj.get_video_provider_display() if obj.video_provider else 'Video'
            return format_html('<span style="color: #1976d2;">🎥 {}</span>', provider)
        return obj.get_media_type_display()
    media_type_display.short_description = "Media"
    
    def media_type_display_readonly(self, obj):
        """Read-only display of media type"""
        return obj.get_media_type_display()
    media_type_display_readonly.short_description = "Current Media Type"
    
    def title_preview(self, obj):
        return obj.title[:50] + "..." if len(obj.title) > 50 else obj.title
    title_preview.short_description = "Title"
    
    def content_preview(self, obj):
        return obj.content[:70] + "..." if len(obj.content) > 70 else obj.content
    content_preview.short_description = "Content"
    
    def media_preview(self, obj):
        """Show preview of either image or video thumbnail in list view"""
        if obj.media_type == 'image' and obj.image:
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 50px;" />', 
                obj.image.url
            )
        elif obj.media_type == 'video' and obj.video_thumbnail:
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 50px;" title="{} video" />', 
                obj.video_thumbnail.url,
                obj.get_video_provider_display() if obj.video_provider else 'Video'
            )
        return "-"
    media_preview.short_description = "Preview"
    
    def image_display(self, obj):
        """Large image preview in detail view"""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 200px; max-width: 200px;" />', 
                obj.image.url
            )
        return "No image uploaded"
    image_display.short_description = "Current Image"
    
    def video_thumbnail_display(self, obj):
        """Large video thumbnail preview in detail view"""
        if obj.video_thumbnail:
            video_info = ""
            if obj.video_provider and obj.video_id:
                video_info = format_html(
                    '<br><strong>Provider:</strong> {}<br><strong>Video ID:</strong> {}',
                    obj.get_video_provider_display(),
                    obj.video_id
                )
            return format_html(
                '<img src="{}" style="max-height: 200px; max-width: 300px;" />{}<br><a href="{}" target="_blank">View Video URL</a>',
                obj.video_thumbnail.url,
                video_info,
                obj.video_url if obj.video_url else '#'
            )
        return "No video thumbnail uploaded"
    video_thumbnail_display.short_description = "Current Video Thumbnail"

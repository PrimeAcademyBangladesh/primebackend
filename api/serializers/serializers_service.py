from rest_framework import serializers

from api.models.models_service import ContentSection, PageService


class PageServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PageService
        fields = [
            "id",
            "name",
            'slug',
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", 'slug', 'is_active', "created_at", "updated_at"]


class ContentSectionListSerializer(serializers.ModelSerializer):
    """Serializer for listing content sections (GET) - shows all available fields"""
    
    page_details = PageServiceSerializer(source='page', read_only=True)
    page = serializers.SlugRelatedField(
        slug_field='name',
        queryset=PageService.objects.all(),
        help_text="Select a page by name"
    )
    
    # Human readable displays
    position_display = serializers.CharField(
        source='get_position_choice_display', read_only=True
    )
    section_type_display = serializers.CharField(
        source='get_section_type_display', read_only=True
    )
    media_type_display = serializers.CharField(
        source='get_media_type_display', read_only=True
    )
    video_provider_display = serializers.CharField(
        source='get_video_provider_display', read_only=True
    )
    # Explicit boolean fields for properties so schema generators infer correct types
    is_info_section = serializers.BooleanField(read_only=True)
    is_icon_section = serializers.BooleanField(read_only=True)
    has_video = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = ContentSection
        fields = [
            "id",
            "page",
            "page_details",
            "section_type",
            "section_type_display",
            "position_choice",
            "position_display",
            "media_type",
            "media_type_display",
            "title",
            "content",
            "button_text",
            "button_link",
            "image",
            "video_provider",
            "video_provider_display",
            "video_url",
            "video_id",
            "video_thumbnail",
            "order",
            "is_active",
            "is_info_section",
            "is_icon_section",
            "has_video",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "page_details",
            "section_type_display",
            "position_display",
            "media_type_display",
            "video_provider_display",
            "video_id",
            "is_info_section",
            "is_icon_section",
            "has_video",
            "created_at",
            "updated_at",
        ]
    # Convert any HTML content urls to absolute URLs when request is present
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Request may be None; absolutize_media_urls will use SITE_BASE_URL
        request = self.context.get('request') if hasattr(self, 'context') else None
        if rep.get('content'):
            from api.utils.ckeditor_paths import absolutize_media_urls
            try:
                rep['content'] = absolutize_media_urls(rep['content'], request)
            except Exception:
                pass
        return rep


class ContentSectionCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating content sections (POST/PUT/PATCH) - only writable fields"""
    
    page = serializers.SlugRelatedField(
        slug_field='name',
        queryset=PageService.objects.all(),
        help_text="Select a page by name"
    )
    
    class Meta:
        model = ContentSection
        fields = [
            "page",
            "section_type",
            "position_choice",
            "media_type",
            "title",
            "content",
            "button_text",
            "button_link",
            "image",
            "video_provider",
            "video_url",
            "video_thumbnail",
            "order",
            "is_active",
        ]
    
    def validate_button_link(self, value):
        """Validate button_link field if button_text is provided"""
        if self.initial_data.get('button_text') and not value:
            raise serializers.ValidationError(
                "Button link is required when button text is provided."
            )
        return value
        
    def validate_order(self, value):
        """Ensure order is not negative"""
        if value < 0:
            raise serializers.ValidationError("Order must be a positive integer.")
        return value
    
    def validate_video_url(self, value):
        """Validate video URL format"""
        if not value:
            return value
        
        video_provider = self.initial_data.get('video_provider')
        
        if not video_provider:
            raise serializers.ValidationError('Video provider must be specified.')
        
        import re
        
        if video_provider == 'youtube':
            youtube_patterns = [
                r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
            ]
            for pattern in youtube_patterns:
                if re.search(pattern, value):
                    return value
            raise serializers.ValidationError('Invalid YouTube URL format.')
        
        elif video_provider == 'vimeo':
            vimeo_patterns = [
                r'vimeo\.com\/(\d+)',
                r'player\.vimeo\.com\/video\/(\d+)',
            ]
            for pattern in vimeo_patterns:
                if re.search(pattern, value):
                    return value
            raise serializers.ValidationError('Invalid Vimeo URL format.')
        
        return value

    def validate(self, data):
        """Additional validation based on section type and media type"""
        # Get values from data or existing instance
        section_type = data.get('section_type', self.instance.section_type if self.instance else 'info')
        media_type = data.get('media_type', self.instance.media_type if self.instance else 'image')
        content = data.get('content', '')
        
        # Icon sections can only use images
        if section_type == 'icon' and media_type == 'video':
            raise serializers.ValidationError({
                'media_type': 'Icon sections can only use images.'
            })
        
        # Validate content length for icon sections
        if section_type == 'icon' and content and len(content) > 500:
            raise serializers.ValidationError({
                'content': 'Icon sections should have concise content (max 500 characters).'
            })
        
        # Validate video fields when media_type is 'video'
        if media_type == 'video' and section_type == 'info':
            if not data.get('video_url'):
                raise serializers.ValidationError({
                    'video_url': 'Video URL is required when media type is video.'
                })
            if not data.get('video_provider'):
                raise serializers.ValidationError({
                    'video_provider': 'Video provider is required when media type is video.'
                })
            # Only require thumbnail for new instances
            if not data.get('video_thumbnail') and not self.instance:
                raise serializers.ValidationError({
                    'video_thumbnail': 'Video thumbnail is required when media type is video.'
                })
        
        # Validate image field when media_type is 'image'
        if media_type == 'image':
            # Only require image for new instances
            if not data.get('image') and not self.instance:
                raise serializers.ValidationError({
                    'image': 'Image is required when media type is image.'
                })
            
        return data


class PageServiceWithSectionsSerializer(serializers.ModelSerializer):
    """Page with all its content sections"""
    
    content_sections = ContentSectionListSerializer(many=True, read_only=True)
    total_sections = serializers.SerializerMethodField()
    active_sections = serializers.SerializerMethodField()
    
    class Meta:
        model = PageService
        fields = [
            'id',
            'name',
            'slug',
            'is_active',
            'total_sections',
            'active_sections',
            'content_sections',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'slug', 'total_sections', 'active_sections', 'created_at', 'updated_at']
    
    def get_total_sections(self, obj):
        return obj.content_sections.count()
    
    def get_active_sections(self, obj):
        return obj.content_sections.filter(is_active=True).count()


# Backward compatibility - keep your original serializer name
ContentSectionSerializer = ContentSectionListSerializer
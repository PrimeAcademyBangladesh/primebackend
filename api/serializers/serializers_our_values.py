from rest_framework import serializers

from api.models.models_our_values import ValueTab, ValueTabContent, ValueTabSection
from api.serializers.serializers_service import PageServiceSerializer


class ValueTabContentListSerializer(serializers.ModelSerializer):
    """Serializer for value tab content (GET) - shows all fields"""

    media_type_display = serializers.CharField(source="get_media_type_display", read_only=True)
    video_provider_display = serializers.CharField(source="get_video_provider_display", read_only=True)

    class Meta:
        model = ValueTabContent
        fields = [
            "id",
            "media_type",
            "media_type_display",
            "image",
            "video_provider",
            "video_provider_display",
            "video_url",
            "video_id",
            "video_thumbnail",
            "title",
            "description",
            "button_text",
            "button_url",
            "has_video",
            "has_button",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "media_type_display",
            "video_provider_display",
            "video_id",
            "has_video",
            "has_button",
            "created_at",
            "updated_at",
        ]


class ValueTabContentCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for value tab content (POST/PUT/PATCH) - only writable fields"""

    class Meta:
        model = ValueTabContent
        fields = [
            "value_tab",
            "media_type",
            "image",
            "video_provider",
            "video_url",
            "video_thumbnail",
            "title",
            "description",
            "button_text",
            "button_url",
            "is_active",
        ]

    def validate_video_url(self, value):
        """Validate video URL format"""
        if not value:
            return value

        video_provider = self.initial_data.get("video_provider")
        if not video_provider:
            raise serializers.ValidationError("Video provider must be specified.")

        import re

        if video_provider == "youtube":
            youtube_patterns = [
                r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})",
            ]
            for pattern in youtube_patterns:
                if re.search(pattern, value):
                    return value
            raise serializers.ValidationError("Invalid YouTube URL format.")

        elif video_provider == "vimeo":
            vimeo_patterns = [
                r"vimeo\.com\/(\d+)",
                r"player\.vimeo\.com\/video\/(\d+)",
            ]
            for pattern in vimeo_patterns:
                if re.search(pattern, value):
                    return value
            raise serializers.ValidationError("Invalid Vimeo URL format.")

        return value

    def validate(self, data):
        """Validate based on media type"""
        media_type = data.get("media_type", self.instance.media_type if self.instance else "image")

        if media_type == "video":
            if not data.get("video_url"):
                raise serializers.ValidationError({"video_url": "Video URL is required when media type is video."})
            if not data.get("video_provider"):
                raise serializers.ValidationError({"video_provider": "Video provider is required."})
            if not data.get("video_thumbnail") and not self.instance:
                raise serializers.ValidationError({"video_thumbnail": "Video thumbnail is required."})

        if media_type == "image" and not data.get("image") and not self.instance:
            raise serializers.ValidationError({"image": "Image is required when media type is image."})

        if data.get("button_text") and not data.get("button_url"):
            raise serializers.ValidationError({"button_url": "Button URL is required when button text is provided."})

        return data


class ValueTabListSerializer(serializers.ModelSerializer):
    """Serializer for value tabs with content"""

    content = ValueTabContentListSerializer(read_only=True)

    class Meta:
        model = ValueTab
        fields = [
            "id",
            "title",
            "slug",
            "order",
            "is_active",
            "content",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class ValueTabCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating value tabs"""

    class Meta:
        model = ValueTab
        fields = [
            "value_section",
            "title",
            "order",
            "is_active",
        ]


class ValueTabSectionListSerializer(serializers.ModelSerializer):
    """Serializer for value tab sections with all tabs"""

    value_tabs = ValueTabListSerializer(many=True, read_only=True)
    page_details = PageServiceSerializer(source="page", read_only=True)
    total_tabs = serializers.SerializerMethodField()
    active_tabs = serializers.SerializerMethodField()

    class Meta:
        model = ValueTabSection
        fields = [
            "id",
            "title",
            "slug",
            "subtitle",
            "page",
            "page_details",
            "order",
            "is_active",
            "total_tabs",
            "active_tabs",
            "value_tabs",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "page_details", "total_tabs", "active_tabs", "created_at", "updated_at"]

    def get_total_tabs(self, obj):
        return obj.value_tabs.count()

    def get_active_tabs(self, obj):
        return obj.value_tabs.filter(is_active=True).count()


class ValueTabSectionCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating value tab sections"""

    class Meta:
        model = ValueTabSection
        fields = [
            "title",
            "subtitle",
            "page",
            "order",
            "is_active",
        ]

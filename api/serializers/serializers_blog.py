from rest_framework import serializers

from api.models.models_blog import Blog, BlogCategory
from api.serializers.serializers_helpers import HTMLFieldsMixin


class BlogCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogCategory
        fields = ["id", "name", "slug", "is_active"]
        read_only_fields = ["id", "slug"]


class BlogSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    # Accept category as a primary key on write, but return nested category on read
    category = serializers.PrimaryKeyRelatedField(queryset=BlogCategory.objects.all())
    html_fields = ["content"]

    class Meta:
        model = Blog
        fields = [
            "id",
            "title",
            "slug",
            "excerpt",
            "content",
            "featured_image",
            "category",
            "status",
            "published_at",
            "show_in_home_latest",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    def to_representation(self, instance):
        """Return nested category for read operations while keeping PK input for writes."""
        representation = super().to_representation(instance)
        try:
            representation["category"] = BlogCategorySerializer(instance.category).data if instance.category else None
        except Exception:
            pass  # Fallback to default representation
        return representation

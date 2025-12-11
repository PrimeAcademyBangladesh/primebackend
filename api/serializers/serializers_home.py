from django.conf import settings
from rest_framework import serializers

from api.models.models_home import Brand, HeroSection, HeroSlideText


class HeroSlideTextSerializer(serializers.ModelSerializer):
    """Serializer for HeroSlideText objects."""

    class Meta:
        model = HeroSlideText
        fields = ["id", "text", "order"]
        read_only_fields = ["id"]


class HeroSectionSerializer(serializers.ModelSerializer):
    """Serializer for HeroSection with nested slides."""
    slides = HeroSlideTextSerializer(many=True)

    class Meta:
        model = HeroSection
        fields = [
            "id",
            "page_name",
            "title",
            "description",
            "button1_text",
            "button1_url",
            "button2_text",
            "button2_url",
            "banner_image",
            "is_active",
            "slides",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_banner_image(self, obj):
        if obj.banner_image:
            url = obj.banner_image.url
            site_base = getattr(settings, "SITE_BASE_URL", None)
            if site_base:
                return site_base.rstrip("/") + url
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(url)
            return url
        return None

    def create(self, validated_data):
        slides_data = validated_data.pop("slides", [])
        hero = HeroSection.objects.create(**validated_data)
        for slide in slides_data:
            HeroSlideText.objects.create(hero_section=hero, **slide)
        return hero

    def update(self, instance, validated_data):
        slides_data = validated_data.pop("slides", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # If slides are included in update, replace existing slides
        if slides_data is not None:
            instance.slides.all().delete()
            for slide in slides_data:
                HeroSlideText.objects.create(hero_section=instance, **slide)
        return instance

    
#===============================end hero section serializers===============================


#===============================start brand section serializers===============================


class BrandSerializer(serializers.ModelSerializer):
    """Serializer for Brand objects."""
    logo = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        fields = ["id", "logo",  "is_active"]
        read_only_fields = ["id"]

    def get_logo(self, obj):
        if obj.logo:
            url = obj.logo.url
            site_base = getattr(settings, "SITE_BASE_URL", None)
            if site_base:
                return site_base.rstrip("/") + url
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(url)
            return url
        return None



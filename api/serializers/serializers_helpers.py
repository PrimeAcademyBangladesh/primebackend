"""Serializer helpers and mixins for handling HTML fields."""

from typing import Iterable

from rest_framework import serializers


class HTMLFieldsMixin:
    """Mixin to automatically absolutize media URLs found in HTML fields.

    Subclasses should set `html_fields = ['content', 'answer', ...]`.
    """

    html_fields: Iterable[str] = []

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Request may be None in scripts/tests; absolutize_media_urls handles that
        request = self.context.get("request") if hasattr(self, "context") else None
        from api.utils.ckeditor_paths import absolutize_media_urls

        for field in getattr(self, "html_fields", ()):
            if field in rep and rep[field]:
                try:
                    rep[field] = absolutize_media_urls(rep[field], request)
                except Exception:
                    # Be defensive: don't break the whole serialization if replacement fails
                    pass

        return rep


class CourseDetailRequiredOnCreateMixin:
    """
    Enforces:
    - course_detail is REQUIRED on CREATE
    - course_detail is IMMUTABLE on UPDATE
    """

    course_detail_field_name = "course_detail"

    def validate(self, data):
        field = self.course_detail_field_name

        # CREATE → required
        if not self.instance and field not in data:
            raise serializers.ValidationError({field: "This field is required when creating."})

        # UPDATE → immutable
        if self.instance and field in data:
            raise serializers.ValidationError({field: f"{field} cannot be changed after creation."})

        return super().validate(data)


class ParentRequiredOnCreateMixin:
    parent_field_name = None

    def validate(self, data):
        data = super().validate(data)

        field = self.parent_field_name

        if not self.instance and field not in data:
            raise serializers.ValidationError({field: "This field is required."})

        if self.instance and field in data:
            raise serializers.ValidationError({field: f"{field} cannot be changed after creation."})

        return data

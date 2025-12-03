"""Serializer helpers and mixins for handling HTML fields."""

from typing import Iterable


class HTMLFieldsMixin:
    """Mixin to automatically absolutize media URLs found in HTML fields.

    Subclasses should set `html_fields = ['content', 'answer', ...]`.
    """

    html_fields: Iterable[str] = []

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Request may be None in scripts/tests; absolutize_media_urls handles that
        request = self.context.get('request') if hasattr(self, 'context') else None
        from api.utils.ckeditor_paths import absolutize_media_urls

        for field in getattr(self, 'html_fields', ()):
            if field in rep and rep[field]:
                try:
                    rep[field] = absolutize_media_urls(rep[field], request)
                except Exception:
                    # Be defensive: don't break the whole serialization if replacement fails
                    pass

        return rep

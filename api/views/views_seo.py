"""Views for PageSEO model - clean and minimal for SEO management"""

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny

from api import permissions
from api.models.models_seo import PageSEO
from api.permissions import IsStaff
from api.serializers.serializers_seo import (PageSEOCreateUpdateSerializer,
                                             PageSEOSerializer)
from api.utils.response_utils import api_response
from api.views.views_base import BaseAdminViewSet


@extend_schema(tags=["SEO Management"])
class PageSEOViewSet(BaseAdminViewSet):
    """
    Clean, minimal ViewSet for SEO management
    """

    queryset = PageSEO.objects.all()
    slug_field = "page_name"
    slug_lookup_only_actions = ["retrieve", "update", "partial_update", "destroy"]

    permission_classes = [IsStaff]

    def get_serializer_class(self):
        """Return serializer class based on action."""
        if self.action in ["create", "update", "partial_update"]:
            return PageSEOCreateUpdateSerializer
        return PageSEOSerializer

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
        url_path="by-page/(?P<page_name>[^/.]+)",
    )
    def by_page(self, request, page_name=None):
        """Public endpoint to get SEO data by page name"""
        try:
            # Only return active SEO entries for public
            seo_entry = PageSEO.objects.get(page_name=page_name, is_active=True)
            serializer = PageSEOSerializer(seo_entry)
            return api_response(True, "SEO data retrieved", serializer.data)
        except PageSEO.DoesNotExist:
            return api_response(False, "SEO data not found", {}, 404)

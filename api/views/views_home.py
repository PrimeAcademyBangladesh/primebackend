from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters

from api.models.models_home import Brand, HeroSection
from api.serializers.serializers_home import (BrandSerializer,
                                              HeroSectionSerializer)
from api.utils.pagination import StandardResultsSetPagination
from api.views.views_base import BaseAdminViewSet
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.parsers import MultiPartParser, FormParser
@extend_schema(
    tags=["Home"],
    summary="Hero Sections Resources",
    responses=HeroSectionSerializer,
    request=HeroSectionSerializer,
)
class HeroSectionViewSet(BaseAdminViewSet):
    """Hero Sections Management"""
    queryset = HeroSection.objects.all()
    serializer_class = HeroSectionSerializer
    parser_classes = (MultiPartParser, FormParser)
    # Admin-friendly listing: pagination, filtering, searching and ordering
    pagination_class = StandardResultsSetPagination
    permission_classes = (MultiPartParser, FormParser)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["is_active", "page_name"]
    search_fields = ["title"]
    ordering_fields = ["created_at", "order"]


@extend_schema(
    tags=["Home"],
    summary="Brand Sections Resources",
    responses=BrandSerializer,
    request=BrandSerializer,
)
class BrandViewSet(BaseAdminViewSet):
    """Brand Management"""
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    parser_classes = (MultiPartParser, FormParser)



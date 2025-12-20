from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny

from api.models.models_our_values import ValueTab, ValueTabContent, ValueTabSection
from api.serializers.serializers_our_values import (
    ValueTabContentCreateUpdateSerializer,
    ValueTabContentListSerializer,
    ValueTabCreateUpdateSerializer,
    ValueTabListSerializer,
    ValueTabSectionCreateUpdateSerializer,
    ValueTabSectionListSerializer,
)
from api.utils.response_utils import api_response
from api.views.views_base import BaseAdminViewSet


@extend_schema(
    tags=["Our Values"],
    summary="Value Tab Section Resources",
    responses=ValueTabSectionListSerializer,
    request=ValueTabSectionCreateUpdateSerializer,
)
class ValueTabSectionViewSet(BaseAdminViewSet):
    """API endpoint for managing value tab sections (like 'OUR VALUES')"""

    queryset = ValueTabSection.objects.select_related("page").prefetch_related("value_tabs__content").all()
    serializer_class = ValueTabSectionListSerializer
    lookup_field = "slug"

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return ValueTabSectionCreateUpdateSerializer
        return ValueTabSectionListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            instance = serializer.instance
            response_serializer = ValueTabSectionListSerializer(instance, context={"request": request})
            return api_response(True, "Value tab section created successfully", response_serializer.data, 201)
        return api_response(False, "Validation failed", serializer.errors, 400)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            self.perform_update(serializer)
            response_serializer = ValueTabSectionListSerializer(instance, context={"request": request})
            return api_response(True, "Value tab section updated successfully", response_serializer.data)
        return api_response(False, "Validation failed", serializer.errors, 400)

    @extend_schema(
        summary="Get value tab sections by page slug",
        description="Retrieve all active value tab sections (like 'OUR VALUES') for a specific page",
        responses=ValueTabSectionListSerializer,
    )
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
        url_path="by-page/(?P<page_slug>[^/.]+)",
    )
    def by_page(self, request, page_slug=None):
        """Get all value tab sections for a specific page"""
        value_sections = self.queryset.filter(page__slug=page_slug, page__is_active=True, is_active=True).order_by("order")

        if not value_sections.exists():
            return api_response(False, "No value tab sections found for this page", {}, 404)

        serializer = ValueTabSectionListSerializer(value_sections, many=True, context={"request": request})
        return api_response(True, "Value tab sections retrieved", serializer.data)


@extend_schema(
    tags=["Our Values"],
    summary="Value Tab Resources",
    responses=ValueTabListSerializer,
    request=ValueTabCreateUpdateSerializer,
)
class ValueTabViewSet(BaseAdminViewSet):
    """API endpoint for managing individual value tabs (like 'Be The Expert')"""

    queryset = ValueTab.objects.select_related("value_section").prefetch_related("content").all()
    serializer_class = ValueTabListSerializer

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return ValueTabCreateUpdateSerializer
        return ValueTabListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            instance = serializer.instance
            response_serializer = ValueTabListSerializer(instance, context={"request": request})
            return api_response(True, "Value tab created successfully", response_serializer.data, 201)
        return api_response(False, "Validation failed", serializer.errors, 400)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            self.perform_update(serializer)
            response_serializer = ValueTabListSerializer(instance, context={"request": request})
            return api_response(True, "Value tab updated successfully", response_serializer.data)
        return api_response(False, "Validation failed", serializer.errors, 400)


@extend_schema(
    tags=["Our Values"],
    summary="Value Tab Content Resources",
    responses=ValueTabContentListSerializer,
    request=ValueTabContentCreateUpdateSerializer,
)
class ValueTabContentViewSet(BaseAdminViewSet):
    """API endpoint for managing value tab content"""

    queryset = ValueTabContent.objects.select_related("value_tab__value_section").all()
    serializer_class = ValueTabContentListSerializer

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return ValueTabContentCreateUpdateSerializer
        return ValueTabContentListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            instance = serializer.instance
            response_serializer = ValueTabContentListSerializer(instance, context={"request": request})
            return api_response(True, "Value tab content created successfully", response_serializer.data, 201)
        return api_response(False, "Validation failed", serializer.errors, 400)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            self.perform_update(serializer)
            response_serializer = ValueTabContentListSerializer(instance, context={"request": request})
            return api_response(True, "Value tab content updated successfully", response_serializer.data)
        return api_response(False, "Validation failed", serializer.errors, 400)

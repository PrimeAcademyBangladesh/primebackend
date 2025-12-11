from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny

from api.models.models_service import ContentSection, PageService
from api.serializers.serializers_service import (
    ContentSectionCreateUpdateSerializer, ContentSectionListSerializer,
    PageServiceSerializer)
from api.utils.response_utils import api_response
from api.views.views_base import BaseAdminViewSet
from rest_framework.parsers import MultiPartParser, FormParser

@extend_schema(
    tags=["Services Sections"],
    summary="Service Page Resources",
    responses=PageServiceSerializer,
    request=PageServiceSerializer,
)
class PageServiceViewSet(BaseAdminViewSet):
    """API endpoint for managing PageService entries."""

    queryset = PageService.objects.all()
    serializer_class = PageServiceSerializer
    parser_classes = (MultiPartParser, FormParser)
    lookup_field = 'slug'


@extend_schema(
    tags=["Services Sections"],
    summary="Service Content Section Resources",
    responses=ContentSectionListSerializer,
    request=ContentSectionCreateUpdateSerializer,
)
class ContentSectionViewSet(BaseAdminViewSet):
    """API endpoint for managing ContentSection entries."""

    queryset = ContentSection.objects.select_related('page').all()
    serializer_class = ContentSectionListSerializer
    parser_classes = (MultiPartParser, FormParser)
    
    def get_serializer_class(self):
        """Use different serializers for read vs write operations"""
        if self.action in ['create', 'update', 'partial_update']:
            return ContentSectionCreateUpdateSerializer
        return ContentSectionListSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a new content section with proper response"""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            # Return with list serializer to show all fields
            instance = serializer.instance
            response_serializer = ContentSectionListSerializer(instance, context={'request': request})
            return api_response(True, "Content section created successfully", response_serializer.data, 201)
        return api_response(False, "Validation failed", serializer.errors, 400)
    
    def update(self, request, *args, **kwargs):
        """Update a content section with proper response"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            self.perform_update(serializer)
            # Return with list serializer to show all fields
            response_serializer = ContentSectionListSerializer(instance, context={'request': request})
            return api_response(True, "Content section updated successfully", response_serializer.data)
        return api_response(False, "Validation failed", serializer.errors, 400)
        
    @extend_schema(
        summary="Get content sections by page slug",
        description="Retrieve all active content sections for a specific page using its slug. Returns all section types (info, icon, cta) with image or video content.",
        responses=ContentSectionListSerializer,
    )
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
        url_path="by-page/(?P<slug>[^/.]+)",
    )
    def by_page(self, request, slug=None):
        """Public endpoint to get content sections by page slug"""
        try:
            page = PageService.objects.get(slug=slug, is_active=True)
            
            content_sections = ContentSection.objects.filter(
                page=page,
                is_active=True
            ).select_related('page').order_by('order')
            
            serializer = ContentSectionListSerializer(content_sections, many=True, context={'request': request})
            
            response_data = {
                'page': PageServiceSerializer(page).data,
                'sections': serializer.data,
                'count': content_sections.count()
            }
            
            return api_response(True, "Content sections retrieved", response_data)

        except PageService.DoesNotExist:
            return api_response(False, "Page not found", {}, 404)

    @extend_schema(
        summary="Get content sections by page slug and type",
        description="Retrieve all active content sections for a specific page and section type. Supports info (with image/video), icon, and cta sections.",
        responses=ContentSectionListSerializer,
        parameters=[
            OpenApiParameter(
                name='section_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='Section type (info, icon, or cta)',
                enum=['info', 'icon', 'cta']
            )
        ],
    )
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
        url_path="by-page/(?P<slug>[^/.]+)/(?P<section_type>[^/.]+)",
    )
    def by_page_and_type(self, request, slug=None, section_type=None):
        """Public endpoint to get content sections by page slug and section type"""
        try:
            valid_section_types = ['info', 'icon', 'cta']
            if section_type not in valid_section_types:
                return api_response(
                    False, 
                    f"Invalid section type. Must be one of: {', '.join(valid_section_types)}", 
                    {}, 
                    400
                )
            
            page = PageService.objects.get(slug=slug, is_active=True)
            
            content_sections = ContentSection.objects.filter(
                page=page,
                section_type=section_type,
                is_active=True
            ).select_related('page').order_by('order')
            
            serializer = ContentSectionListSerializer(content_sections, many=True, context={'request': request})
            
            response_data = {
                'page': PageServiceSerializer(page).data,
                'section_type': section_type,
                'sections': serializer.data,
                'count': content_sections.count()
            }
            
            return api_response(True, f"{section_type} sections retrieved", response_data)

        except PageService.DoesNotExist:
            return api_response(False, "Page not found", {}, 404)

    @extend_schema(
        summary="Get content sections by page slug, type and position",
        description="Retrieve all active content sections for a specific page, section type and position",
        responses=ContentSectionListSerializer,
        parameters=[
            OpenApiParameter(
                name='section_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='Section type (info, icon, or cta)',
                enum=['info', 'icon', 'cta']
            ),
            OpenApiParameter(
                name='position',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='Position on the page (top, middle, bottom)',
                enum=['top', 'middle', 'bottom']
            ),
        ],
    )
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
        url_path="by-page/(?P<slug>[^/.]+)/(?P<section_type>[^/.]+)/(?P<position>[^/.]+)",
    )
    def by_page_type_and_position(self, request, slug=None, section_type=None, position=None):
        """Public endpoint to get content sections by page slug, section type and position"""
        try:
            valid_section_types = ['info', 'icon', 'cta']
            valid_positions = ['top', 'middle', 'bottom']
            
            if section_type not in valid_section_types:
                return api_response(
                    False, 
                    f"Invalid section type. Must be one of: {', '.join(valid_section_types)}", 
                    {}, 
                    400
                )
            if position not in valid_positions:
                return api_response(
                    False, 
                    f"Invalid position. Must be one of: {', '.join(valid_positions)}", 
                    {}, 
                    400
                )

            page = PageService.objects.get(slug=slug, is_active=True)

            content_sections = ContentSection.objects.filter(
                page=page,
                section_type=section_type,
                position_choice=position,
                is_active=True
            ).select_related('page').order_by('order')

            serializer = ContentSectionListSerializer(content_sections, many=True, context={'request': request})

            response_data = {
                'page': PageServiceSerializer(page).data,
                'section_type': section_type,
                'position': position,
                'sections': serializer.data,
                'count': content_sections.count()
            }

            return api_response(True, f"{section_type} sections at {position} retrieved", response_data)

        except PageService.DoesNotExist:
            return api_response(False, "Page not found", {}, 404)
    
    @extend_schema(
        summary="Get content sections by page slug and media type",
        description="Retrieve all active content sections for a specific page filtered by media type (image or video)",
        responses=ContentSectionListSerializer,
        parameters=[
            OpenApiParameter(
                name='media_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='Media type (image or video)',
                enum=['image', 'video']
            )
        ],
    )
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
        url_path="by-page/(?P<slug>[^/.]+)/media/(?P<media_type>[^/.]+)",
    )
    def by_page_and_media(self, request, slug=None, media_type=None):
        """Public endpoint to get content sections by page slug and media type"""
        try:
            valid_media_types = ['image', 'video']
            if media_type not in valid_media_types:
                return api_response(
                    False, 
                    f"Invalid media type. Must be one of: {', '.join(valid_media_types)}", 
                    {}, 
                    400
                )
            
            page = PageService.objects.get(slug=slug, is_active=True)
            
            content_sections = ContentSection.objects.filter(
                page=page,
                media_type=media_type,
                is_active=True
            ).select_related('page').order_by('order')
            
            serializer = ContentSectionListSerializer(content_sections, many=True, context={'request': request})
            
            response_data = {
                'page': PageServiceSerializer(page).data,
                'media_type': media_type,
                'sections': serializer.data,
                'count': content_sections.count()
            }
            
            return api_response(True, f"Sections with {media_type} retrieved", response_data)

        except PageService.DoesNotExist:
            return api_response(False, "Page not found", {}, 404)
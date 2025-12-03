"""Blog API views."""

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, permissions, status
from rest_framework.decorators import action

from api.models.models_blog import Blog, BlogCategory
from api.permissions import IsStaff
from api.serializers.serializers_blog import (BlogCategorySerializer,
                                              BlogSerializer)
from api.utils.filters_utils import BlogFilter
from api.utils.pagination import StandardResultsSetPagination
from api.utils.response_utils import api_response
from api.utils.cache_utils import cache_response, CACHE_KEY_BLOG_LIST, CACHE_KEY_BLOG_DETAIL
from api.views.views_base import BaseAdminViewSet


@extend_schema_view(
    list=extend_schema(summary="List all active blog categories", responses={200: BlogCategorySerializer}, tags=['Blog Category']),
    retrieve=extend_schema(summary="Retrieve a blog category by slug", responses={200: BlogCategorySerializer}, tags=['Blog Category']),
    create=extend_schema(summary="Create a blog category", responses={201: BlogCategorySerializer}, tags=['Blog Category']),
    update=extend_schema(summary="Update a blog category", responses={200: BlogCategorySerializer}, tags=['Blog Category']),
    partial_update=extend_schema(summary="Partially update a blog category", responses={200: BlogCategorySerializer}, tags=['Blog Category']),
    destroy=extend_schema(summary="Delete a blog category", responses={204: None}, tags=['Blog Category']),
)
class BlogCategoryViewSet(BaseAdminViewSet):
    """CRUD for Blog Categories"""
    queryset = BlogCategory.objects.all()
    serializer_class = BlogCategorySerializer
    permission_classes = [IsStaff]
    slug_field = "slug"
    slug_lookup_only_actions = ["retrieve"]
    
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["is_active"]
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "created_at"]
    
    def get_permissions(self):
        """Override to allow staff to destroy blog categories."""
        # Allow staff for all actions including destroy
        from rest_framework import permissions
        if self.action in ["list", "retrieve", "latest", "featured", "home_categories", "megamenu_nav", "by_category"]:
            return [permissions.AllowAny()]
        return [IsStaff()]
   
    


@extend_schema_view(
    list=extend_schema(summary="List blogs", responses={200: BlogSerializer}, tags=["Blogs"]),
    create=extend_schema(summary="Create a blog", responses={201: BlogSerializer}, tags=['Blogs']),
    retrieve=extend_schema(summary="Retrieve blog by slug", responses={200: BlogSerializer}, tags=["Blogs"]),
    update=extend_schema(summary="Update blog by ID", responses={200: BlogSerializer}, tags=["Blogs"]),
    partial_update=extend_schema(summary="Partially update blog by ID", responses={200: BlogSerializer}, tags=["Blogs"]),
    destroy=extend_schema(summary="Delete blog by ID", responses={204: None}, tags=["Blogs"]),
    latest=extend_schema(summary="Latest blogs", responses={200: BlogSerializer}, tags=["Blogs"]),
)
class BlogViewSet(BaseAdminViewSet):
    """Blog CRUD: slug for retrieve, ID for update/delete."""
    queryset = Blog.objects.select_related("category").all()
    serializer_class = BlogSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsStaff]
    slug_field = "slug"
    slug_lookup_only_actions = ["retrieve"]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = BlogFilter
    search_fields = ["title", "excerpt", "content"]
    ordering_fields = ["title", "published_at", "updated_at"]
    ordering = ["-published_at"]

    @cache_response(timeout=600, key_prefix=CACHE_KEY_BLOG_LIST)
    def list(self, request, *args, **kwargs):
        """List blogs - cached for 10 minutes."""
        return super().list(request, *args, **kwargs)
    
    @cache_response(timeout=1800, key_prefix=CACHE_KEY_BLOG_DETAIL)
    def retrieve(self, request, *args, **kwargs):
        """Retrieve blog detail - cached for 30 minutes."""
        return super().retrieve(request, *args, **kwargs)

    @cache_response(timeout=900, key_prefix='blog_latest')
    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def latest(self, request):
        """Retrieve the latest 3 published blogs that are marked to show on home page."""
        qs = self.get_queryset().filter(show_in_home_latest=True).order_by("-published_at")[:3]
        serializer = self.get_serializer(qs, many=True)
        return api_response(True, "Latest blogs retrieved successfully", {"results": serializer.data}, status.HTTP_200_OK)


"""Import Libraries"""

from django.core.cache import cache
from django.db import IntegrityError

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound
from rest_framework.generics import CreateAPIView, DestroyAPIView, RetrieveAPIView, UpdateAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from api.models.models_footer import Footer
from api.permissions import IsAdmin
from api.serializers.serializers_footer import FooterSerializer
from api.utils.response_utils import api_response
from api.utils.resposne_return import APIResponseSerializer

CACHE_KEY = "footer_api_response"
CACHE_TIMEOUT = 60 * 30  # 30 minutes


@extend_schema(
    tags=["Footer"],
    methods=["GET"],
    summary="Get public footer",
    description="Retrieve the site's footer (public). Returns cached result when available.",
    responses=FooterSerializer,
    request=FooterSerializer,
)
class FooterPublicView(RetrieveAPIView):
    serializer_class = FooterSerializer
    permission_classes = [permissions.AllowAny]

    def get_object(self):
        cached = cache.get(CACHE_KEY)
        if cached:
            return cached

        footer = Footer.objects.prefetch_related("link_groups__links", "social_links").first()
        if footer:
            cache.set(CACHE_KEY, footer, CACHE_TIMEOUT)
        return footer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance:
            return api_response(False, "No footer found", {}, status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(instance, context={"request": request})
        return api_response(True, "Footer retrieved successfully", serializer.data, status.HTTP_200_OK)


@extend_schema_view(
    post=extend_schema(
        tags=["Footer"],
        summary="Create footer",
        description="Create the single footer instance. Only one footer is allowed.",
        request=FooterSerializer,
        responses=APIResponseSerializer,
    ),
    put=extend_schema(
        tags=["Footer"],
        summary="Update footer (Full)",
        description="Full update of the existing footer.",
        request=FooterSerializer,
        responses=APIResponseSerializer,
    ),
    patch=extend_schema(
        tags=["Footer"],
        summary="Update footer (Partial)",
        description="Partial update of the existing footer.",
        request=FooterSerializer,
        responses=APIResponseSerializer,
    ),
    delete=extend_schema(
        tags=["Footer"],
        summary="Delete footer",
        description="Delete the footer instance.",
        responses={204: OpenApiResponse(description="Footer deleted"), 404: OpenApiResponse(description="Footer not found")},
    ),
)
class FooterAdminView(CreateAPIView, UpdateAPIView, DestroyAPIView):
    serializer_class = FooterSerializer
    permission_classes = [IsAdmin]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_object(self):
        footer = Footer.objects.first()
        if not footer:
            raise NotFound("No footer exists yet")
        return footer

    def create(self, request, *args, **kwargs):
        if Footer.objects.exists():
            return api_response(
                False,
                "Footer already exists. Only one is allowed.",
                {},
                status.HTTP_400_BAD_REQUEST,
            )
        try:
            response = super().create(request, *args, **kwargs)
            cache.delete(CACHE_KEY)
            return api_response(
                True,
                "Footer created successfully",
                response.data,
                status.HTTP_201_CREATED,
            )
        except IntegrityError:
            return api_response(
                False,
                "Footer already exists (DB constraint). Only one is allowed.",
                {},
                status.HTTP_400_BAD_REQUEST,
            )

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        cache.delete(CACHE_KEY)
        return api_response(True, "Footer updated successfully", response.data, status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        super().destroy(request, *args, **kwargs)
        cache.delete(CACHE_KEY)
        return api_response(True, "Footer deleted successfully", {}, status.HTTP_204_NO_CONTENT)

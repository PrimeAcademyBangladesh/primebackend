"""Views for managing policy pages such as Privacy Policy, Terms of Service, etc."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema

from api.models.models_policy_pages import PolicyPage
from api.serializers.serializers_policy import PolicyPageSerializer
from api.utils.response_utils import api_response
from api.views.views_base import BaseAdminViewSet


@extend_schema(
    tags=["Admin Policy Pages"],
    description=(
        "APIs for managing policy related pages such as Privacy Policy, "
        "Terms of Service, Cookie Policy, Data Protection Policy, Refund Policy, etc."
    ),
    request=PolicyPageSerializer,
    responses={200: PolicyPageSerializer},
)
class PolicyPageViewSet(BaseAdminViewSet):
    """
    ViewSet for managing policy pages such as
    Privacy Policy,
    Terms of Service,
    Cookie Policy,
    Data Protection Policy,
    Refund Policy, etc.

    NOTE:
    - GET uses page_name (slug) for public access
    - PUT, PATCH, DELETE use UUID (pk) for admin operations
    """

    queryset = PolicyPage.objects.all()
    serializer_class = PolicyPageSerializer
    lookup_field = "pk"  # Default to UUID for admin operations

    @extend_schema(
        summary="Retrieve policy page by page name",
        description="Get policy page content using page name slug (e.g., 'privacy', 'terms')",
        parameters=[
            OpenApiParameter(
                name="page_name",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description="Page name slug (privacy, terms, refund, cookie, etc.)",
                required=True,
            )
        ],
        responses={200: PolicyPageSerializer},
    )
    def retrieve(self, request, page_name=None):
        """
        Retrieve a policy page by its page_name slug.
        Public endpoint - no authentication required.
        """
        try:
            policy_page = self.get_queryset().get(page_name=page_name)
            serializer = self.get_serializer(policy_page)
            return api_response(True, "Policy page retrieved successfully", serializer.data)
        except PolicyPage.DoesNotExist:
            return api_response(False, "Policy page not found", {}, 404)

    @extend_schema(
        summary="Retrieve policy page by name (alternative endpoint)",
        description="Alternative endpoint to get policy page by name",
        parameters=[
            OpenApiParameter(
                name="page_name",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description="Page name slug",
                required=True,
            )
        ],
        responses={200: PolicyPageSerializer},
    )
    def by_page_name(self, request, page_name=None):
        """
        Alternative endpoint to retrieve a policy page by its name.
        Same as retrieve but with explicit naming.
        """
        try:
            policy_page = self.get_queryset().get(page_name=page_name)
            serializer = self.get_serializer(policy_page)
            return api_response(True, "Policy page retrieved successfully", serializer.data)
        except PolicyPage.DoesNotExist:
            return api_response(False, "Policy page not found", {}, 404)

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, mixins, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from api.models.models_contact import ContactMessage
from api.permissions import IsStaff
from api.serializers.serializers_contact import ContactMessageSerializer
from api.utils.filters_utils import ContactMessageFilter
from api.utils.pagination import StandardResultsSetPagination


@extend_schema(
    tags=["Contact Form display and submission"],
    summary="Submit or view contact messages",
    request=ContactMessageSerializer,
    responses={201: ContactMessageSerializer, 400: "Validation Error"},
)
class ContactMessageViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    Provides:
      - POST /api/contact/   → Public can submit a message
      - GET  /api/contact/   → Only admin can view messages
    """

    queryset = ContactMessage.objects.all().order_by("-created_at")
    serializer_class = ContactMessageSerializer
    # Admin listing: pagination, filters (including date range), search and ordering
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    # Use shared filter from api.utils.filters_utils
    # Bind model on the fly to avoid circular imports inside the filters module
    ContactMessageFilter.Meta.model = ContactMessage
    filterset_class = ContactMessageFilter
    # Search by sender name/email or message text
    search_fields = ["first_name", "last_name", "email", "message"]
    ordering_fields = ["created_at"]

    def get_permissions(self):
        """Allow anyone to POST but restrict GET to admin users."""
        if self.action == "create":
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsStaff]
        return [permission() for permission in permission_classes]

    def create(self, request, *args, **kwargs):
        """Create a contact message with uniform success/error response."""
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "message": "Validation failed.", "data": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        self.perform_create(serializer)

        return Response(
            {"success": True, "message": "Your message has been submitted successfully.", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

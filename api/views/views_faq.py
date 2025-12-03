from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.response import Response

from api.models.models_faq import FAQItem
from api.serializers.serializers_faq import FAQItemSerializer
from api.utils.cache_utils import cache_response, CACHE_KEY_FAQ_LIST
from api.views.views_base import BaseAdminViewSet


@extend_schema(
    tags=["FAQ Management"],
    description="ViewSet for managing FAQs grouped by FAQ navigation category (ordered by FAQItem.order).",
    responses=FAQItemSerializer,
    request=FAQItemSerializer,
)
class FAQViewSet(BaseAdminViewSet):
    """
    Returns grouped FAQs under each FAQ navigation (faq_nav).
    """
    queryset = FAQItem.objects.all().prefetch_related('faqs').order_by('order', 'created_at')
    serializer_class = FAQItemSerializer

    @cache_response(timeout=3600, key_prefix=CACHE_KEY_FAQ_LIST)
    def list(self, request):
        items = FAQItem.objects.all()\
            .prefetch_related('faqs')\
            .order_by('order', 'created_at')

        serializer = FAQItemSerializer(items, many=True)
        return Response({
            "success": True,
            "message": "FAQs retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)



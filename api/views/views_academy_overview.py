from drf_spectacular.utils import extend_schema

from api.models.models_academy_overview import AcademyOverview
from api.serializers.serializers_academy_overview import \
    AcademyOverviewSerializer
from api.views.views_base import BaseAdminViewSet


@extend_schema(
    tags=["Academy Overview"],
    summary="Academy Overview Resource",
    responses=AcademyOverviewSerializer,
    request=AcademyOverviewSerializer,
)
class AcademyOverviewViewSet(BaseAdminViewSet):
    queryset = AcademyOverview.objects.all().order_by("-created_at")
    serializer_class = AcademyOverviewSerializer

    def get_queryset(self):
        """Return a queryset containing only the most-recent AcademyOverview.

        Uses the base class public/staff filtering, orders by created_at and
        limits the result to the first row so list endpoints always return a
        single item.
        """
        qs = super().get_queryset()
        # ensure consistent ordering and only the first item is returned as a queryset slice
        return qs.order_by("-created_at")[:1]

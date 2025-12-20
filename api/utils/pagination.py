"""Pagination helpers used across API views and viewsets.

Defines a standard PageNumberPagination subclass and an optional mixin
for reuse in GenericAPIView-based views.
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


# Standard Pagination for ViewSets and Generic Views
class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination class for consistent pagination across all API endpoints
    Can be used for users, blogs, courses, products, etc.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 60

    def get_paginated_response(self, data):
        """
        Return a paginated response with the given data.

        Args:
            data: List of objects to be paginated

        Returns:
            Response: Paginated response with count, next, previous, and results
        """
        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )


# Generic Mixin for Pagination where use APIView or GenericAPIView
class PaginatedListMixin:
    """
    Generic mixin to add pagination to any list view
    Works with any Django model - users, blogs, courses, products, etc.
    """

    pagination_class = StandardResultsSetPagination

    def paginate_queryset(self, queryset, request):
        """
        Paginate any queryset and return paginated data
        """
        paginator = self.pagination_class()
        paginated_data = paginator.paginate_queryset(queryset, request)
        return paginated_data, paginator

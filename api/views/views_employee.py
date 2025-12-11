from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters

from api.models.models_employee import Department, Employee
from api.permissions import IsAdmin
from api.serializers.serializers_employee import (DepartmentSerializer,
                                                  EmployeeSerializer)
from api.utils.pagination import StandardResultsSetPagination
from api.views.views_base import BaseAdminViewSet
from rest_framework.parsers import MultiPartParser, FormParser

@extend_schema(
    tags=["Employee"],
    summary="Employee Department Resources",
    responses=EmployeeSerializer,
    request=EmployeeSerializer,
)
class DepartmentViewSet(BaseAdminViewSet):
    """
    A simple ViewSet for viewing and editing departments.
    """

    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    # Provide admin-friendly listing: pagination, filtering and search
    pagination_class = StandardResultsSetPagination
    parser_classes = (MultiPartParser, FormParser)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["is_active"]
    search_fields = ["name"]
    
    def get_permissions(self):
        """Force all Employee actions to require admin."""
        return [IsAdmin()]


@extend_schema(
    tags=["Employee"],
    summary="Employee Resources",
    responses=EmployeeSerializer,
    request=EmployeeSerializer,
)
class EmployeeViewSet(BaseAdminViewSet):
    """
    A simple ViewSet for viewing and editing employees.
    """

    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    # Admin listing improvements: pagination, filtering, search and ordering
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # Only include fields that exist on the model. 'role' and 'employment_status'
    # are not present on Employee model, so we expose department and is_active.
    filterset_fields = ["department", "is_active", "joining_date"]
    # Search using actual model fields
    search_fields = ["employee_name", "email", "phone_number"]
    ordering_fields = ["created_at", "employee_name", "joining_date"]
    
    def get_permissions(self):
        """Force all Employee actions to require admin."""
        return [IsAdmin()]

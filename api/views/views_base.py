"""Base ViewSet for admin-style CRUD operations with standardized responses and
role-based access control."""

from django.core.exceptions import ImproperlyConfigured
from django.http import Http404

from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import NotFound

from api.permissions import IsAdmin
from api.utils.response_utils import api_response


class BaseAdminViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet for admin-style CRUD.
    - Retrieve uses slug if declared.
    - Update, partial_update, destroy use pk.
    - Standardized CRUD responses.
    - Permissions are overridable in child viewsets.
    """

    queryset = None
    serializer_class = None
    pagination_class = None
    permission_classes = None

    # Optional: slug for retrieve only
    slug_field = None
    slug_lookup_only_actions = ["retrieve"]

    def get_default_permissions(self):
        """Return default fallback permission for all actions except public ones.

        By default we consider destructive operations (delete) to require admin,
        while create/update operations are allowed for staff (see get_permissions).
        Child viewsets may still override `permission_classes` to customise.
        """
        return [IsAdmin()]

    def get_permissions(self):
        """
        Returns the list of permissions for the current action.

        Checks if the action is in public actions (list, retrieve, latest) and
        returns AllowAny permission if so. Otherwise, it uses the child-defined
        permission_classes if set, or falls back to the default permissions.
        """
        # Define permission tiers for consistency across viewsets
        PUBLIC_ACTIONS = {
            "list",
            "retrieve",
            "latest",
            "featured",
            "home_categories",
            "megamenu_nav",
            "by_category",
        }
        STAFF_ACTIONS = {"create", "update", "partial_update"}
        ADMIN_ACTIONS = {"destroy"}

        # Public actions (available to anonymous users) - ALWAYS public
        if self.action in PUBLIC_ACTIONS:
            return [permissions.AllowAny()]

        # if self.action in PUBLIC_ACTIONS:
        #     if getattr(self, "permission_classes", None):
        #         return [perm() for perm in self.permission_classes]
        #     return [permissions.AllowAny()]

        # Admin-only destructive actions - requires explicit override
        if self.action in ADMIN_ACTIONS:
            return [IsAdmin()]

        # If viewset explicitly sets permission_classes, use them for staff-level actions
        if getattr(self, "permission_classes", None):
            return [perm() for perm in self.permission_classes]

        # If no permission_classes set, use action-based permissions
        # Staff-level actions: create and updates
        if self.action in STAFF_ACTIONS:
            from api.permissions import IsStaff

            return [IsStaff()]

        # fallback to default
        return self.get_default_permissions()

        # ----------------------------

    # Queryset Filtering - ADD THESE MISSING METHODS
    # ----------------------------

    def is_staff_user(self, user):
        """Check if user has staff/admin role"""
        return user.is_authenticated and user.role in ["staf", "admin", "superadmin"]

    def is_staff_and_teacher_user(self, user):
        """Check if user has staff/admin/teacher role"""
        return user.is_authenticated and user.role in [
            "staff",
            "admin",
            "superadmin",
            "teacher",
        ]

    def get_base_queryset(self):
        """Get the base queryset before any filtering"""
        if self.queryset is None:
            raise ImproperlyConfigured(f"{self.__class__.__name__} must define queryset")
        return self.queryset.all()

    def filter_public_queryset(self, queryset):
        """
        Smart default public filtering for safety.
        - If model has is_active: filter by it
        - If model has status: filter by status='published'
        - Otherwise: force explicit implementation
        """
        model = queryset.model

        # Safety check 1: If model has is_active field, use it
        if hasattr(model, "is_active"):
            return queryset.filter(is_active=True)

        # Safety check 2: If model has status field, filter published
        elif hasattr(model, "status"):
            return queryset.filter(status="published")

        # Safety check 3: Force implementation for models without standard fields
        else:
            raise NotImplementedError(
                f"{self.__class__.__name__} must implement filter_public_queryset method "
                f"for model {model.__name__} (no is_active or status field found)"
            )

    def get_queryset(self):
        """
        Apply role-based filtering:
        - Staff users: see everything
        - Non-staff users: see filtered content (via filter_public_queryset)
        """
        queryset = self.get_base_queryset()

        # For public actions, apply public filtering to non-staff users
        if self.action in ["list", "retrieve", "latest"] and not self.is_staff_user(self.request.user):
            queryset = self.filter_public_queryset(queryset)

        return queryset

    # ----------------------------
    # Helpers
    # ----------------------------

    def get_model_name(self):
        if not hasattr(self, "queryset") or self.queryset is None:
            raise ImproperlyConfigured(f"{self.__class__.__name__} must define queryset")
        return self.queryset.model._meta.verbose_name.title()

    def get_lookup_field_for_action(self):
        """Determine which field to use for the current action."""
        if self.action in getattr(self, "slug_lookup_only_actions", []) and self.slug_field:
            return self.slug_field
        return "pk"

    def get_object(self):
        """
        Retrieve object using slug only for retrieve action,
        otherwise always use pk.
        """
        self.lookup_field = self.get_lookup_field_for_action()
        try:
            return super().get_object()
        except (Http404, NotFound, AssertionError) as original_exc:
            # fallback: only allow pk lookup if not already using pk
            if self.lookup_field != "pk":
                lookup_value = self.kwargs.get("pk")
                if lookup_value is None:
                    raise original_exc
                queryset = self.filter_queryset(self.get_queryset())
                try:
                    obj = queryset.get(pk=lookup_value)
                except Exception:
                    raise original_exc
                self.check_object_permissions(self.request, obj)
                return obj
            raise original_exc

    # ----------------------------
    # CRUD Response Wrappers
    # ----------------------------
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return api_response(
                True,
                f"{self.get_model_name()}s retrieved successfully",
                self.get_paginated_response(serializer.data).data,
            )
        serializer = self.get_serializer(queryset, many=True)
        return api_response(True, f"{self.get_model_name()}s retrieved successfully", serializer.data)

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        return api_response(True, f"{self.get_model_name()} retrieved successfully", response.data)

    def create(self, request, *args, **kwargs):
        from django.core.exceptions import ValidationError as DjangoValidationError

        self.check_permissions(request)
        print("Permissions checked", request.user.role)

        try:
            response = super().create(request, *args, **kwargs)
            return api_response(
                True,
                f"{self.get_model_name()} created successfully",
                response.data,
                status.HTTP_201_CREATED,
            )
        except DjangoValidationError as e:
            # Convert Django ValidationError to DRF response
            error_dict = e.message_dict if hasattr(e, "message_dict") else {"non_field_errors": [str(e)]}
            # Extract first error message for the main message field
            first_error = next(iter(error_dict.values()))[0] if error_dict else "Validation failed"
            return api_response(False, first_error, error_dict, status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        from django.core.exceptions import ValidationError as DjangoValidationError

        try:
            response = super().update(request, *args, **kwargs)
            return api_response(True, f"{self.get_model_name()} updated successfully", response.data)
        except DjangoValidationError as e:
            # Convert Django ValidationError to DRF response
            error_dict = e.message_dict if hasattr(e, "message_dict") else {"non_field_errors": [str(e)]}
            # Extract first error message for the main message field
            first_error = next(iter(error_dict.values()))[0] if error_dict else "Validation failed"
            return api_response(False, first_error, error_dict, status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        from django.core.exceptions import ValidationError as DjangoValidationError

        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return api_response(True, f"{self.get_model_name()} updated successfully", serializer.data)
        except DjangoValidationError as e:
            # Convert Django ValidationError to DRF response
            error_dict = e.message_dict if hasattr(e, "message_dict") else {"non_field_errors": [str(e)]}
            # Extract first error message for the main message field
            first_error = next(iter(error_dict.values()))[0] if error_dict else "Validation failed"
            return api_response(False, first_error, error_dict, status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        super().destroy(request, *args, **kwargs)
        return api_response(
            True,
            f"{self.get_model_name()} deleted successfully",
            {},
            status.HTTP_204_NO_CONTENT,
        )

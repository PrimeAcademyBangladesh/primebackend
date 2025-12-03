"""Course API views."""

import django_filters
from django.core.cache import cache
from django.db.models import Count, Prefetch, Q, Exists, OuterRef
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import filters, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

# Models
from api.models.models_course import (
    Category,
    Course,
    CourseContentSection,
    CourseDetail,
    CourseInstructor,
    CourseModule,
    CourseSectionTab,
    CourseTabbedContent,
    KeyBenefit,
    SideImageSection,
    SuccessStory,
    WhyEnrol,
)
from api.models.models_pricing import Coupon, CoursePrice
from api.models.models_order import Enrollment

# Permissions
from api.permissions import IsCourseManager, IsStaff

# Serializers
from api.serializers.serializers_course import (
    CategoryNavSerializer,
    CategorySerializer,
    CouponApplyResultSerializer,
    CouponCreateUpdateSerializer,
    CouponSerializer,
    CouponValidationSerializer,
    CourseContentSectionCreateUpdateSerializer,
    CourseContentSectionSerializer,
    CourseCreateUpdateSerializer,
    CourseDetailCreateUpdateSerializer,
    CourseDetailedSerializer,
    CourseDetailSerializer,
    CourseInstructorCreateUpdateSerializer,
    CourseInstructorSerializer,
    CourseListSerializer,
    CourseModuleCreateUpdateSerializer,
    CourseModuleSerializer,
    CourseNavSerializer,
    CoursePriceCreateUpdateSerializer,
    CoursePriceSerializer,
    CourseSectionTabCreateUpdateSerializer,
    CourseSectionTabSerializer,
    CourseTabbedContentCreateUpdateSerializer,
    CourseTabbedContentSerializer,
    KeyBenefitCreateUpdateSerializer,
    KeyBenefitSerializer,
    SideImageSectionCreateUpdateSerializer,
    SideImageSectionSerializer,
    SuccessStoryCreateUpdateSerializer,
    SuccessStorySerializer,
    WhyEnrolCreateUpdateSerializer,
    WhyEnrolSerializer,
)

# Utils
from api.utils.cache_utils import (
    CACHE_KEY_COURSE_DETAIL,
    CACHE_KEY_COURSE_FEATURED,
    CACHE_KEY_COURSE_LIST,
    CACHE_KEY_HOME_CATEGORIES,
    CACHE_KEY_MEGAMENU,
    cache_response,
)
from api.utils.pagination import StandardResultsSetPagination
from api.utils.response_utils import api_response
from api.views.views_base import BaseAdminViewSet

# ========== Custom Filters ==========


class CourseFilter(django_filters.FilterSet):
    """Custom filter for Course to accept category slug instead of UUID."""

    category = django_filters.CharFilter(
        field_name="category__slug",
        lookup_expr="iexact",
        help_text="Filter by category slug (e.g., web-development, data-science)",
    )
    status = django_filters.ChoiceFilter(
        choices=Course.STATUS_CHOICES,
        help_text="Filter by course status (draft, published, archived)",
    )
    is_active = django_filters.BooleanFilter(
        help_text="Filter by active status (true/false)"
    )

    class Meta:
        model = Course
        fields = ["category", "status", "is_active"]


# ========== Category ViewSet ==========


@extend_schema_view(
    list=extend_schema(
        summary="List all course categories",
        description="Retrieve all active categories. Staff users see all categories.",
        responses={200: CategorySerializer},
        tags=["Course - Categories"],
    ),
    retrieve=extend_schema(
        summary="Retrieve a course category by slug",
        description="Get a single category by its slug identifier.",
        responses={200: CategorySerializer},
        tags=["Course - Categories"],
    ),
    create=extend_schema(
        summary="Create a course category",
        description="Create a new category. Requires staff permissions.",
        responses={201: CategorySerializer},
        tags=["Course - Categories"],
    ),
    update=extend_schema(
        summary="Update a course category",
        description="Full update of a category. Requires staff permissions. Uses category ID.",
        responses={200: CategorySerializer},
        tags=["Course - Categories"],
    ),
    partial_update=extend_schema(
        summary="Partially update a course category",
        description="Partial update of a category. Requires staff permissions. Uses category ID.",
        responses={200: CategorySerializer},
        tags=["Course - Categories"],
    ),
    destroy=extend_schema(
        summary="Delete a course category",
        description="Delete a category. Requires admin permissions. Uses category ID.",
        responses={204: None},
        tags=["Course - Categories"],
    ),
)
class CategoryViewSet(BaseAdminViewSet):
    """
    CRUD operations for Course Categories.

    Permissions:
    - List/Retrieve: Public (shows only active categories to non-staff)
    - Create/Update: Staff
    - Delete: Admin

    Lookup:
    - Retrieve: Uses slug (e.g., /courses/categories/web-development/)
    - Update/Delete: Uses ID for safety
    """

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    lookup_field = "slug"
    slug_field = "slug"

    # FIXED: Only use slug for retrieve (public viewing)
    # Update and destroy should use pk for safety
    slug_lookup_only_actions = ["retrieve"]

    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active", "show_in_megamenu"]
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        """Optimize queryset with annotations for better performance."""
        queryset = super().get_queryset()

        # Annotate with active courses count for list views (prevents N+1 queries)
        if self.action == "list":
            queryset = queryset.annotate(
                active_courses_count=Count(
                    "courses",
                    filter=Q(courses__is_active=True, courses__status="published"),
                    distinct=True,
                )
            )

        return queryset


# ========== Course ViewSet ==========


@extend_schema_view(
    list=extend_schema(
        summary="List courses",
        description="Get paginated list of courses. Public users see only published & active courses.",
        responses={200: CourseListSerializer},
        tags=["Course - Main"],
    ),
    create=extend_schema(
        summary="Create a course",
        responses={201: CourseCreateUpdateSerializer},
        tags=["Course - Main"],
    ),
    retrieve=extend_schema(
        summary="Retrieve course by slug",
        description="Get detailed course information including pricing and all course details.",
        parameters=[
            OpenApiParameter(
                name="slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="Slug of the course (use slug, not UUID)",
            )
        ],
        responses={200: CourseDetailedSerializer},
        tags=["Course - Main"],
    ),
    update=extend_schema(
        summary="Update course by ID",
        responses={200: CourseCreateUpdateSerializer},
        tags=["Course - Main"],
    ),
    partial_update=extend_schema(
        summary="Partially update course by ID",
        responses={200: CourseCreateUpdateSerializer},
        tags=["Course - Main"],
    ),
    destroy=extend_schema(
        summary="Delete course by ID", responses={204: None}, tags=["Course - Main"]
    ),
)
class CourseViewSet(BaseAdminViewSet):
    """Course CRUD: slug for retrieve, ID for update/delete."""

    queryset = (
        Course.objects.select_related("category", "pricing")
        .prefetch_related(
            "detail__content_sections__tabs__contents",
            "detail__content_sections__tabs",
            "detail__content_sections",
            "detail__why_enrol",
            "detail__modules",
            "detail__benefits",
            "detail__side_image_sections",
            "detail__success_stories",
        )
        .order_by("-created_at")
    )
    serializer_class = CourseListSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsCourseManager]
    slug_field = "slug"
    slug_lookup_only_actions = ["retrieve"]

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = CourseFilter
    search_fields = ["title", "short_description"]
    ordering_fields = ["title", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_permissions(self):
        """Return permission classes based on action.
        
        Custom actions can define their own permission_classes which will
        override the viewset-level permissions.
        """
        # Check if this action has custom permission_classes in its decorator
        if hasattr(self, 'action'):
            try:
                # Get the action method
                action_method = getattr(self, self.action, None)
                if action_method and hasattr(action_method, 'kwargs'):
                    # Check if the action has permission_classes defined
                    action_permissions = action_method.kwargs.get('permission_classes')
                    if action_permissions is not None:
                        return [permission() for permission in action_permissions]
            except (AttributeError, KeyError):
                pass
        
        # Fall back to viewset-level permissions
        return super().get_permissions()

    def get_serializer_class(self):
        """Use detailed serializer for retrieve, create/update serializer for modifications."""
        if self.action == "retrieve":
            return CourseDetailedSerializer
        elif self.action in ["create", "update", "partial_update"]:
            return CourseCreateUpdateSerializer
        return CourseListSerializer

    def get_queryset(self):
        """Annotate queryset with `is_purchased` for authenticated users to avoid N+1 queries.

        Uses an `Exists` subquery on `Enrollment` to mark courses the current user
        is enrolled in. For anonymous users the queryset is left unchanged.
        """
        queryset = super().get_queryset()

        user = getattr(self.request, 'user', None)
        if user and user.is_authenticated:
            enrollment_qs = Enrollment.objects.filter(user=user, course=OuterRef('pk'), is_active=True)
            queryset = queryset.annotate(is_purchased=Exists(enrollment_qs))

        return queryset

    def filter_public_queryset(self, queryset):
        """Public users only see published and active courses."""
        return queryset.filter(is_active=True, status="published")

    @cache_response(timeout=600, key_prefix=CACHE_KEY_COURSE_LIST)
    def list(self, request, *args, **kwargs):
        """List courses - cached for 10 minutes."""
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Retrieve course detail.

        Caching policy:
        - Anonymous users: return cached payload (sample modules)
        - Staff/superusers: bypass cache and return full payload
        - Authenticated students: if purchased, bypass cache and return full payload
          otherwise treat as anonymous (show sample)
        """
        from django.core.cache import cache
        from api.utils.cache_utils import generate_cache_key, CACHE_KEY_COURSE_DETAIL

        # Determine the course instance early so we can check enrollment
        instance = self.get_object()

        # Determine if requester should see full list
        user = getattr(request, 'user', None)
        is_staff_user = bool(user and getattr(user, 'is_staff', False)) or bool(user and getattr(user, 'is_superuser', False))
        is_purchased = False
        if user and user.is_authenticated and not is_staff_user:
            try:
                from api.models.models_order import Enrollment
                is_purchased = Enrollment.objects.filter(user=user, course=instance, is_active=True).exists()
            except Exception:
                is_purchased = False

        # If staff or purchased user, bypass cache entirely
        if is_staff_user or is_purchased:
            response = super().retrieve(request, *args, **kwargs)
            return api_response(True, f"{self.get_model_name()} retrieved successfully", response.data)

        # Anonymous/guest path: use cache
        # Build cache key consistent with cache_utils.generate_cache_key
        query_params = sorted(request.GET.items())
        cache_key = generate_cache_key(CACHE_KEY_COURSE_DETAIL, request.path, *[f"{k}={v}" for k, v in query_params])

        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return api_response(
                cached_data['success'],
                cached_data['message'],
                cached_data['data'],
            )

        # Not cached: call view and store
        response = super().retrieve(request, *args, **kwargs)
        if hasattr(response, 'data') and hasattr(response, 'status_code') and response.status_code == 200:
            cache_data = {
                'success': response.data.get('success', True),
                'message': response.data.get('message', ''),
                'data': response.data.get('data', {}),
                'status_code': response.status_code,
            }
            cache.set(cache_key, cache_data, 1800)

        return api_response(True, f"{self.get_model_name()} retrieved successfully", response.data)

    @extend_schema(
        summary="Get courses by category",
        description="Retrieve all active published courses in a specific category.",
        parameters=[
            OpenApiParameter(
                name="category_slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="Slug of the category",
            )
        ],
        responses={200: CourseListSerializer},
        tags=["Course - Main"],
    )
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.AllowAny],
        url_path="category/(?P<category_slug>[^/.]+)",
    )
    def by_category(self, request, category_slug=None):
        """Get all courses in a specific category."""
        queryset = self.get_queryset().filter(
            category__slug=category_slug,
            category__is_active=True,
            is_active=True,
            status="published",
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return api_response(
                True,
                f"Courses in category '{category_slug}' retrieved successfully",
                self.get_paginated_response(serializer.data).data,
            )

        serializer = self.get_serializer(queryset, many=True)
        return api_response(
            True,
            f"Courses in category '{category_slug}' retrieved successfully",
            serializer.data,
        )

    @extend_schema(
        summary="Get featured/latest courses",
        description="Retrieve the latest 6 published courses.",
        responses={200: CourseListSerializer},
        tags=["Course - Main"],
    )
    @cache_response(timeout=1800, key_prefix=CACHE_KEY_COURSE_FEATURED)
    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def featured(self, request):
        """Retrieve the latest 6 published courses."""
        queryset = (
            self.get_queryset()
            .filter(is_active=True, status="published")
            .order_by("-created_at")[:6]
        )

        serializer = self.get_serializer(queryset, many=True)
        return api_response(
            True,
            "Featured courses retrieved successfully",
            {"results": serializer.data},
            status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Get categories with courses for home",
        description="Return active categories and up to 10 courses per category for home display. By default only courses with `show_in_home_tab=True` are returned. Use `include_all=true` to include all published courses.",
        responses={200: OpenApiParameter},
        tags=["Course - Main"],
    )
    @cache_response(timeout=900, key_prefix=CACHE_KEY_HOME_CATEGORIES)
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.AllowAny],
        url_path="home-categories",
    )
    def home_categories(self, request):
        """Return categories each with up to 10 courses for frontend home sections."""
        include_all = request.query_params.get("include_all", "false").lower() == "true"

        # Optimize: Prefetch courses for each category to avoid N+1
        # Build the courses queryset with proper select_related for nested objects
        courses_base_qs = (
            Course.objects.filter(is_active=True, status="published")
            .select_related("category", "pricing")
            .order_by("-created_at")
        )

        if not include_all:
            courses_base_qs = courses_base_qs.filter(show_in_home_tab=True)

        # Prefetch courses for each category (limit 10 per category)
        categories = (
            Category.objects.filter(is_active=True)
            .prefetch_related(
                Prefetch(
                    "courses", queryset=courses_base_qs[:10], to_attr="home_courses"
                )
            )
            .order_by("name")
        )

        result = []
        for cat in categories:
            # Use prefetched courses
            if not cat.home_courses:
                continue

            serializer = CourseListSerializer(cat.home_courses, many=True)
            result.append(
                {"category": CategorySerializer(cat).data, "courses": serializer.data}
            )

        return api_response(True, "Home categories with courses retrieved", result)

    @extend_schema(
        summary="Get megamenu navigation (category -> course titles)",
        description="Return categories with a list of course titles (and slugs) for building site navigation.",
        responses={200: OpenApiParameter},
        tags=["Course - Main"],
    )
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.AllowAny],
        url_path="megamenu-nav",
    )
    def megamenu_nav(self, request):
        """Return categories and a minimal list of course titles (and slugs).

        Cached under a single key; invalidated by Course/Category signals.
        """
        MEGAMENU_CACHE_TTL = 60 * 60  # 1 hour
        cached = cache.get(CACHE_KEY_MEGAMENU)
        if cached is not None:
            # Normalize cached payload: handle both old {"results": [...]} and new [...]
            if isinstance(cached, dict) and "results" in cached:
                data = cached["results"]
            else:
                data = cached
            return api_response(True, "Megamenu nav retrieved (cached)", data)

        # Optimize: Prefetch courses for each category to avoid N+1
        megamenu_courses_qs = (
            Course.objects.filter(
                is_active=True, status="published", show_in_megamenu=True
            )
            .select_related("category")
            .order_by("-created_at")[:10]
        )

        categories = (
            Category.objects.filter(is_active=True, show_in_megamenu=True)
            .prefetch_related(
                Prefetch(
                    "courses", queryset=megamenu_courses_qs, to_attr="megamenu_courses"
                )
            )
            .order_by("name")
        )

        result = []
        for cat in categories:
            # Use prefetched courses
            if not cat.megamenu_courses:
                continue

            cat_ser = CategoryNavSerializer(cat)
            course_ser = CourseNavSerializer(cat.megamenu_courses, many=True)
            result.append(
                {
                    "category": cat_ser.data,
                    "courses": course_ser.data,
                }
            )

        # Return plain list (frontend expects array directly for .map())
        payload = result
        cache.set(CACHE_KEY_MEGAMENU, payload, MEGAMENU_CACHE_TTL)
        return api_response(True, "Megamenu nav retrieved", payload)

    @extend_schema(
        summary="Get modules for a course",
        description="Get all modules for a specific course by course slug. Returns modules with UUIDs that can be used to filter live classes, assignments, and quizzes.",
        parameters=[
            OpenApiParameter(
                name="course_slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="Slug of the course",
            )
        ],
        responses={200: CourseModuleSerializer(many=True)},
        tags=["Course - Main"],
    )
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.AllowAny],
        url_path="(?P<course_slug>[^/.]+)/modules",
    )
    def modules(self, request, course_slug=None):
        """Get all modules for a specific course by slug."""
        try:
            course = Course.objects.select_related('detail').get(
                slug=course_slug,
                is_active=True,
                status='published'
            )
        except Course.DoesNotExist:
            return api_response(False, "Course not found", None, status.HTTP_404_NOT_FOUND)
        
        modules = CourseModule.objects.filter(
            course=course.detail,
            is_active=True
        ).order_by('order')
        
        serializer = CourseModuleSerializer(modules, many=True)
        return api_response(
            True,
            f"Modules for course '{course.title}' retrieved successfully",
            serializer.data,
            status.HTTP_200_OK
        )

    # Note: megamenu and compact megamenu endpoints removed per request.


# ========== Course Price ViewSet ==========


@extend_schema_view(
    list=extend_schema(
        summary="List course prices",
        responses={200: CoursePriceSerializer},
        tags=["Course - Pricing"],
    ),
    retrieve=extend_schema(
        summary="Retrieve course price",
        responses={200: CoursePriceSerializer},
        tags=["Course - Pricing"],
    ),
    create=extend_schema(
        summary="Create course price",
        responses={201: CoursePriceCreateUpdateSerializer},
        tags=["Course - Pricing"],
    ),
    update=extend_schema(
        summary="Update course price",
        responses={200: CoursePriceCreateUpdateSerializer},
        tags=["Course - Pricing"],
    ),
    partial_update=extend_schema(
        summary="Partially update course price",
        responses={200: CoursePriceCreateUpdateSerializer},
        tags=["Course - Pricing"],
    ),
    destroy=extend_schema(
        summary="Delete course price", responses={204: None}, tags=["Course - Pricing"]
    ),
)
class CoursePriceViewSet(BaseAdminViewSet):
    """CRUD for Course Pricing."""

    queryset = CoursePrice.objects.select_related("course").all()
    serializer_class = CoursePriceSerializer
    permission_classes = [IsStaff]

    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["currency", "is_free", "is_active", "installment_available"]
    search_fields = ["course__title"]
    ordering_fields = ["base_price", "created_at"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """Use create/update serializer for modifications."""
        if self.action in ["create", "update", "partial_update"]:
            return CoursePriceCreateUpdateSerializer
        return CoursePriceSerializer

    @extend_schema(
        summary="Get price by course slug",
        description="Retrieve pricing information for a specific course.",
        parameters=[
            OpenApiParameter(
                name="course_slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="Slug of the course",
            )
        ],
        responses={200: CoursePriceSerializer},
        tags=["Course - Pricing"],
    )
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.AllowAny],
        url_path="course/(?P<course_slug>[^/.]+)",
    )
    def by_course(self, request, course_slug=None):
        """Get pricing for a specific course."""
        try:
            price = self.get_queryset().get(
                course__slug=course_slug, course__is_active=True, is_active=True
            )
            serializer = self.get_serializer(price)
            return api_response(
                True, "Course price retrieved successfully", serializer.data
            )
        except CoursePrice.DoesNotExist:
            return api_response(
                False, "Price not found for this course", {}, status.HTTP_404_NOT_FOUND
            )


# ========== Coupon ViewSet ==========


@extend_schema_view(
    list=extend_schema(
        summary="List coupons",
        responses={200: CouponSerializer},
        tags=["Course - Coupons"],
    ),
    retrieve=extend_schema(
        summary="Retrieve coupon",
        responses={200: CouponSerializer},
        tags=["Course - Coupons"],
    ),
    create=extend_schema(
        summary="Create coupon",
        responses={201: CouponCreateUpdateSerializer},
        tags=["Course - Coupons"],
    ),
    update=extend_schema(
        summary="Update coupon",
        responses={200: CouponCreateUpdateSerializer},
        tags=["Course - Coupons"],
    ),
    partial_update=extend_schema(
        summary="Partially update coupon",
        responses={200: CouponCreateUpdateSerializer},
        tags=["Course - Coupons"],
    ),
    destroy=extend_schema(
        summary="Delete coupon", responses={204: None}, tags=["Course - Coupons"]
    ),
)
class CouponViewSet(BaseAdminViewSet):
    """CRUD for Coupons."""

    queryset = Coupon.objects.prefetch_related("courses").all()
    serializer_class = CouponSerializer
    permission_classes = [IsStaff]

    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["discount_type", "is_active", "apply_to_all"]
    search_fields = ["code"]
    ordering_fields = ["code", "valid_from", "valid_until", "created_at"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """Use create/update serializer for modifications."""
        if self.action in ["create", "update", "partial_update"]:
            return CouponCreateUpdateSerializer
        elif self.action == "validate_coupon":
            return CouponValidationSerializer
        return CouponSerializer

    def filter_public_queryset(self, queryset):
        """Public users only see active coupons."""
        return queryset.filter(is_active=True)

    @extend_schema(
        summary="Validate coupon code",
        description="Validate a coupon code for a specific course and calculate discount.",
        request=CouponValidationSerializer,
        responses={200: CouponApplyResultSerializer},
        tags=["Course - Coupons"],
    )
    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.AllowAny],
        url_path="validate",
    )
    def validate_coupon(self, request):
        """Validate a coupon code and calculate the discount."""
        serializer = CouponValidationSerializer(data=request.data)

        if not serializer.is_valid():
            return api_response(
                False,
                "Validation failed",
                serializer.errors,
                status.HTTP_400_BAD_REQUEST,
            )

        # Get validated coupon and course
        coupon = serializer.validated_data["coupon"]
        course = serializer.validated_data["course"]

        # Get course pricing
        try:
            pricing = course.pricing
            original_price = pricing.get_discounted_price()
        except CoursePrice.DoesNotExist:
            return api_response(
                False, "No pricing found for this course", {}, status.HTTP_404_NOT_FOUND
            )

        # Calculate coupon discount
        discount_amount = coupon.calculate_discount(original_price)
        final_price = max(original_price - discount_amount, 0)

        result_data = {
            "original_price": original_price,
            "discount_amount": discount_amount,
            "final_price": final_price,
            "discount_type": coupon.discount_type,
            "discount_value": coupon.discount_value,
            "coupon_code": coupon.code,
            "message": f"Coupon applied successfully! You save {pricing.currency} {discount_amount}",
        }

        result_serializer = CouponApplyResultSerializer(result_data)
        return api_response(
            True,
            "Coupon validated successfully",
            result_serializer.data,
            status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Get active coupons",
        description="Retrieve all currently valid and active coupons.",
        responses={200: CouponSerializer},
        tags=["Course - Coupons"],
    )
    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def active(self, request):
        """Get all currently valid coupons."""
        from django.utils import timezone

        now = timezone.now()

        queryset = self.get_queryset().filter(
            is_active=True, valid_from__lte=now, valid_until__gte=now
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return api_response(
                True,
                "Active coupons retrieved successfully",
                self.get_paginated_response(serializer.data).data,
            )

        serializer = self.get_serializer(queryset, many=True)
        return api_response(
            True, "Active coupons retrieved successfully", serializer.data
        )


# ========== Course Detail ViewSet ==========


@extend_schema_view(
    list=extend_schema(
        summary="List all course details",
        description="Get all course detail pages with nested components.",
        tags=["Course - Details"],
    ),
    retrieve=extend_schema(
        summary="Retrieve course detail by ID", tags=["Course - Details"]
    ),
    create=extend_schema(summary="Create course detail", tags=["Course - Details"]),
    update=extend_schema(summary="Update course detail", tags=["Course - Details"]),
    partial_update=extend_schema(
        summary="Partially update course detail", tags=["Course - Details"]
    ),
    destroy=extend_schema(
        summary="Delete course detail", responses={204: None}, tags=["Course - Details"]
    ),
)
class CourseDetailViewSet(BaseAdminViewSet):
    """CRUD operations for CourseDetail (hero sections)."""

    queryset = (
        CourseDetail.objects.select_related("course")
        .prefetch_related(
            "content_sections__tabs__contents",
            "why_enrol",
            "modules",
            "benefits",
            "side_image_sections",
            "success_stories",
        )
        .all()
    )
    serializer_class = CourseDetailSerializer
    permission_classes = [IsStaff]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active", "course"]
    search_fields = ["course__title", "hero_text"]
    ordering_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CourseDetailCreateUpdateSerializer
        return CourseDetailSerializer


# ========== Course Content Section ViewSet ==========


@extend_schema_view(
    list=extend_schema(summary="List content sections", tags=["Course - Content"]),
    retrieve=extend_schema(
        summary="Retrieve content section", tags=["Course - Content"]
    ),
    create=extend_schema(summary="Create content section", tags=["Course - Content"]),
    update=extend_schema(summary="Update content section", tags=["Course - Content"]),
    partial_update=extend_schema(
        summary="Partially update content section", tags=["Course - Content"]
    ),
    destroy=extend_schema(
        summary="Delete content section",
        responses={204: None},
        tags=["Course - Content"],
    ),
)
class CourseContentSectionViewSet(BaseAdminViewSet):
    """CRUD operations for CourseContentSection."""

    queryset = (
        CourseContentSection.objects.select_related("course__course")
        .prefetch_related("tabs__contents")
        .all()
    )
    serializer_class = CourseContentSectionSerializer
    permission_classes = [IsStaff]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active", "course"]
    search_fields = ["section_name", "course__course__title"]
    ordering_fields = ["order", "created_at"]
    ordering = ["course", "order"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CourseContentSectionCreateUpdateSerializer
        return CourseContentSectionSerializer


# ========== Course Section Tab ViewSet ==========


@extend_schema_view(
    list=extend_schema(
        summary="List section tabs", responses={200: None}, tags=["Course - Content"]
    ),
    retrieve=extend_schema(
        summary="Retrieve section tab", responses={200: None}, tags=["Course - Content"]
    ),
    create=extend_schema(
        summary="Create section tab", responses={201: None}, tags=["Course - Content"]
    ),
    update=extend_schema(
        summary="Update section tab", responses={200: None}, tags=["Course - Content"]
    ),
    partial_update=extend_schema(
        summary="Partially update section tab",
        responses={200: None},
        tags=["Course - Content"],
    ),
    destroy=extend_schema(
        summary="Delete section tab", responses={204: None}, tags=["Course - Content"]
    ),
)
class CourseSectionTabViewSet(BaseAdminViewSet):
    """CRUD operations for CourseSectionTab (max 2 per section)."""

    queryset = (
        CourseSectionTab.objects.select_related("section__course__course")
        .prefetch_related("contents")
        .all()
    )
    serializer_class = CourseSectionTabSerializer
    permission_classes = [IsStaff]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active", "section"]
    search_fields = ["tab_name", "section__section_name"]
    ordering_fields = ["order", "section"]
    ordering = ["section", "order"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CourseSectionTabCreateUpdateSerializer
        return CourseSectionTabSerializer


# ========== Course Tabbed Content ViewSet ==========


@extend_schema_view(
    list=extend_schema(
        summary="List tabbed content items",
        responses={200: None},
        tags=["Course - Content"],
    ),
    retrieve=extend_schema(
        summary="Retrieve content item",
        responses={200: None},
        tags=["Course - Content"],
    ),
    create=extend_schema(
        summary="Create content item", responses={201: None}, tags=["Course - Content"]
    ),
    update=extend_schema(
        summary="Update content item", responses={200: None}, tags=["Course - Content"]
    ),
    partial_update=extend_schema(
        summary="Partially update content item",
        responses={200: None},
        tags=["Course - Content"],
    ),
    destroy=extend_schema(
        summary="Delete content item", responses={204: None}, tags=["Course - Content"]
    ),
)
class CourseTabbedContentViewSet(BaseAdminViewSet):
    """CRUD operations for CourseTabbedContent (images/videos)."""

    queryset = CourseTabbedContent.objects.select_related(
        "tab__section__course__course"
    ).all()
    serializer_class = CourseTabbedContentSerializer
    permission_classes = [IsStaff]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active", "media_type", "tab"]
    search_fields = ["title", "description"]
    ordering_fields = ["order", "created_at"]
    ordering = ["tab", "order"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CourseTabbedContentCreateUpdateSerializer
        return CourseTabbedContentSerializer


# ========== Why Enrol ViewSet ==========


@extend_schema_view(
    list=extend_schema(
        summary="List why enrol sections",
        responses={200: None},
        tags=["Course - Components"],
    ),
    retrieve=extend_schema(
        summary="Retrieve why enrol section",
        responses={200: None},
        tags=["Course - Components"],
    ),
    create=extend_schema(
        summary="Create why enrol section",
        responses={201: None},
        tags=["Course - Components"],
    ),
    update=extend_schema(
        summary="Update why enrol section",
        responses={200: None},
        tags=["Course - Components"],
    ),
    partial_update=extend_schema(
        summary="Partially update why enrol section",
        responses={200: None},
        tags=["Course - Components"],
    ),
    destroy=extend_schema(
        summary="Delete why enrol section",
        responses={204: None},
        tags=["Course - Components"],
    ),
)
class WhyEnrolViewSet(BaseAdminViewSet):
    """CRUD operations for WhyEnrol sections."""

    queryset = WhyEnrol.objects.select_related("course__course").all()
    serializer_class = WhyEnrolSerializer
    permission_classes = [IsStaff]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active", "course"]
    search_fields = ["title", "text"]
    ordering_fields = ["id"]
    ordering = ["id"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return WhyEnrolCreateUpdateSerializer
        return WhyEnrolSerializer


# ========== Course Module ViewSet ==========


@extend_schema_view(
    list=extend_schema(
        summary="List course modules",
        responses={200: None},
        tags=["Course - Components"],
    ),
    retrieve=extend_schema(
        summary="Retrieve course module",
        responses={200: None},
        tags=["Course - Components"],
    ),
    create=extend_schema(
        summary="Create course module",
        responses={201: None},
        tags=["Course - Components"],
    ),
    update=extend_schema(
        summary="Update course module",
        responses={200: None},
        tags=["Course - Components"],
    ),
    partial_update=extend_schema(
        summary="Partially update course module",
        responses={200: None},
        tags=["Course - Components"],
    ),
    destroy=extend_schema(
        summary="Delete course module",
        responses={204: None},
        tags=["Course - Components"],
    ),
)
class CourseModuleViewSet(BaseAdminViewSet):
    """CRUD operations for CourseModule."""

    queryset = CourseModule.objects.select_related("course__course").all()
    serializer_class = CourseModuleSerializer
    permission_classes = [IsStaff]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active", "course"]
    search_fields = ["title", "short_description"]
    ordering_fields = ["order", "created_at"]
    ordering = ["course", "order"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CourseModuleCreateUpdateSerializer
        return CourseModuleSerializer


# ========== Key Benefit ViewSet ==========


@extend_schema_view(
    list=extend_schema(
        summary="List key benefits", responses={200: None}, tags=["Course - Components"]
    ),
    retrieve=extend_schema(
        summary="Retrieve key benefit",
        responses={200: None},
        tags=["Course - Components"],
    ),
    create=extend_schema(
        summary="Create key benefit",
        responses={201: None},
        tags=["Course - Components"],
    ),
    update=extend_schema(
        summary="Update key benefit",
        responses={200: None},
        tags=["Course - Components"],
    ),
    partial_update=extend_schema(
        summary="Partially update key benefit",
        responses={200: None},
        tags=["Course - Components"],
    ),
    destroy=extend_schema(
        summary="Delete key benefit",
        responses={204: None},
        tags=["Course - Components"],
    ),
)
class KeyBenefitViewSet(BaseAdminViewSet):
    """CRUD operations for KeyBenefit."""

    queryset = KeyBenefit.objects.select_related("course__course").all()
    serializer_class = KeyBenefitSerializer
    permission_classes = [IsStaff]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active", "course"]
    search_fields = ["title", "text"]
    ordering_fields = ["id"]
    ordering = ["id"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return KeyBenefitCreateUpdateSerializer
        return KeyBenefitSerializer


# ========== Side Image Section ViewSet ==========


@extend_schema_view(
    list=extend_schema(
        summary="List side image sections",
        responses={200: None},
        tags=["Course - Components"],
    ),
    retrieve=extend_schema(
        summary="Retrieve side image section",
        responses={200: None},
        tags=["Course - Components"],
    ),
    create=extend_schema(
        summary="Create side image section",
        responses={201: None},
        tags=["Course - Components"],
    ),
    update=extend_schema(
        summary="Update side image section",
        responses={200: None},
        tags=["Course - Components"],
    ),
    partial_update=extend_schema(
        summary="Partially update side image section",
        responses={200: None},
        tags=["Course - Components"],
    ),
    destroy=extend_schema(
        summary="Delete side image section",
        responses={204: None},
        tags=["Course - Components"],
    ),
)
class SideImageSectionViewSet(BaseAdminViewSet):
    """CRUD operations for SideImageSection."""

    queryset = SideImageSection.objects.select_related("course__course").all()
    serializer_class = SideImageSectionSerializer
    permission_classes = [IsStaff]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active", "course"]
    search_fields = ["title", "text"]
    ordering_fields = ["id"]
    ordering = ["id"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return SideImageSectionCreateUpdateSerializer
        return SideImageSectionSerializer


# ========== Success Story ViewSet ==========


@extend_schema_view(
    list=extend_schema(
        summary="List success stories",
        responses={200: None},
        tags=["Course - Components"],
    ),
    retrieve=extend_schema(
        summary="Retrieve success story",
        responses={200: None},
        tags=["Course - Components"],
    ),
    create=extend_schema(
        summary="Create success story",
        responses={201: None},
        tags=["Course - Components"],
    ),
    update=extend_schema(
        summary="Update success story",
        responses={200: None},
        tags=["Course - Components"],
    ),
    partial_update=extend_schema(
        summary="Partially update success story",
        responses={200: None},
        tags=["Course - Components"],
    ),
    destroy=extend_schema(
        summary="Delete success story",
        responses={204: None},
        tags=["Course - Components"],
    ),
)
class SuccessStoryViewSet(BaseAdminViewSet):
    """CRUD operations for SuccessStory."""

    queryset = SuccessStory.objects.select_related("course__course").all()
    serializer_class = SuccessStorySerializer
    permission_classes = [IsStaff]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active", "course"]
    search_fields = ["name", "description"]
    ordering_fields = ["id"]
    ordering = ["id"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return SuccessStoryCreateUpdateSerializer
        return SuccessStorySerializer


# ========== Course Instructor ViewSet ==========


@extend_schema_view(
    list=extend_schema(
        summary="List course instructors",
        responses={200: None},
        tags=["Course - Instructors"],
    ),
    retrieve=extend_schema(
        summary="Retrieve course instructor",
        responses={200: None},
        tags=["Course - Instructors"],
    ),
    create=extend_schema(
        summary="Assign instructor to course",
        responses={201: None},
        tags=["Course - Instructors"],
    ),
    update=extend_schema(
        summary="Update instructor assignment",
        responses={200: None},
        tags=["Course - Instructors"],
    ),
    partial_update=extend_schema(
        summary="Partially update instructor assignment",
        responses={200: None},
        tags=["Course - Instructors"],
    ),
    destroy=extend_schema(
        summary="Remove instructor from course",
        responses={204: None},
        tags=["Course - Instructors"],
    ),
)
class CourseInstructorViewSet(BaseAdminViewSet):
    """CRUD operations for CourseInstructor assignments."""

    queryset = (
        CourseInstructor.objects.select_related("course", "teacher")
        .prefetch_related("modules")
        .all()
    )
    serializer_class = CourseInstructorSerializer
    permission_classes = [IsStaff]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active", "course", "teacher", "instructor_type"]
    search_fields = ["teacher__first_name", "teacher__last_name", "course__title"]
    ordering_fields = ["assigned_date", "instructor_type"]
    ordering = ["-assigned_date"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CourseInstructorCreateUpdateSerializer
        return CourseInstructorSerializer

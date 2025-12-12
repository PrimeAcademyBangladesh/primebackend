"""Course API views."""

import django_filters
from django.core.cache import cache
from django.db.models import Count, Prefetch, Q, Exists, OuterRef
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import filters, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.parsers import MultiPartParser, FormParser
# Models
from api.models.models_course import (
    Category,
    Course,
    CourseBatch,
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
    CourseBatchCreateUpdateSerializer,
    CourseBatchSerializer,
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
        description="""
        Retrieve all active categories for course organization.
        
        **Permissions:**
        - Public users: See only active categories (`is_active=True`)
        - Staff users: See all categories including inactive ones
        
        **Frontend Usage:**
        - Course category navigation/filters
        - Homepage category sections
        - Course listing filter dropdowns
        - Megamenu category links
        
        **Response includes:**
        - `id`: Category UUID
        - `name`: Display name
        - `slug`: URL-friendly identifier
        - `description`: Category description
        - `is_active`: Visibility status
        - `show_in_megamenu`: Whether to show in navigation
        - `icon`: Optional icon identifier
        
        **Example Usage:**
        ```javascript
        // Fetch all categories for navigation
        const response = await fetch('/api/courses/categories/');
        const { data } = await response.json();
        const categories = data.results; // Array of category objects
        ```
        """,
        responses={200: CategorySerializer},
        tags=["Course - Categories"],
    ),
    retrieve=extend_schema(
        summary="Retrieve a course category by slug",
        description="""
        Get detailed information about a specific category using its slug.
        
        **Frontend Usage:**
        - Category landing pages
        - Display category details above filtered courses
        - Breadcrumb navigation context
        
        **URL Pattern:** `/api/courses/categories/{category_slug}/`
        
        **Example:**
        ```javascript
        // Get web-development category details
        const response = await fetch('/api/courses/categories/web-development/');
        const { data } = await response.json();
        console.log(data.name); // "Web Development"
        ```
        """,
        parameters=[
            OpenApiParameter(
                name="slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="URL-friendly category identifier (e.g., 'web-development', 'data-science')",
                required=True,
            )
        ],
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
        description="""
        Get paginated list of courses with batch information.
        
        **Permissions:**
        - Public: Only published & active courses
        - Staff: All courses regardless of status
        
        **Key Features:**
        - Each course includes `active_batches` array with enrollment status
        - `is_purchased` flag for authenticated users (shows if user is enrolled)
        - Optimized with select_related/prefetch_related to avoid N+1 queries
        - Cached for 10 minutes to improve performance
        
        **Filtering Options:**
        - `category`: Filter by category slug or ID
        - `status`: Filter by status (published, draft, archived)
        - `is_active`: Boolean filter for active courses
        - `search`: Search in title and short_description
        - `ordering`: Sort by title, created_at, updated_at (use `-` for descending)
        
        **Pagination:**
        - Default page size: 10 items
        - Use `?page=2` for next pages
        
        **Frontend Usage:**
        ```javascript
        // Get first page of courses
        const response = await fetch('/api/courses/');
        const { data } = await response.json();
        
        data.results.forEach(course => {
          console.log(course.title);
          console.log(course.active_batches); // Array of available batches
          console.log(course.is_purchased); // true if user enrolled
        });
        
        // Filter by category
        const webCourses = await fetch('/api/courses/?category=web-development');
        
        // Search courses
        const searchResults = await fetch('/api/courses/?search=python');
        
        // Sort by newest first
        const newest = await fetch('/api/courses/?ordering=-created_at');
        ```
        
        **Response Structure:**
        - Each course has `active_batches` field containing batches with `is_enrollment_open=True`
        - Use batch information to show "Enroll Now" buttons with batch selection
        - Check `is_purchased` to show "Continue Learning" vs "Enroll" buttons
        """,
        parameters=[
            OpenApiParameter(
                name="category",
                type=str,
                description="Filter by category slug or UUID",
                required=False,
            ),
            OpenApiParameter(
                name="status",
                type=str,
                description="Filter by status: published, draft, or archived",
                required=False,
                enum=["published", "draft", "archived"],
            ),
            OpenApiParameter(
                name="is_active",
                type=bool,
                description="Filter by active status",
                required=False,
            ),
            OpenApiParameter(
                name="search",
                type=str,
                description="Search in course title and description",
                required=False,
            ),
            OpenApiParameter(
                name="ordering",
                type=str,
                description="Sort results: title, created_at, updated_at (prefix with - for descending)",
                required=False,
            ),
            OpenApiParameter(
                name="page",
                type=int,
                description="Page number for pagination",
                required=False,
            ),
        ],
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
        description="""
        Get comprehensive course details including all batches, pricing, modules, and content.
        
        **URL Pattern:** `/api/courses/{course_slug}/`
        
        **Smart Caching Behavior:**
        - **Anonymous users**: Cached response (10 min) with sample module content only
        - **Enrolled students**: Full uncached response with complete module access
        - **Staff/Admins**: Full uncached response with all content
        
        **Response Includes:**
        - Complete course information (title, description, thumbnail, etc.)
        - `batches` array: All batches for this course with enrollment status
        - `pricing` object: Course pricing details (regular, discount, installments)
        - `detail` object: Extended course details with:
          - `modules`: Course curriculum modules
          - `content_sections`: Organized course content
          - `why_enrol`: Enrollment reasons
          - `benefits`: Key benefits
          - `success_stories`: Student testimonials
          - `instructors`: Course instructors
        - `is_purchased`: Boolean indicating if current user is enrolled (authenticated users only)
        
        **Batch Information:**
        Each batch in the `batches` array includes:
        - `batch_number`: Batch identifier
        - `start_date`, `end_date`: Batch schedule
        - `enrollment_start`, `enrollment_end`: Enrollment window
        - `is_enrollment_open`: Whether enrollment is currently open
        - `available_seats`: Remaining capacity
        - `is_full`: Whether batch is at capacity
        
        **Frontend Usage:**
        ```javascript
        // Get complete course details
        const response = await fetch('/api/courses/django-web-development/');
        const { data } = await response.json();
        
        // Display available batches
        const openBatches = data.batches.filter(b => b.is_enrollment_open);
        
        // Show enrollment button based on status
        if (data.is_purchased) {
          showButton('Continue Learning');
        } else if (openBatches.length > 0) {
          showButton('Enroll Now');
        } else {
          showButton('Notify Me');
        }
        
        // Display pricing
        console.log(`Price: $${data.pricing.regular_price}`);
        if (data.pricing.discount_price) {
          console.log(`Discount: $${data.pricing.discount_price}`);
        }
        ```
        
        **Module Access:**
        - Anonymous/Guest users: See only modules marked as `is_sample=True`
        - Enrolled students: See all modules with full content
        - Staff: See all modules regardless of enrollment
        """,
        parameters=[
            OpenApiParameter(
                name="slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="URL-friendly course identifier (e.g., 'django-web-development', 'react-masterclass')",
                required=True,
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
    parser_classes = (MultiPartParser, FormParser, JSONParser)
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
        if hasattr(self, 'action') and self.action is not None:
            try:
                # Get the action method
                action_method = getattr(self, self.action, None)
                if action_method and hasattr(action_method, 'kwargs'):
                    # Check if the action has permission_classes defined
                    action_permissions = action_method.kwargs.get('permission_classes')
                    if action_permissions is not None:
                        return [permission() for permission in action_permissions]
            except (AttributeError, KeyError, TypeError):
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
            # If the called view already returned an `api_response`-shaped payload,
            # return it directly to avoid double-wrapping.
            if isinstance(response.data, dict) and "success" in response.data and "data" in response.data:
                return response
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

        # Avoid wrapping an already-formatted api_response payload again.
        if isinstance(response.data, dict) and "success" in response.data and "data" in response.data:
            return response

        return api_response(True, f"{self.get_model_name()} retrieved successfully", response.data)

    @extend_schema(
        summary="Get courses by category",
        description="""
        Retrieve all active published courses in a specific category.
        
        **URL Pattern:** `/api/courses/category/{category_slug}/`
        
        **Permissions:** Public (AllowAny)
        
        **Use Cases:**
        - Category landing pages showing all courses in category
        - Category-specific course browsing
        - Filtered course listings by category
        
        **Response:** Paginated list of courses (same as main list endpoint)
        
        **Frontend Usage:**
        ```javascript
        // Get all web development courses
        const response = await fetch('/api/courses/category/web-development/');
        const { data } = await response.json();
        
        data.results.forEach(course => {
          console.log(course.title);
          console.log(course.active_batches); // Available batches
        });
        
        // Pagination
        const page2 = await fetch('/api/courses/category/web-development/?page=2');
        ```
        
        **Filter Behavior:**
        - Only returns courses where:
          - `category.slug` matches the provided slug
          - `category.is_active = True`
          - `course.is_active = True`
          - `course.status = 'published'`
        """,
        parameters=[
            OpenApiParameter(
                name="category_slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="Category slug identifier (e.g., 'web-development', 'data-science')",
                required=True,
            ),
            OpenApiParameter(
                name="page",
                type=int,
                description="Page number for pagination",
                required=False,
            ),
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
        description="""
        Retrieve the latest 6 published courses for homepage/featured sections.
        
        **URL Pattern:** `/api/courses/featured/`
        
        **Permissions:** Public (AllowAny)
        
        **Caching:** Response cached for 30 minutes for performance
        
        **Use Cases:**
        - Homepage featured course carousel
        - "Latest Courses" section
        - Course highlights above the fold
        
        **Response Structure:**
        ```json
        {
          "success": true,
          "message": "Featured courses retrieved successfully",
          "data": {
            "results": [
              // Array of 6 most recent published courses
            ]
          }
        }
        ```
        
        **Frontend Usage:**
        ```javascript
        // Get featured courses for homepage
        const response = await fetch('/api/courses/featured/');
        const { data } = await response.json();
        const featuredCourses = data.results;
        
        // Display in carousel/grid
        featuredCourses.forEach(course => {
          displayCourseCard(course.title, course.thumbnail, course.slug);
        });
        ```
        
        **Notes:**
        - Always returns exactly 6 courses (or fewer if less than 6 are published)
        - Sorted by creation date (newest first)
        - Only includes active, published courses
        """,
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
        description="""
        Return active categories each with up to 10 courses for homepage tabbed sections.
        
        **URL Pattern:** `/api/courses/home-categories/`
        
        **Permissions:** Public (AllowAny)
        
        **Caching:** Response cached for 15 minutes
        
        **Query Parameters:**
        - `include_all=true`: Include all published courses (default: only courses with `show_in_home_tab=True`)
        
        **Use Cases:**
        - Homepage tabbed course sections by category
        - Category-organized course browsing on landing page
        - Dynamic homepage content sections
        
        **Response Structure:**
        ```json
        {
          "success": true,
          "message": "Home categories with courses retrieved",
          "data": [
            {
              "category": {
                "id": "uuid",
                "name": "Web Development",
                "slug": "web-development",
                "icon": "fa-code"
              },
              "courses": [
                // Up to 10 courses in this category
              ]
            },
            // ... more categories
          ]
        }
        ```
        
        **Frontend Usage:**
        ```javascript
        // Get categories with courses for tabbed homepage
        const response = await fetch('/api/courses/home-categories/');
        const { data } = await response.json();
        
        // Render tabs for each category
        data.forEach(section => {
          createTab(section.category.name);
          section.courses.forEach(course => {
            displayCourseCard(course);
          });
        });
        
        // Include all courses (not just featured)
        const allCourses = await fetch('/api/courses/home-categories/?include_all=true');
        ```
        
        **Filtering Logic:**
        - Only active categories with active, published courses
        - Categories with no matching courses are excluded from response
        - Courses sorted by creation date (newest first)
        - Maximum 10 courses per category
        """,
        parameters=[
            OpenApiParameter(
                name="include_all",
                type=bool,
                description="Include all published courses instead of only courses with show_in_home_tab=True",
                required=False,
                default=False,
            ),
        ],
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
        description="""
        Return categories with minimal course information for site navigation megamenu.
        
        **URL Pattern:** `/api/courses/megamenu-nav/`
        
        **Permissions:** Public (AllowAny)
        
        **Caching:** Response cached for 1 hour (invalidated on Course/Category changes)
        
        **Use Cases:**
        - Header megamenu dropdown navigation
        - Category-based course navigation
        - Site-wide course directory
        
        **Response Structure:**
        ```json
        {
          "success": true,
          "message": "Megamenu nav retrieved",
          "data": [
            {
              "category": {
                "id": "uuid",
                "name": "Web Development",
                "slug": "web-development"
              },
              "courses": [
                {
                  "id": "uuid",
                  "title": "Django Web Development",
                  "slug": "django-web-development"
                },
                // ... up to 10 courses
              ]
            },
            // ... more categories
          ]
        }
        ```
        
        **Frontend Usage:**
        ```javascript
        // Build megamenu navigation
        const response = await fetch('/api/courses/megamenu-nav/');
        const { data } = await response.json();
        
        // Create dropdown menu structure
        data.forEach(section => {
          const dropdown = createDropdown(section.category.name);
          section.courses.forEach(course => {
            dropdown.addLink(course.title, `/courses/${course.slug}`);
          });
        });
        ```
        
        **Filtering Logic:**
        - Only categories with `show_in_megamenu=True`
        - Only courses with `show_in_megamenu=True`
        - Active and published courses only
        - Maximum 10 courses per category
        - Courses sorted by creation date (newest first)
        
        **Performance:**
        - Highly optimized with prefetch_related to avoid N+1 queries
        - Returns minimal data (only IDs, titles, and slugs)
        - Aggressively cached for fast navigation rendering
        """,
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
        description="""
        Get all modules for a specific course by course slug.
        
        **URL Pattern:** `/api/courses/{course_slug}/modules/`
        
        **Permissions:** Public (AllowAny)
        
        **Use Cases:**
        - Display course curriculum/syllabus
        - Module navigation in course player
        - Filter live classes/assignments/quizzes by module
        
        **Response Structure:**
        Each module includes:
        - `id`: Module UUID (use this for filtering content)
        - `title`: Module name
        - `description`: Module description
        - `order`: Display order (sorted)
        - `duration`: Estimated duration
        - `is_active`: Visibility status
        - `is_sample`: Whether module is available for preview
        
        **Frontend Usage:**
        ```javascript
        // Get all modules for Django course
        const response = await fetch('/api/courses/django-web-development/modules/');
        const { data } = await response.json();
        
        // Display module list
        data.forEach(module => {
          console.log(`${module.order}. ${module.title}`);
          console.log(`Duration: ${module.duration}`);
        });
        
        // Filter live classes by module
        const moduleId = data[0].id;
        const classes = await fetch(`/api/live-classes/?module=${moduleId}`);
        
        // Filter assignments by module
        const assignments = await fetch(`/api/assignments/?module=${moduleId}`);
        
        // Filter quizzes by module
        const quizzes = await fetch(`/api/quizzes/?module=${moduleId}`);
        ```
        
        **Important:**
        - Returns only active modules (`is_active=True`)
        - Modules are sorted by `order` field
        - Module UUIDs are required for filtering related content (classes, assignments, quizzes)
        - Sample modules (`is_sample=True`) are visible to all users
        
        **Error Handling:**
        - Returns 404 if course not found or not published
        """,
        parameters=[
            OpenApiParameter(
                name="course_slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="Course slug identifier (e.g., 'django-web-development')",
                required=True,
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
        summary="List course prices (Admin)",
        description="""
        **Admin Only**: Manage course pricing records.
        
        **Filtering:**
        - `?currency=USD|BDT`: Filter by currency
        - `?is_free=true`: Filter free courses
        - `?is_active=true`: Active prices only
        - `?installment_available=true`: Courses with installment options
        
        **Frontend Note:** Use course detail endpoint for public pricing info.
        """,
        responses={200: CoursePriceSerializer},
        tags=["Course - Pricing"],
    ),
    retrieve=extend_schema(
        summary="Retrieve course price (Admin)",
        description="Get specific pricing record by UUID.",
        responses={200: CoursePriceSerializer},
        tags=["Course - Pricing"],
    ),
    create=extend_schema(
        summary="Create course price (Admin)",
        description="""
        Create new pricing for a course.
        
        **Required Fields:**
        - `course`: Course UUID
        - `base_price`: Original price
        - `currency`: 'USD' or 'BDT'
        
        **Optional:**
        - `discount_price`: Discounted price
        - `is_free`: Mark as free course
        - `installment_available`: Enable installment payments
        - `installment_count`: Number of installments
        """,
        responses={201: CoursePriceCreateUpdateSerializer},
        tags=["Course - Pricing"],
    ),
    update=extend_schema(
        summary="Update course price (Admin)",
        description="Full update of course pricing.",
        responses={200: CoursePriceCreateUpdateSerializer},
        tags=["Course - Pricing"],
    ),
    partial_update=extend_schema(
        summary="Partially update course price (Admin)",
        description="Partial update of pricing fields.",
        responses={200: CoursePriceCreateUpdateSerializer},
        tags=["Course - Pricing"],
    ),
    destroy=extend_schema(
        summary="Delete course price (Admin)",
        description="Delete a course pricing record.",
        responses={204: None},
        tags=["Course - Pricing"]
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
        description="""
        Retrieve pricing information for a specific course.
        
        **URL Pattern:** `/api/courses/prices/course/{course_slug}/`
        
        **Permissions:** Public (AllowAny)
        
        **Use Cases:**
        - Display pricing on course detail page
        - Check installment availability
        - Calculate discounted prices
        
        **Frontend Usage:**
        ```javascript
        // Get pricing for Django course
        const response = await fetch('/api/courses/prices/course/django-web-development/');
        const { data } = await response.json();
        
        console.log(`Regular: $${data.base_price}`);
        if (data.discount_price) {
          console.log(`Discounted: $${data.discount_price}`);
        }
        
        if (data.installment_available) {
          const installmentAmount = data.discount_price || data.base_price;
          const perMonth = installmentAmount / data.installment_count;
          console.log(`${data.installment_count} installments of $${perMonth}`);
        }
        ```
        
        **Note:** Pricing is also included in course detail endpoint (`/api/courses/{slug}/`).
        Use this endpoint when you need only pricing without full course details.
        """,
        parameters=[
            OpenApiParameter(
                name="course_slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="Course slug identifier (e.g., 'django-web-development')",
                required=True,
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
        summary="List coupons (Admin)",
        description="""
        **Admin Only**: Manage discount coupons.
        
        **Filtering:**
        - `?discount_type=percentage|fixed`: Filter by discount type
        - `?is_active=true`: Active coupons only
        - `?apply_to_all=true`: Universal coupons vs course-specific
        - `?search=CODE123`: Search by coupon code
        
        **Frontend Note:** Public users should use `/api/courses/coupons/active/` endpoint.
        """,
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
        description="""
        Validate a coupon code for a specific course and calculate the discount.
        
        **URL Pattern:** `/api/courses/coupons/validate/` (POST)
        
        **Permissions:** Public (AllowAny)
        
        **Use Cases:**
        - Apply coupon code at checkout
        - Display discount amount before payment
        - Validate coupon before enrollment
        
        **Request Body:**
        ```json
        {
          "code": "SUMMER2024",
          "course_slug": "django-web-development"
        }
        ```
        
        **Response:**
        ```json
        {
          "success": true,
          "message": "Coupon validated successfully",
          "data": {
            "original_price": 199.99,
            "discount_amount": 50.00,
            "final_price": 149.99,
            "discount_type": "fixed",
            "discount_value": 50,
            "coupon_code": "SUMMER2024",
            "message": "Coupon applied successfully! You save USD 50.00"
          }
        }
        ```
        
        **Frontend Usage:**
        ```javascript
        // Validate coupon at checkout
        const validateCoupon = async (code, courseSlug) => {
          const response = await fetch('/api/courses/coupons/validate/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code, course_slug: courseSlug })
          });
          
          const { data } = await response.json();
          if (response.ok) {
            displayDiscount(data.discount_amount);
            updateTotal(data.final_price);
          }
        };
        ```
        
        **Validation Rules:**
        - Coupon must be active (`is_active=True`)
        - Must be within validity dates (`valid_from` to `valid_until`)
        - Must apply to the specified course (unless `apply_to_all=True`)
        - Usage limit must not be exceeded (`usage_limit`)
        
        **Error Cases:**
        - Invalid coupon code: 400 error
        - Expired coupon: 400 error with "expired" message
        - Coupon not applicable to course: 400 error
        - Usage limit exceeded: 400 error
        """,
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
        description="""
        Retrieve all currently valid and active coupons.
        
        **URL Pattern:** `/api/courses/coupons/active/`
        
        **Permissions:** Public (AllowAny)
        
        **Use Cases:**
        - Display available coupons to users
        - Show promotional codes on homepage
        - Coupon suggestion at checkout
        
        **Filtering:**
        - Only coupons with `is_active=True`
        - Current date within `valid_from` to `valid_until` range
        - Pagination enabled
        
        **Frontend Usage:**
        ```javascript
        // Get all active coupons
        const response = await fetch('/api/courses/coupons/active/');
        const { data } = await response.json();
        
        data.results.forEach(coupon => {
          console.log(`Code: ${coupon.code}`);
          console.log(`Discount: ${coupon.discount_value}${coupon.discount_type === 'percentage' ? '%' : ' USD'}`);
          console.log(`Valid until: ${coupon.valid_until}`);
          
          if (coupon.apply_to_all) {
            console.log('Applies to all courses');
          } else {
            console.log(`Applies to: ${coupon.courses.length} courses`);
          }
        });
        ```
        
        **Response Fields:**
        - `code`: Coupon code to use
        - `discount_type`: 'percentage' or 'fixed'
        - `discount_value`: Discount amount or percentage
        - `valid_from`: Start date
        - `valid_until`: Expiration date
        - `apply_to_all`: Boolean - applies to all courses
        - `courses`: Array of applicable course slugs (if not apply_to_all)
        - `usage_limit`: Maximum number of uses (null = unlimited)
        - `times_used`: Current usage count
        """,
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
        summary="List all course details (Admin)",
        description="""
        **Admin Only**: Get all CourseDetail records with nested components.
        
        CourseDetail extends Course with hero sections, content organization, and marketing components.
        Frontend typically accesses this via the main Course retrieve endpoint.
        
        **Use Cases:**
        - Admin dashboard listing
        - Bulk course detail management
        - Content audit and review
        
        **Note:** Frontend should use `/api/courses/{slug}/` to get course details,
        not this endpoint directly.
        """,
        tags=["Course - Details"],
    ),
    retrieve=extend_schema(
        summary="Retrieve course detail by ID (Admin)",
        description="""
        **Admin Only**: Get a specific CourseDetail record by its UUID.
        
        **Note:** Frontend should use `/api/courses/{slug}/` which includes
        the nested course detail information.
        """,
        tags=["Course - Details"]
    ),
    create=extend_schema(
        summary="Create course detail (Admin)",
        description="Create a new CourseDetail record linked to a Course.",
        tags=["Course - Details"]
    ),
    update=extend_schema(
        summary="Update course detail (Admin)",
        description="Full update of a CourseDetail record.",
        tags=["Course - Details"]
    ),
    partial_update=extend_schema(
        summary="Partially update course detail (Admin)",
        description="Partial update of CourseDetail fields.",
        tags=["Course - Details"]
    ),
    destroy=extend_schema(
        summary="Delete course detail (Admin)",
        description="Delete a CourseDetail record.",
        responses={204: None},
        tags=["Course - Details"]
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
    list=extend_schema(
        summary="List content sections (Admin)",
        description="""
        **Admin Only**: Manage course content sections.
        
        Content sections organize course detail page content into logical groups.
        Each section can have up to 2 tabs with multiple media items.
        
        **Use Cases:**
        - Admin content management
        - Course page structure editing
        - Content section reordering
        
        **Frontend Note:** Access sections via `/api/courses/{slug}/` in the nested
        `detail.content_sections` array.
        
        **Filtering:**
        - `?is_active=true`: Active sections only
        - `?course={uuid}`: Filter by CourseDetail UUID
        """,
        tags=["Course - Content"]
    ),
    retrieve=extend_schema(
        summary="Retrieve content section (Admin)",
        description="Get a specific content section by UUID with nested tabs and contents.",
        tags=["Course - Content"]
    ),
    create=extend_schema(
        summary="Create content section (Admin)",
        description="Create a new content section for a course detail page.",
        tags=["Course - Content"]
    ),
    update=extend_schema(
        summary="Update content section (Admin)",
        description="Full update of a content section.",
        tags=["Course - Content"]
    ),
    partial_update=extend_schema(
        summary="Partially update content section (Admin)",
        description="Partial update of content section fields.",
        tags=["Course - Content"]
    ),
    destroy=extend_schema(
        summary="Delete content section (Admin)",
        description="Delete a content section and its nested tabs/contents.",
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
    parser_classes = (MultiPartParser, FormParser, JSONParser)
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
        summary="List section tabs (Admin)",
        description="""
        **Admin Only**: Manage tabs within course content sections.
        
        **Business Rule:** Maximum 2 tabs per content section.
        
        Each tab can contain multiple media items (images/videos).
        
        **Filtering:**
        - `?section={uuid}`: Filter by content section UUID
        - `?is_active=true`: Active tabs only
        
        **Frontend Note:** Tabs are accessed via nested structure in course detail.
        """,
        responses={200: None},
        tags=["Course - Content"]
    ),
    retrieve=extend_schema(
        summary="Retrieve section tab (Admin)",
        description="Get a specific tab with its nested contents (images/videos).",
        responses={200: None},
        tags=["Course - Content"]
    ),
    create=extend_schema(
        summary="Create section tab (Admin)",
        description="Create a new tab within a content section. Max 2 tabs per section.",
        responses={201: None},
        tags=["Course - Content"]
    ),
    update=extend_schema(
        summary="Update section tab (Admin)",
        description="Full update of a section tab.",
        responses={200: None},
        tags=["Course - Content"]
    ),
    partial_update=extend_schema(
        summary="Partially update section tab (Admin)",
        description="Partial update of tab fields.",
        responses={200: None},
        tags=["Course - Content"],
    ),
    destroy=extend_schema(
        summary="Delete section tab (Admin)",
        description="Delete a tab and its nested contents.",
        responses={204: None},
        tags=["Course - Content"]
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
        summary="List tabbed content items (Admin)",
        description="""
        **Admin Only**: Manage media items (images/videos) within section tabs.
        
        Each tab can have multiple content items displayed in order.
        
        **Filtering:**
        - `?tab={uuid}`: Filter by tab UUID
        - `?media_type=image|video`: Filter by media type
        - `?is_active=true`: Active content only
        
        **Frontend Note:** Content items accessed via course detail nested structure.
        """,
        responses={200: None},
        tags=["Course - Content"],
    ),
    retrieve=extend_schema(
        summary="Retrieve content item (Admin)",
        description="Get a specific media item by UUID.",
        responses={200: None},
        tags=["Course - Content"],
    ),
    create=extend_schema(
        summary="Create content item (Admin)",
        description="Add new image or video to a tab.",
        responses={201: None},
        tags=["Course - Content"]
    ),
    update=extend_schema(
        summary="Update content item (Admin)",
        description="Full update of a media item.",
        responses={200: None},
        tags=["Course - Content"]
    ),
    partial_update=extend_schema(
        summary="Partially update content item (Admin)",
        description="Partial update of media item fields.",
        responses={200: None},
        tags=["Course - Content"],
    ),
    destroy=extend_schema(
        summary="Delete content item (Admin)",
        description="Delete a media item from a tab.",
        responses={204: None},
        tags=["Course - Content"]
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
    parser_classes = (MultiPartParser, FormParser, JSONParser)
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
        summary="List why enrol sections (Admin)",
        description="""
        **Admin Only**: Manage enrollment reason sections.
        
        These highlight key reasons to enroll in a course.
        
        **Filtering:** `?course={uuid}` - Filter by CourseDetail UUID
        
        **Frontend:** Access via `/api/courses/{slug}/` in `detail.why_enrol` array
        """,
        responses={200: None},
        tags=["Course - Components"],
    ),
    retrieve=extend_schema(
        summary="Retrieve why enrol section (Admin)",
        description="Get a specific enrollment reason by UUID.",
        responses={200: None},
        tags=["Course - Components"],
    ),
    create=extend_schema(
        summary="Create why enrol section (Admin)",
        description="Add new enrollment reason to course detail.",
        responses={201: None},
        tags=["Course - Components"],
    ),
    update=extend_schema(
        summary="Update why enrol section (Admin)",
        description="Full update of enrollment reason.",
        responses={200: None},
        tags=["Course - Components"],
    ),
    partial_update=extend_schema(
        summary="Partially update why enrol section (Admin)",
        description="Partial update of enrollment reason.",
        responses={200: None},
        tags=["Course - Components"],
    ),
    destroy=extend_schema(
        summary="Delete why enrol section (Admin)",
        description="Delete an enrollment reason.",
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
        summary="List course modules (Admin)",
        description="""
        **Admin Only**: Manage course curriculum modules.
        
        **Important:** Frontend should use `/api/courses/{slug}/modules/` instead.
        This endpoint is for admin management only.
        
        **Filtering:**
        - `?course={uuid}`: Filter by CourseDetail UUID
        - `?is_active=true`: Active modules only
        
        **Note:** Module UUIDs are used to filter live classes, assignments, and quizzes.
        """,
        responses={200: None},
        tags=["Course - Components"],
    ),
    retrieve=extend_schema(
        summary="Retrieve course module (Admin)",
        description="Get specific module with all details.",
        responses={200: None},
        tags=["Course - Components"],
    ),
    create=extend_schema(
        summary="Create course module (Admin)",
        description="Add new module to course curriculum.",
        responses={201: None},
        tags=["Course - Components"],
    ),
    update=extend_schema(
        summary="Update course module (Admin)",
        description="Full update of course module.",
        responses={200: None},
        tags=["Course - Components"],
    ),
    partial_update=extend_schema(
        summary="Partially update course module (Admin)",
        description="Partial update of module fields.",
        responses={200: None},
        tags=["Course - Components"],
    ),
    destroy=extend_schema(
        summary="Delete course module (Admin)",
        description="Delete a course module.",
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

    def get_queryset(self):
        """Override to allow filtering by Course ID/slug via 'course_id' or 'course_slug' params."""
        queryset = super().get_queryset()
        
        # Allow filtering by Course ID/slug
        course_id = self.request.query_params.get('course_id')
        course_slug = self.request.query_params.get('course_slug')
        
        if course_id:
            queryset = queryset.filter(course__course__id=course_id)
        elif course_slug:
            queryset = queryset.filter(course__course__slug=course_slug)
        
        return queryset

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CourseModuleCreateUpdateSerializer
        return CourseModuleSerializer


# ========== Key Benefit ViewSet ==========


@extend_schema_view(
    list=extend_schema(
        summary="List key benefits (Admin)",
        description="""
        **Admin Only**: Manage course key benefits.
        
        Benefits highlight what students gain from the course.
        
        **Filtering:** `?course={uuid}` - Filter by CourseDetail UUID
        
        **Frontend:** Access via `/api/courses/{slug}/` in `detail.benefits` array
        """,
        responses={200: None},
        tags=["Course - Components"]
    ),
    retrieve=extend_schema(
        summary="Retrieve key benefit (Admin)",
        description="Get a specific benefit by UUID.",
        responses={200: None},
        tags=["Course - Components"],
    ),
    create=extend_schema(
        summary="Create key benefit (Admin)",
        description="Add new benefit to course.",
        responses={201: None},
        tags=["Course - Components"],
    ),
    update=extend_schema(
        summary="Update key benefit (Admin)",
        description="Full update of course benefit.",
        responses={200: None},
        tags=["Course - Components"],
    ),
    partial_update=extend_schema(
        summary="Partially update key benefit (Admin)",
        description="Partial update of benefit.",
        responses={200: None},
        tags=["Course - Components"],
    ),
    destroy=extend_schema(
        summary="Delete key benefit (Admin)",
        description="Delete a course benefit.",
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
        summary="List side image sections (Admin)",
        description="""
        **Admin Only**: Manage side-by-side image/text sections.
        
        These display content with accompanying images.
        
        **Filtering:** `?course={uuid}` - Filter by CourseDetail UUID
        
        **Frontend:** Access via `/api/courses/{slug}/` in `detail.side_image_sections`
        """,
        responses={200: None},
        tags=["Course - Components"],
    ),
    retrieve=extend_schema(
        summary="Retrieve side image section (Admin)",
        description="Get specific side image section by UUID.",
        responses={200: None},
        tags=["Course - Components"],
    ),
    create=extend_schema(
        summary="Create side image section (Admin)",
        description="Add new side image section to course.",
        responses={201: None},
        tags=["Course - Components"],
    ),
    update=extend_schema(
        summary="Update side image section (Admin)",
        description="Full update of side image section.",
        responses={200: None},
        tags=["Course - Components"],
    ),
    partial_update=extend_schema(
        summary="Partially update side image section (Admin)",
        description="Partial update of side image section.",
        responses={200: None},
        tags=["Course - Components"],
    ),
    destroy=extend_schema(
        summary="Delete side image section (Admin)",
        description="Delete a side image section.",
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
    parser_classes = (MultiPartParser, FormParser, JSONParser)
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
        summary="List success stories (Admin)",
        description="""
        **Admin Only**: Manage student success stories/testimonials.
        
        Success stories showcase student achievements after completing courses.
        
        **Filtering:** `?course={uuid}` - Filter by CourseDetail UUID
        
        **Frontend:** Access via `/api/courses/{slug}/` in `detail.success_stories` array
        """,
        responses={200: None},
        tags=["Course - Components"],
    ),
    retrieve=extend_schema(
        summary="Retrieve success story (Admin)",
        description="Get specific success story with student details.",
        responses={200: None},
        tags=["Course - Components"],
    ),
    create=extend_schema(
        summary="Create success story (Admin)",
        description="Add new student success story/testimonial.",
        responses={201: None},
        tags=["Course - Components"],
    ),
    update=extend_schema(
        summary="Update success story (Admin)",
        description="Full update of success story.",
        responses={200: None},
        tags=["Course - Components"],
    ),
    partial_update=extend_schema(
        summary="Partially update success story (Admin)",
        description="Partial update of success story.",
        responses={200: None},
        tags=["Course - Components"],
    ),
    destroy=extend_schema(
        summary="Delete success story (Admin)",
        description="Delete a success story.",
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
    parser_classes = (MultiPartParser, FormParser, JSONParser)
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
        summary="List course instructor assignments (Admin)",
        description="""
        **Admin Only**: Manage instructor-to-course assignments.
        
        Links teachers/instructors to courses and specific modules.
        
        **Filtering:**
        - `?course={uuid}`: Filter by course UUID
        - `?teacher={uuid}`: Filter by teacher UUID
        - `?instructor_type=lead|assistant`: Filter by instructor role
        - `?is_active=true`: Active assignments only
        
        **Use Cases:**
        - Assign instructors to courses
        - Link instructors to specific modules
        - Manage instructor roles (lead vs assistant)
        
        **Frontend:** Instructor info included in course detail response.
        """,
        responses={200: None},
        tags=["Course - Instructors"],
    ),
    retrieve=extend_schema(
        summary="Retrieve instructor assignment (Admin)",
        description="Get specific instructor assignment with linked modules.",
        responses={200: None},
        tags=["Course - Instructors"],
    ),
    create=extend_schema(
        summary="Assign instructor to course (Admin)",
        description="""
        Create new instructor assignment to a course.
        
        **Required Fields:**
        - `course`: Course UUID
        - `teacher`: Teacher/Instructor UUID
        - `instructor_type`: 'lead' or 'assistant'
        
        **Optional:**
        - `modules`: Array of module UUIDs this instructor handles
        - `assigned_date`: Assignment date (defaults to now)
        """,
        responses={201: None},
        tags=["Course - Instructors"],
    ),
    update=extend_schema(
        summary="Update instructor assignment (Admin)",
        description="Full update of instructor assignment.",
        responses={200: None},
        tags=["Course - Instructors"],
    ),
    partial_update=extend_schema(
        summary="Partially update instructor assignment (Admin)",
        description="Update specific fields of instructor assignment.",
        responses={200: None},
        tags=["Course - Instructors"],
    ),
    destroy=extend_schema(
        summary="Remove instructor from course (Admin)",
        description="Delete instructor assignment from course.",
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


# ========== Course Batch ViewSet ==========

@extend_schema_view(
    list=extend_schema(
        summary="List all course batches",
        description="""Get paginated list of course batches with filtering and search.
        
        **Frontend Usage:**
        - Display all available batches across all courses
        - Filter by course, status, or batch number
        - Search by batch name, course title, or description
        
        **Query Parameters:**
        - `course` (UUID): Filter by course ID
        - `status`: Filter by status (upcoming, enrollment_open, running, completed, cancelled)
        - `is_active` (boolean): Filter by active status
        - `search`: Search in batch_name, course title, description
        - `ordering`: Sort by start_date, batch_number, created_at (prefix with - for descending)
        
        **Response includes:**
        - Full batch details with enrollment info
        - Computed fields: is_enrollment_open, available_seats, is_full
        - Related course information (title, slug)
        """,
        responses={200: CourseBatchSerializer(many=True)},
        tags=["Course - Batches"],
        parameters=[
            OpenApiParameter(name='course', type=str, description='Filter by course UUID'),
            OpenApiParameter(name='status', type=str, description='Filter by batch status'),
            OpenApiParameter(name='is_active', type=bool, description='Filter by active status'),
            OpenApiParameter(name='search', type=str, description='Search in batch name, course title, description'),
            OpenApiParameter(name='ordering', type=str, description='Order by: start_date, batch_number, created_at (prefix - for desc)'),
        ],
    ),
    retrieve=extend_schema(
        summary="Get single batch details",
        description="""Retrieve detailed information about a specific course batch by slug.
        
        **Frontend Usage:**
        - Display batch detail page
        - Show enrollment status and availability
        - Check if batch accepts enrollments
        
        **Returns:**
        - Complete batch information
        - Enrollment statistics (enrolled_students, available_seats)
        - Computed properties (is_enrollment_open, is_full)
        - Related course details
        
        **Note:** Use slug from batch list or course detail response
        """,
        responses={200: CourseBatchSerializer},
        tags=["Course - Batches"],
    ),
    create=extend_schema(
        summary="Create new course batch (Admin only)",
        description="""Create a new batch for a course.
        
        **Admin Only** - Requires staff authentication.
        
        **Required Fields:**
        - course (UUID): Course this batch belongs to
        - batch_number (int): Sequential batch number (must be unique per course)
        - start_date (date): When batch starts (YYYY-MM-DD)
        - end_date (date): When batch ends (YYYY-MM-DD)
        - max_students (int): Maximum enrollment capacity
        
        **Optional Fields:**
        - batch_name: Custom name (e.g., 'Winter 2025', 'Weekend Batch')
        - enrollment_start_date: When enrollment opens (defaults to now)
        - enrollment_end_date: When enrollment closes (defaults to start_date)
        - custom_price: Override course default price for this batch
        - status: Batch status (default: 'upcoming')
        - description: Batch-specific notes
        
        **Auto-generated:**
        - slug: Created from course slug + batch number
        - enrolled_students: Calculated from actual enrollments
        """,
        request=CourseBatchCreateUpdateSerializer,
        responses={201: CourseBatchSerializer},
        tags=["Course - Batches"],
    ),
    update=extend_schema(
        summary="Update course batch",
        responses={200: CourseBatchSerializer},
        tags=["Course - Batches"],
    ),
    partial_update=extend_schema(
        summary="Partially update course batch",
        responses={200: CourseBatchSerializer},
        tags=["Course - Batches"],
    ),
    destroy=extend_schema(
        summary="Delete course batch",
        responses={204: None},
        tags=["Course - Batches"],
    ),
)
class CourseBatchViewSet(BaseAdminViewSet):
    """CRUD operations for Course Batches.
    
    Students enroll in course batches, not courses directly.
    Each batch represents a time-bound offering of a course.
    """

    queryset = CourseBatch.objects.select_related("course").all()
    serializer_class = CourseBatchSerializer
    permission_classes = [permissions.AllowAny]  # Public can view batches
    pagination_class = StandardResultsSetPagination
    lookup_field = "slug"
    lookup_url_kwarg = "slug"
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["course", "status", "is_active", "batch_number"]
    search_fields = ["batch_name", "course__title", "description"]
    ordering_fields = ["start_date", "batch_number", "created_at"]
    ordering = ["-start_date"]

    def get_permissions(self):
        """Allow public read access, require staff for write operations."""
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsStaff()]
        return [permissions.AllowAny()]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CourseBatchCreateUpdateSerializer
        return CourseBatchSerializer

    @extend_schema(
        summary="Get batches for specific course",
        description="""Get all batches for a specific course by course slug.
        
        **Frontend Usage:**
        - Course detail page batch selection
        - Display available batches for a course
        - Show enrollment options
        
        **URL:** `/api/courses/batches/by-course/{course_slug}/`
        
        **Example:** `/api/courses/batches/by-course/django-web-development/`
        
        **Returns:**
        - Array of batches for the specified course
        - Only active batches returned
        - Sorted by start date (most recent first)
        """,
        responses={200: CourseBatchSerializer(many=True)},
        tags=["Course - Batches"],
        parameters=[
            OpenApiParameter(
                name='course_slug',
                type=str,
                location=OpenApiParameter.PATH,
                description='Course slug (e.g., django-web-development)'
            ),
        ],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="by-course/(?P<course_slug>[^/.]+)",
        permission_classes=[permissions.AllowAny],
    )
    def by_course(self, request, course_slug=None):
        """Get all batches for a specific course by course slug.
        
        Usage: GET /api/courses/batches/by-course/django-bootcamp/
        """
        try:
            course = Course.objects.get(slug=course_slug, is_active=True)
        except Course.DoesNotExist:
            return api_response(
                success=False,
                message="Course not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        batches = self.queryset.filter(course=course, is_active=True)
        serializer = self.get_serializer(batches, many=True)
        
        return api_response(
            success=True,
            message="Course batches retrieved successfully",
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )
    
    @extend_schema(
        summary="Get batches with open enrollment",
        description="""Get all batches currently accepting enrollments across all courses.
        
        **Frontend Usage:**
        - Homepage 'Enroll Now' sections
        - Browse enrollable batches
        - Filter available courses
        
        **URL:** `/api/courses/batches/enrollment-open/`
        
        **Automatically filters by:**
        - Active batches only
        - Current date within enrollment window
        - Status: 'enrollment_open' or 'upcoming'
        - Not at capacity (enrolled_students < max_students)
        - Not cancelled or completed
        
        **Returns:**
        - Array of batches ready for enrollment
        - Includes availability info (available_seats)
        - Shows enrollment deadline (enrollment_end_date)
        
        **Perfect for:** 'Available Courses' listings, enrollment widgets
        """,
        responses={200: CourseBatchSerializer(many=True)},
        tags=["Course - Batches"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="enrollment-open",
        permission_classes=[permissions.AllowAny],
    )
    def enrollment_open(self, request):
        """Get all batches currently accepting enrollments.
        
        Usage: GET /api/courses/batches/enrollment-open/
        """
        from django.utils import timezone
        now = timezone.now().date()
        
        # Get batches with open enrollment
        batches = self.queryset.filter(
            is_active=True,
            status__in=['enrollment_open', 'upcoming'],
        ).exclude(
            status='cancelled'
        ).exclude(
            status='completed'
        )
        
        # Filter by enrollment dates and capacity
        open_batches = []
        for batch in batches:
            if batch.is_enrollment_open:
                open_batches.append(batch)
        
        serializer = self.get_serializer(open_batches, many=True)
        
        return api_response(
            success=True,
            message="Open enrollment batches retrieved successfully",
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

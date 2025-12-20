from rest_framework import serializers

from api.models.models_auth import CustomUser
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
from api.serializers.serializers_helpers import CourseDetailRequiredOnCreateMixin, HTMLFieldsMixin

# ========== Category Serializers ==========


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for course categories."""

    courses_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "is_active",
            "show_in_megamenu",
            "courses_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "courses_count", "created_at", "updated_at"]

    def get_courses_count(self, obj):
        """Get count of active published courses. Uses annotated value if available."""
        if hasattr(obj, "active_courses_count"):
            return obj.active_courses_count
        return obj.courses.filter(is_active=True, status="published").count()

    def validate_name(self, value):
        """Ensure category name is unique (case-insensitive)."""
        queryset = Category.objects.filter(name__iexact=value)

        # Exclude current instance for updates
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError("A category with this name already exists.")

        return value


# ========== Nested Component Serializers ==========


class CourseTabbedContentSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Serializer for course tabbed content (supports image/video)."""

    html_fields = ["description"]

    class Meta:
        model = CourseTabbedContent
        fields = [
            "id",
            "media_type",
            "title",
            "description",
            "image",
            "video_provider",
            "video_url",
            "video_id",
            "video_thumbnail",
            "button_text",
            "button_link",
            "order",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "video_id", "created_at", "updated_at"]


class CourseSectionTabSerializer(serializers.ModelSerializer):
    """Serializer for course section tabs."""

    contents = serializers.SerializerMethodField()

    class Meta:
        model = CourseSectionTab
        fields = ["id", "tab_name", "order", "is_active", "contents"]
        read_only_fields = ["id"]

    def get_contents(self, obj):
        """Return contents ordered by newest first (-created_at)."""
        contents = obj.contents.filter(is_active=True).order_by("-created_at")
        return CourseTabbedContentSerializer(contents, many=True).data


class CourseContentSectionSerializer(serializers.ModelSerializer):
    """Serializer for course content sections."""

    tabs = CourseSectionTabSerializer(many=True, read_only=True)

    class Meta:
        model = CourseContentSection
        fields = ["id", "section_name", "order", "is_active", "tabs"]
        read_only_fields = ["id"]


class WhyEnrolSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Serializer for why enrol sections."""

    html_fields = ["text"]

    class Meta:
        model = WhyEnrol
        fields = ["id", "icon", "title", "text", "is_active"]
        read_only_fields = ["id"]


class CourseModuleMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for course modules in GET API responses.

    Returns only essential fields:
    - id: Module UUID (required for filtering assignments/quizzes/live-classes)
    - order: Module number (e.g., 1, 2, 3...)
    - title: Module title
    - short_description: 1-2 line description (plain text only)
    - is_active: Whether module is active
    """

    class Meta:
        model = CourseModule
        fields = [
            "id",
            "title",
            "slug",
            "order",
            "short_description",
            "short_description_plain",
            "is_active",
        ]
        read_only_fields = [
            "id",
            "slug",
            "order",
            "title",
            "short_description",
            "is_active",
        ]

    short_description_plain = serializers.SerializerMethodField()

    def get_short_description_plain(self, obj):
        """Return a plain-text version of `short_description` suitable for frontend previews."""
        try:
            from django.utils.html import strip_tags

            text = strip_tags(obj.short_description or "")
            return text.strip()
        except Exception:
            return ""


class CourseModuleSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Serializer for course modules."""

    html_fields = ["short_description"]
    start_date = serializers.SerializerMethodField()

    class Meta:
        model = CourseModule
        fields = [
            "id",
            "title",
            "slug",
            "short_description",
            "short_description_plain",
            "order",
            "is_active",
            "start_date",
        ]
        read_only_fields = ["id", "start_date", "slug"]

    def get_start_date(self, obj):
        """Get the earliest live class date for this module."""
        from api.models.models_module import LiveClass

        first_class = LiveClass.objects.filter(module=obj, is_active=True).order_by("scheduled_date").first()

        if first_class:
            return first_class.scheduled_date
        return None

    short_description_plain = serializers.SerializerMethodField()

    def get_short_description_plain(self, obj):
        """Return a plain-text version of `short_description` for detailed responses."""
        try:
            from django.utils.html import strip_tags

            text = strip_tags(obj.short_description or "")
            # Limit to 500 chars in detailed view to avoid huge payloads
            return text.strip()[:500]
        except Exception:
            return ""


class CourseModuleCreateUpdateSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Serializer for creating/updating course modules.
    Accepts 'course' field with Course UUID or slug.
    """

    html_fields = ["short_description"]
    course = serializers.CharField(
        write_only=True,
        help_text="Course UUID or slug.",
    )

    class Meta:
        model = CourseModule
        fields = [
            "id",
            "course",
            "title",
            "slug",
            "short_description",
            "order",
            "is_active",
        ]
        read_only_fields = ["id", "slug"]
        validators = []

    def validate_course(self, value):
        """Validate and get Course object."""
        import uuid

        from api.models.models_course import Course

        if not value:
            raise serializers.ValidationError("This field is required.")

        # Try to determine if it's a UUID or slug
        try:
            # Try parsing as UUID first
            uuid.UUID(value)
            course_obj = Course.objects.get(id=value)
        except (ValueError, Course.DoesNotExist):
            # If not a UUID, try as slug
            try:
                course_obj = Course.objects.get(slug=value)
            except Course.DoesNotExist:
                raise serializers.ValidationError(f'Course with identifier "{value}" not found.')

        # ✅ Return Course directly (not CourseDetail)
        return course_obj

    def validate(self, data):
        """Validate order uniqueness per course."""
        course = data.get("course")
        order = data.get("order")

        if course and order is not None:
            query = CourseModule.objects.filter(course=course, order=order)
            if self.instance:
                query = query.exclude(pk=self.instance.pk)

            if query.exists():
                raise serializers.ValidationError({"order": f"A module with order {order} already exists for this course."})

        return data


class KeyBenefitSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Serializer for key benefits."""

    html_fields = ["text"]

    class Meta:
        model = KeyBenefit
        fields = ["id", "icon", "title", "text", "is_active"]
        read_only_fields = ["id"]


class SideImageSectionSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Serializer for side image sections."""

    html_fields = ["text"]

    class Meta:
        model = SideImageSection
        fields = [
            "id",
            "image",
            "title",
            "text",
            "button_text",
            "button_url",
            "is_active",
        ]
        read_only_fields = ["id"]


class SuccessStorySerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Serializer for success stories."""

    html_fields = ["description"]

    class Meta:
        model = SuccessStory
        fields = ["id", "icon", "name", "description", "is_active"]
        read_only_fields = ["id"]


# ========== Course Instructor Serializers ==========


class CourseInstructorSerializer(serializers.ModelSerializer):
    """Serializer for course instructors."""

    teacher_name = serializers.CharField(source="teacher.get_full_name", read_only=True)
    teacher_email = serializers.EmailField(source="teacher.email", read_only=True)
    teacher_id = serializers.UUIDField(source="teacher.id", read_only=True)
    instructor_type_display = serializers.CharField(source="get_instructor_type_display", read_only=True)
    module_titles = serializers.SerializerMethodField()
    modules_count = serializers.SerializerMethodField()

    class Meta:
        model = CourseInstructor
        fields = [
            "id",
            "teacher",
            "teacher_id",
            "teacher_name",
            "teacher_email",
            "instructor_type",
            "instructor_type_display",
            "modules",
            "modules_count",
            "module_titles",
            "is_lead_instructor",
            "is_active",
            "assigned_date",
        ]
        read_only_fields = [
            "id",
            "teacher_id",
            "teacher_name",
            "teacher_email",
            "instructor_type_display",
            "modules_count",
            "module_titles",
            "is_lead_instructor",
            "assigned_date",
        ]

    def get_modules_count(self, obj):
        count = obj.modules.count()
        return count if count > 0 else "All modules"

    def get_module_titles(self, obj):
        if obj.modules.count() == 0:
            return []
        return list(obj.modules.values_list("title", flat=True))


class CourseInstructorCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating course instructor assignments."""

    course = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.all(),
        required=False,
        help_text="Course being assigned to.",
    )
    teacher = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.filter(role="teacher"),
        required=False,
        help_text="Teacher being assigned.",
    )

    class Meta:
        model = CourseInstructor
        fields = [
            "id",
            "course",
            "teacher",
            "modules",
            "is_lead_instructor",
            "is_active",
        ]
        read_only_fields = ["id"]

    def validate_teacher(self, value):
        """Ensure the selected user is a valid active teacher."""
        if value.role != "teacher":
            raise serializers.ValidationError("Only users with teacher role can be assigned as instructors.")
        if not value.is_active:
            raise serializers.ValidationError("Cannot assign an inactive teacher.")
        return value

    def validate(self, data):
        # ✅ REQUIRED
        data = super().validate(data)

        course = data.get("course")
        teacher = data.get("teacher")

        # ======================
        # CREATE
        # ======================
        if not self.instance:
            if not course:
                raise serializers.ValidationError({"course": "This field is required."})
            if not teacher:
                raise serializers.ValidationError({"teacher": "This field is required."})

            if CourseInstructor.objects.filter(course=course, teacher=teacher).exists():
                raise serializers.ValidationError(
                    {"teacher": f"{teacher.get_full_name()} is already assigned to this course."}
                )

        # ======================
        # UPDATE
        # ======================
        else:
            if "course" in data:
                raise serializers.ValidationError({"course": "Course cannot be changed after assignment."})
            if "teacher" in data:
                raise serializers.ValidationError({"teacher": "Teacher cannot be changed after assignment."})

        return data


# ========== Course Batch Serializers ==========


class CourseBatchSerializer(serializers.ModelSerializer):
    """Serializer for course batches (read-only, for listings)."""

    course_title = serializers.CharField(source="course.title", read_only=True)
    course_slug = serializers.CharField(source="course.slug", read_only=True)
    display_name = serializers.CharField(source="get_display_name", read_only=True)
    is_enrollment_open = serializers.BooleanField(read_only=True)
    available_seats = serializers.IntegerField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    has_installment = serializers.SerializerMethodField()
    installment_preview = serializers.SerializerMethodField()
    is_enrolled = serializers.SerializerMethodField()

    class Meta:
        model = CourseBatch
        fields = [
            "id",
            "course",
            "course_title",
            "course_slug",
            "batch_number",
            "batch_name",
            "slug",
            "display_name",
            "start_date",
            "end_date",
            "enrollment_start_date",
            "enrollment_end_date",
            "max_students",
            "enrolled_students",
            "available_seats",
            "is_full",
            "custom_price",
            "status",
            "is_active",
            "is_enrollment_open",
            "has_installment",
            "installment_preview",
            "is_enrolled",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "enrolled_students",
            "course_title",
            "course_slug",
            "display_name",
            "is_enrollment_open",
            "available_seats",
            "is_full",
            "has_installment",
            "installment_preview",
            "is_enrolled",
            "created_at",
            "updated_at",
        ]

    def get_is_enrolled(self, obj):
        """Check if the current user is enrolled in this batch."""
        request = self.context.get("request")
        if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
            return False

        try:
            from api.models.models_order import Enrollment

            return Enrollment.objects.filter(user=request.user, batch=obj, is_active=True).exists()
        except Exception:
            return False

    def get_has_installment(self, obj):
        """Check if this batch has installment payment available."""
        # Batch-specific override
        if obj.installment_available is not None:
            return obj.installment_available and obj.installment_count is not None and obj.installment_count > 0

        # Course default
        if hasattr(obj.course, "pricing") and obj.course.pricing:
            return (
                obj.course.pricing.installment_available
                and obj.course.pricing.installment_count is not None
                and obj.course.pricing.installment_count > 0
            )

        return False

    def get_installment_preview(self, obj):
        """Get installment info for this batch (batch setting overrides course setting)."""
        # Check if batch has specific installment setting
        if obj.installment_available is not None:
            # Batch overrides course setting
            if not obj.installment_available:
                return None  # Batch explicitly disabled installments

            if obj.installment_count:
                # Calculate price for this batch
                if obj.custom_price:
                    total_price = obj.custom_price
                elif hasattr(obj.course, "pricing") and obj.course.pricing:
                    total_price = obj.course.pricing.get_discounted_price()
                else:
                    return None

                per_installment = total_price / obj.installment_count
                return {
                    "available": True,
                    "count": obj.installment_count,
                    "amount": float(per_installment),
                    "total": float(total_price),
                    "description": f"Pay in {obj.installment_count} installments of ৳{per_installment:,.2f}",
                }

        # Use course default setting
        if hasattr(obj.course, "pricing") and obj.course.pricing:
            pricing = obj.course.pricing
            if pricing.installment_available and pricing.installment_count:
                total_price = obj.custom_price or pricing.get_discounted_price()
                per_installment = total_price / pricing.installment_count
                return {
                    "available": True,
                    "count": pricing.installment_count,
                    "amount": float(per_installment),
                    "total": float(total_price),
                    "description": f"Pay in {pricing.installment_count} installments of ৳{per_installment:,.2f}",
                }

        return None


class CourseBatchMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for course batches (for nested use in course lists)."""

    display_name = serializers.CharField(source="get_display_name", read_only=True)
    is_enrollment_open = serializers.BooleanField(read_only=True)
    available_seats = serializers.IntegerField(read_only=True)
    has_installment = serializers.SerializerMethodField()
    installment_preview = serializers.SerializerMethodField()
    is_enrolled = serializers.SerializerMethodField()

    class Meta:
        model = CourseBatch
        fields = [
            "id",
            "batch_number",
            "batch_name",
            "slug",
            "display_name",
            "start_date",
            "end_date",
            "status",
            "max_students",
            "enrolled_students",
            "available_seats",
            "is_enrollment_open",
            "custom_price",
            "has_installment",
            "installment_preview",
            "is_enrolled",
        ]
        read_only_fields = fields

    def get_is_enrolled(self, obj):
        """Check if the current user is enrolled in this batch."""
        request = self.context.get("request")
        if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
            return False

        try:
            from api.models.models_order import Enrollment

            return Enrollment.objects.filter(user=request.user, batch=obj, is_active=True).exists()
        except Exception:
            return False

    def get_has_installment(self, obj):
        """Check if this batch has installment payment available."""
        # Batch-specific override
        if obj.installment_available is not None:
            return obj.installment_available and obj.installment_count is not None and obj.installment_count > 0

        # Course default
        if hasattr(obj.course, "pricing") and obj.course.pricing:
            return (
                obj.course.pricing.installment_available
                and obj.course.pricing.installment_count is not None
                and obj.course.pricing.installment_count > 0
            )

        return False

    def get_installment_preview(self, obj):
        """Get installment info for this batch (batch setting overrides course setting)."""
        # Check if batch has specific installment setting
        if obj.installment_available is not None:
            # Batch overrides course setting
            if not obj.installment_available:
                return None  # Batch explicitly disabled installments

            if obj.installment_count:
                # Calculate price for this batch
                if obj.custom_price:
                    total_price = obj.custom_price
                elif hasattr(obj.course, "pricing") and obj.course.pricing:
                    total_price = obj.course.pricing.get_discounted_price()
                else:
                    return None

                per_installment = total_price / obj.installment_count
                return {
                    "available": True,
                    "count": obj.installment_count,
                    "amount": float(per_installment),
                    "total": float(total_price),
                    "description": f"Pay in {obj.installment_count} installments of ৳{per_installment:,.2f}",
                }

        # Use course default setting
        if hasattr(obj.course, "pricing") and obj.course.pricing:
            pricing = obj.course.pricing
            if pricing.installment_available and pricing.installment_count:
                total_price = obj.custom_price or pricing.get_discounted_price()
                per_installment = total_price / pricing.installment_count
                return {
                    "available": True,
                    "count": pricing.installment_count,
                    "amount": float(per_installment),
                    "total": float(total_price),
                    "description": f"Pay in {pricing.installment_count} installments of ৳{per_installment:,.2f}",
                }

        return None


class CourseBatchCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating course batches."""

    # Make fields optional for updates (required=False allows partial updates)
    max_students = serializers.IntegerField(required=False, min_value=1)
    status = serializers.ChoiceField(choices=CourseBatch.BATCH_STATUS_CHOICES, required=False)

    class Meta:
        model = CourseBatch
        fields = [
            "id",
            "course",
            "batch_number",
            "batch_name",
            "start_date",
            "end_date",
            "enrollment_start_date",
            "enrollment_end_date",
            "max_students",
            "custom_price",
            "status",
            "is_active",
            "description",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "course": {"required": False},
            "batch_number": {"required": False},
            "start_date": {"required": False},
            "end_date": {"required": False},
        }

    def validate(self, data):
        """Validate batch data."""
        course = data.get("course")
        batch_number = data.get("batch_number")
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        enrollment_end_date = data.get("enrollment_end_date")

        # Check for duplicate batch number (only on create)
        if not self.instance:
            if course and batch_number:
                if CourseBatch.objects.filter(course=course, batch_number=batch_number).exists():
                    raise serializers.ValidationError(
                        {"batch_number": f"Batch {batch_number} already exists for this course."}
                    )

        # Validate dates
        if start_date and end_date:
            if end_date <= start_date:
                raise serializers.ValidationError({"end_date": "End date must be after start date."})

        if enrollment_end_date and start_date:
            if enrollment_end_date > start_date:
                raise serializers.ValidationError(
                    {"enrollment_end_date": "Enrollment must close before or on the start date."}
                )

        return data


# ========== Course Price Serializers ==========


class CoursePriceSerializer(serializers.ModelSerializer):
    """Serializer for course pricing with computed fields."""

    effective_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, source="get_discounted_price")
    savings = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, source="get_savings")
    installment_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True, source="get_installment_amount"
    )
    is_discounted = serializers.BooleanField(read_only=True, source="is_currently_discounted")
    currency_display = serializers.CharField(source="get_currency_display", read_only=True)
    installment_preview = serializers.SerializerMethodField()

    def get_installment_preview(self, obj):
        """Generate installment preview for frontend display."""
        if not obj.installment_available or not obj.installment_count:
            return None

        total_price = obj.get_discounted_price()
        installment_amount = obj.get_installment_amount()

        return {
            "available": True,
            "count": obj.installment_count,
            "amount": float(installment_amount) if installment_amount else 0,
            "total": float(total_price),
            "description": (
                f"Pay in {obj.installment_count} installments of ৳{installment_amount:,.2f}" if installment_amount else None
            ),
        }

    class Meta:
        model = CoursePrice
        fields = [
            "id",
            "base_price",
            "currency",
            "currency_display",
            "is_free",
            "is_active",
            "discount_percentage",
            "discount_amount",
            "discount_start_date",
            "discount_end_date",
            "is_discounted",
            "effective_price",
            "savings",
            "installment_available",
            "installment_count",
            "installment_amount",
            "installment_preview",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "currency_display",
            "is_discounted",
            "effective_price",
            "savings",
            "installment_amount",
            "installment_preview",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        """Validate pricing data."""
        # Validate discount dates
        discount_start = data.get("discount_start_date")
        discount_end = data.get("discount_end_date")

        if discount_start and discount_end:
            if discount_start >= discount_end:
                raise serializers.ValidationError({"discount_end_date": "Discount end date must be after start date."})

        # Validate discount percentage
        discount_percentage = data.get("discount_percentage", 0)
        if discount_percentage > 100:
            raise serializers.ValidationError({"discount_percentage": "Discount percentage cannot exceed 100%."})

        # Validate installment settings
        installment_available = data.get("installment_available", False)
        installment_count = data.get("installment_count")

        if installment_available and not installment_count:
            raise serializers.ValidationError(
                {"installment_count": "Installment count is required when installments are available."}
            )

        if installment_count and installment_count < 2:
            raise serializers.ValidationError({"installment_count": "Installment count must be at least 2."})

        return data


class CoursePriceCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating course prices."""

    class Meta:
        model = CoursePrice
        fields = [
            "course",
            "base_price",
            "currency",
            "is_free",
            "is_active",
            "discount_percentage",
            "discount_amount",
            "discount_start_date",
            "discount_end_date",
            "installment_available",
            "installment_count",
        ]


# ========== Course Detail Serializers ==========


class CourseDetailSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Serializer for course details with all nested components (READ-ONLY for nested data)."""

    html_fields = ["hero_description"]
    hero_image = serializers.SerializerMethodField()

    # Nested read-only fields
    content_sections = CourseContentSectionSerializer(many=True, read_only=True)
    why_enrol = WhyEnrolSerializer(many=True, read_only=True)
    modules = CourseModuleSerializer(many=True, read_only=True)
    benefits = KeyBenefitSerializer(many=True, read_only=True)
    side_image_sections = SideImageSectionSerializer(many=True, read_only=True)
    success_stories = SuccessStorySerializer(many=True, read_only=True)

    # Course info
    course_title = serializers.CharField(source="course.title", read_only=True)
    course_slug = serializers.CharField(source="course.slug", read_only=True)

    class Meta:
        model = CourseDetail
        fields = [
            "id",
            "hero_image",
            "course",
            "course_title",
            "course_slug",
            "hero_text",
            "hero_description",
            "hero_button",
            "is_active",
            "content_sections",
            "why_enrol",
            "modules",
            "benefits",
            "side_image_sections",
            "success_stories",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "hero_image",
            "course_title",
            "course_slug",
            "created_at",
            "updated_at",
        ]

    def get_hero_image(self, obj):
        """Return absolute URL for course hero/header image with fallback."""
        request = self.context.get("request")

        header_image_url = None
        try:
            if hasattr(obj, "course") and obj.course.header_image:
                header_image_url = obj.course.header_image.url
        except Exception:
            header_image_url = None

        if not header_image_url:
            from django.templatetags.static import static

            header_image_url = static("default_images/default_course.webp")

        if request:
            return request.build_absolute_uri(header_image_url)
        return header_image_url


class CourseDetailCreateUpdateSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Serializer for creating/updating course details (hero section only)."""

    html_fields = ["hero_description"]

    class Meta:
        model = CourseDetail
        fields = [
            "course",
            "hero_text",
            "hero_description",
            "hero_button",
            "is_active",
        ]

    def validate_course(self, value):
        """Ensure course exists and is active."""
        if not value.is_active:
            raise serializers.ValidationError("Cannot create detail for an inactive course.")

        # Check if detail already exists (only on create)
        if not self.instance and hasattr(value, "detail"):
            raise serializers.ValidationError(
                f'Course detail already exists for "{value.title}". Use update endpoint instead.'
            )

        return value

    def validate_hero_button(self, value):
        """Validate hero button text length."""
        if len(value) > 100:
            raise serializers.ValidationError("Hero button text must be 100 characters or less.")
        return value


# ========== Nested Component Create/Update Serializers ==========


class CourseContentSectionCreateUpdateSerializer(CourseDetailRequiredOnCreateMixin, serializers.ModelSerializer):
    """Serializer for creating/updating content sections.

    IMPORTANT: Use 'course_detail' field with CourseDetail UUID.
    """

    course_detail = serializers.PrimaryKeyRelatedField(
        queryset=CourseDetail.objects.all(),
        required=False,
        help_text="UUID of CourseDetail (not Course).",
    )

    class Meta:
        model = CourseContentSection
        fields = ["id", "course_detail", "section_name", "order", "is_active"]
        read_only_fields = ["id"]

    def validate_course_detail(self, value):
        """Ensure CourseDetail exists."""
        if not hasattr(value, "course"):
            raise serializers.ValidationError("Invalid course detail reference.")
        return value

    def validate(self, data):
        """Validate order uniqueness per course."""
        data = super().validate(data)

        course_detail = data.get("course_detail") or (self.instance.course_detail if self.instance else None)
        order = data.get("order")

        if course_detail and order is not None:
            query = CourseContentSection.objects.filter(course_detail=course_detail, order=order)
            if self.instance:
                query = query.exclude(pk=self.instance.pk)

            if query.exists():
                raise serializers.ValidationError({"order": f"A section with order {order} already exists for this course."})

        return data


class CourseSectionTabCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating section tabs."""

    section = serializers.PrimaryKeyRelatedField(
        queryset=CourseContentSection.objects.all(),
        required=False,
    )

    class Meta:
        model = CourseSectionTab
        fields = ["id", "section", "tab_name", "order", "is_active"]
        read_only_fields = ["id"]

    def validate(self, data):
        # ✅ REQUIRED
        data = super().validate(data)

        # CREATE → section required
        if not self.instance and "section" not in data:
            raise serializers.ValidationError({"section": "This field is required."})

        # UPDATE → section immutable
        if self.instance and "section" in data:
            raise serializers.ValidationError({"section": "Section cannot be changed."})

        section = data.get("section") or self.instance.section
        order = data.get("order")

        # Order uniqueness per section
        if order is not None:
            qs = CourseSectionTab.objects.filter(section=section, order=order)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise serializers.ValidationError({"order": f"A tab with order {order} already exists in this section."})

        return data


class CourseTabbedContentCreateUpdateSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Serializer for creating/updating tabbed content items."""

    html_fields = ["description"]

    tab = serializers.PrimaryKeyRelatedField(
        queryset=CourseSectionTab.objects.all(),
        required=False,
    )

    class Meta:
        model = CourseTabbedContent
        fields = [
            "id",
            "tab",
            "media_type",
            "title",
            "description",
            "image",
            "video_provider",
            "video_url",
            "video_thumbnail",
            "button_text",
            "button_link",
            "order",
            "is_active",
        ]
        read_only_fields = ["id", "video_id"]

    def validate(self, data):
        # ✅ ALWAYS call super first
        data = super().validate(data)

        # ======================
        # Parent tab rules
        # ======================
        if not self.instance and "tab" not in data:
            raise serializers.ValidationError({"tab": "This field is required."})

        if self.instance and "tab" in data:
            raise serializers.ValidationError({"tab": "Tab cannot be changed."})

        # ======================
        # Media validation
        # ======================
        media_type = data.get("media_type", self.instance.media_type if self.instance else "image")

        image = data.get("image")
        video_url = data.get("video_url")
        video_provider = data.get("video_provider")
        video_thumbnail = data.get("video_thumbnail")

        if media_type == "image":
            if not image and not self.instance:
                raise serializers.ValidationError({"image": "Image is required for image media type."})

        elif media_type == "video":
            if not video_url:
                raise serializers.ValidationError({"video_url": "Video URL is required for video media type."})
            if not video_provider:
                raise serializers.ValidationError({"video_provider": "Video provider is required for video media type."})
            if not video_thumbnail and not self.instance:
                raise serializers.ValidationError({"video_thumbnail": "Video thumbnail is required for video media type."})

        # ======================
        # Order uniqueness
        # ======================
        tab = data.get("tab") or (self.instance.tab if self.instance else None)
        order = data.get("order")

        if tab and order is not None:
            qs = CourseTabbedContent.objects.filter(tab=tab, order=order)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise serializers.ValidationError({"order": f"Content with order {order} already exists in this tab."})

        return data


class WhyEnrolCreateUpdateSerializer(CourseDetailRequiredOnCreateMixin, HTMLFieldsMixin, serializers.ModelSerializer):
    """
    Serializer for creating/updating why enrol sections.
    """

    html_fields = ["text"]
    course_detail = serializers.PrimaryKeyRelatedField(
        queryset=CourseDetail.objects.all(),
        required=False,
        help_text="UUID of CourseDetail (not Course).",
    )

    class Meta:
        model = WhyEnrol
        fields = ["id", "course_detail", "icon", "title", "text", "is_active"]
        read_only_fields = ["id"]


class KeyBenefitCreateUpdateSerializer(CourseDetailRequiredOnCreateMixin, HTMLFieldsMixin, serializers.ModelSerializer):
    """
    Serializer for creating/updating key benefits.
    """

    html_fields = ["text"]
    course_detail = serializers.PrimaryKeyRelatedField(
        queryset=CourseDetail.objects.all(),
        required=False,
        help_text="UUID of CourseDetail (not Course).",
    )

    class Meta:
        model = KeyBenefit
        fields = ["id", "course_detail", "icon", "title", "text", "is_active"]
        read_only_fields = ["id"]


class SideImageSectionCreateUpdateSerializer(CourseDetailRequiredOnCreateMixin, HTMLFieldsMixin, serializers.ModelSerializer):
    """
    Serializer for creating/updating side image sections.
    """

    html_fields = ["text"]
    course_detail = serializers.PrimaryKeyRelatedField(
        queryset=CourseDetail.objects.all(),
        required=False,
        help_text="UUID of CourseDetail (not Course).",
    )

    class Meta:
        model = SideImageSection
        fields = [
            "id",
            "course_detail",
            "image",
            "title",
            "text",
            "button_text",
            "button_url",
            "is_active",
        ]
        read_only_fields = ["id"]


class SuccessStoryCreateUpdateSerializer(CourseDetailRequiredOnCreateMixin, HTMLFieldsMixin, serializers.ModelSerializer):
    """
    Serializer for creating/updating success stories.

    Rules:
    - course_detail is REQUIRED on CREATE
    - course_detail is NOT REQUIRED on UPDATE
    - course_detail CANNOT be changed after creation
    """

    html_fields = ["description"]

    course_detail = serializers.PrimaryKeyRelatedField(
        queryset=CourseDetail.objects.all(),
        required=False,
        help_text="UUID of CourseDetail (not Course).",
    )

    class Meta:
        model = SuccessStory
        fields = [
            "id",
            "course_detail",
            "icon",
            "name",
            "description",
            "is_active",
        ]
        read_only_fields = ["id"]


# ========== Course Serializers ==========


class CourseListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for course listings."""

    category = CategorySerializer(read_only=True)
    pricing = CoursePriceSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_purchased = serializers.SerializerMethodField(read_only=True)
    active_batches = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Course
        fields = [
            "id",
            "title",
            "slug",
            "short_description",
            "header_image",
            "show_in_megamenu",
            "show_in_home_tab",
            "category",
            "status",
            "status_display",
            "is_active",
            "pricing",
            "created_at",
            "updated_at",
            "is_purchased",
            "active_batches",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    def get_is_purchased(self, obj):
        """Return True if current request user is already enrolled in ANY batch of this course."""
        request = self.context.get("request")
        # If view annotated the queryset, prefer the annotated boolean
        if hasattr(obj, "is_purchased"):
            return bool(getattr(obj, "is_purchased"))

        if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
            return False
        try:
            from api.models.models_order import Enrollment

            return Enrollment.objects.filter(user=request.user, course=obj, is_active=True).exists()
        except Exception:
            return False

    def get_active_batches(self, obj):
        """Return active batches for this course with enrollment status."""
        request = self.context.get("request")
        batches = obj.batches.filter(is_active=True).order_by("start_date")[:5]
        return CourseBatchMinimalSerializer(batches, many=True, context={"request": request}).data


class CourseDetailedSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Complete serializer for course with all details."""

    html_fields = ["full_description"]

    category = CategorySerializer(read_only=True)
    pricing = CoursePriceSerializer(read_only=True)
    detail = CourseDetailSerializer(read_only=True)
    instructors = CourseInstructorSerializer(many=True, read_only=True)
    modules = serializers.SerializerMethodField()
    batches = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_purchased = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Course
        fields = [
            "id",
            "title",
            "slug",
            "short_description",
            "full_description",
            "header_image",
            "category",
            "show_in_megamenu",
            "show_in_home_tab",
            "status",
            "status_display",
            "is_active",
            "pricing",
            "detail",
            "modules",
            "instructors",
            "created_at",
            "updated_at",
            "is_purchased",
            "batches",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    def get_modules(self, obj):
        """Return minimal module information ordered by module number."""
        # Modules are now directly on the Course object
        if not hasattr(obj, "modules"):
            return []
        modules_qs = obj.modules.filter(is_active=True).order_by("order")

        sample_limit = 5
        sample_modules = modules_qs[:sample_limit]
        return CourseModuleMinimalSerializer(sample_modules, many=True).data

    def get_is_purchased(self, obj):
        """Return True if current request user is already enrolled in this course."""
        request = self.context.get("request")
        # Prefer annotated value when available (avoids per-object queries)
        if hasattr(obj, "is_purchased"):
            return bool(getattr(obj, "is_purchased"))

        if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
            return False
        try:
            from api.models.models_order import Enrollment

            return Enrollment.objects.filter(user=request.user, course=obj, is_active=True).exists()
        except Exception:
            return False

    def get_batches(self, obj):
        """Return all batches for this course."""
        batches = obj.batches.filter(is_active=True).order_by("-start_date")
        return CourseBatchSerializer(batches, many=True, context=self.context).data


class CourseCreateUpdateSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    """Serializer for creating/updating courses."""

    html_fields = ["full_description"]

    class Meta:
        model = Course
        fields = [
            "id",
            "slug",
            "category",
            "show_in_megamenu",
            "show_in_home_tab",
            "title",
            "short_description",
            "full_description",
            "header_image",
            "status",
            "is_active",
        ]
        read_only_fields = ["id", "slug"]

    def validate_category(self, value):
        """Ensure category is active."""
        if not value.is_active:
            raise serializers.ValidationError("Cannot assign course to an inactive category.")
        return value


# ========== Coupon Serializers ==========


class CouponSerializer(serializers.ModelSerializer):
    """Serializer for coupons."""

    discount_type_display = serializers.CharField(source="get_discount_type_display", read_only=True)
    is_valid_now = serializers.SerializerMethodField()
    validity_message = serializers.SerializerMethodField()
    applicable_courses = serializers.SerializerMethodField()
    coupons_remaining = serializers.SerializerMethodField()

    class Meta:
        model = Coupon
        fields = [
            "id",
            "code",
            "discount_type",
            "discount_type_display",
            "discount_value",
            "apply_to_all",
            "is_active",
            "valid_from",
            "valid_until",
            "max_uses",
            "used_count",
            "coupons_remaining",
            "max_uses_per_user",
            "is_valid_now",
            "validity_message",
            "applicable_courses",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "used_count",
            "coupons_remaining",
            "discount_type_display",
            "is_valid_now",
            "validity_message",
            "applicable_courses",
            "created_at",
            "updated_at",
        ]

    def get_is_valid_now(self, obj):
        is_valid, _ = obj.is_valid()
        return is_valid

    def get_validity_message(self, obj):
        _, message = obj.is_valid()
        return message

    def get_coupons_remaining(self, obj):
        """Get number of coupons remaining (None for unlimited)."""
        return obj.get_remaining_uses()

    def get_applicable_courses(self, obj):
        if obj.apply_to_all:
            return "All Courses"
        course_count = obj.courses.count()
        return f"{course_count} specific courses"


class CouponCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating coupons."""

    class Meta:
        model = Coupon
        fields = [
            "code",
            "discount_type",
            "discount_value",
            "courses",
            "apply_to_all",
            "max_uses",
            "max_uses_per_user",
            "is_active",
            "valid_from",
            "valid_until",
        ]

    def validate(self, data):
        """Validate coupon data."""
        # Validate date range
        valid_from = data.get("valid_from")
        valid_until = data.get("valid_until")

        if valid_from and valid_until:
            if valid_from >= valid_until:
                raise serializers.ValidationError({"valid_until": "Valid until date must be after valid from date."})

        # Validate discount value based on type
        discount_type = data.get("discount_type")
        discount_value = data.get("discount_value")

        if discount_type == "percentage" and discount_value > 100:
            raise serializers.ValidationError({"discount_value": "Percentage discount cannot exceed 100%."})

        return data


# Legacy compact megamenu serializers removed; use nav serializers for minimal payloads.


class CourseNavSerializer(serializers.ModelSerializer):
    """Very small serializer for navigation: title (and slug).

    Note: I include `slug` along with `title` because frontends often
    need a stable URL fragment to build links. If you really want
    only `title`, we can remove `slug`.
    """

    class Meta:
        model = Course
        fields = ["title", "slug"]


class CategoryNavSerializer(serializers.ModelSerializer):
    """Minimal category serializer for nav payloads."""

    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class CouponValidationSerializer(serializers.Serializer):
    """Serializer for validating coupon codes against courses."""

    code = serializers.CharField(max_length=50)
    course_id = serializers.UUIDField()

    def validate(self, data):
        """Validate that coupon exists and can be applied to course."""
        code = data["code"]
        course_id = data["course_id"]

        try:
            coupon = Coupon.objects.get(code=code)
        except Coupon.DoesNotExist:
            raise serializers.ValidationError({"code": "Invalid coupon code."})

        # Check if coupon is valid
        is_valid, message = coupon.is_valid()
        if not is_valid:
            raise serializers.ValidationError({"code": message})

        # Check if coupon applies to this course
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            raise serializers.ValidationError({"course_id": "Invalid course."})

        if not coupon.can_apply_to_course(course):
            raise serializers.ValidationError({"code": "This coupon is not applicable to the selected course."})

        # Add coupon and course to validated data for use in view
        data["coupon"] = coupon
        data["course"] = course

        return data


class CouponApplyResultSerializer(serializers.Serializer):
    """Serializer for coupon application results."""

    original_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    final_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    discount_type = serializers.CharField()
    discount_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    coupon_code = serializers.CharField()
    message = serializers.CharField()

"""URL configuration for the API app.

Registers viewsets with a router and exposes auth, profile, admin and
footer endpoints used by the frontend and by automated tests.
"""

from django.urls import path

from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from api.views.views_academy_overview import AcademyOverviewViewSet
from api.views.views_accounting import IncomeViewSet, IncomeUpdateRequestViewSet, ExpenseViewSet, \
    ExpenseUpdateRequestViewSet, PaymentMethodViewSet, IncomeTypeViewSet, ExpensePaymentMethod, \
    ExpensePaymentMethodViewSet, AccountingDashboardAPIView, TransactionsAPIView
from api.views.views_auth import (
    AdminLoginView,
    AdminStudentViewSet,
    AdminTeacherViewSet,
    CurrentUserProfileView,
    LogoutView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetView,
    RequestPhoneChangeView,
    ResendVerificationEmailView,
    SkillViewSet,
    StaffLoginView,
    StudentLoginView,
    StudentRegisterView,
    TeacherLoginView,
    VerifyEmailView, AccountantLoginView,
)
from api.views.views_blog import BlogCategoryViewSet, BlogViewSet
from api.views.views_cart import (
    add_to_cart,
    add_to_wishlist,
    cart_detail,
    clear_cart,
    move_to_cart,
    remove_from_cart,
    remove_from_wishlist,
    wishlist_detail,
)
from api.views.views_ckeditor_image_upload import CKEditorImageUploadView
from api.views.views_contact import ContactMessageViewSet
from api.views.views_course import (
    CategoryViewSet,
    CouponViewSet,
    CourseBatchViewSet,
    CourseContentSectionViewSet,
    CourseDetailViewSet,
    CourseInstructorViewSet,
    CourseModuleViewSet,
    CoursePriceViewSet,
    CourseSectionTabViewSet,
    CourseTabbedContentViewSet,
    CourseViewSet,
    KeyBenefitViewSet,
    SideImageSectionViewSet,
    SuccessStoryViewSet,
    WhyEnrolViewSet,
)
from api.views.views_custom_payment import CustomPaymentViewSet
from api.views.views_dashboard import course_details, dashboard_overview, earnings_details, student_details
from api.views.views_employee import DepartmentViewSet, EmployeeViewSet
from api.views.views_export import (
    export_course_completion_csv,
    export_course_completion_pdf,
    export_employees_csv,
    export_employees_pdf,
    export_my_order_invoice_by_number_pdf,
    export_my_order_invoice_pdf,
    export_order_invoice_pdf,
    export_orders_csv,
    export_revenue_analytics_csv,
    export_revenue_analytics_pdf,
    export_students_csv,
    export_students_pdf,
)
from api.views.views_faq import FAQViewSet
from api.views.views_footer import FooterAdminView, FooterPublicView
from api.views.views_free_enrollment import enroll_free_course
from api.views.views_home import BrandViewSet, HeroSectionViewSet
from api.views.views_invoice_verification import verify_invoice
from api.views.views_live_class_assignment_quiz import (
    AssignmentSubmissionViewSet,
    AssignmentViewSet,
    CourseResourceViewSet,
    LiveClassViewSet,
    QuizAttemptViewSet,
    QuizQuestionViewSet,
    QuizViewSet, StudentAssignmentViewSet, StudentQuizViewSet, StudentLiveClassViewSet, StudentResourceViewSet,
    StudentAttendanceViewSet
)
from api.views.views_module import CourseModuleStudyPlanView
from api.views.views_order import EnrollmentViewSet, OrderItemViewSet, OrderViewSet
from api.views.views_our_values import ValueTabContentViewSet, ValueTabSectionViewSet, ValueTabViewSet
from api.views.views_payment import (
    InstallmentPaymentInitiateView,
    InstallmentSummaryView,
    PaymentInitiateView,
    payment_cancel_redirect,
    payment_fail_redirect,
    payment_success_redirect,
    payment_webhook,
    verify_payment,
)
from api.views.views_policy import PolicyPageViewSet
from api.views.views_seo import PageSEOViewSet
from api.views.views_service import ContentSectionViewSet, PageServiceViewSet

router = DefaultRouter()

router.register(r"seo", PageSEOViewSet, basename="seo")
router.register(r"admin/students", AdminStudentViewSet, basename="admin-student")
router.register(r"admin/teachers", AdminTeacherViewSet, basename="admin-teacher")
router.register(r"hero", HeroSectionViewSet, basename="hero")
router.register(r"skills", SkillViewSet, basename="skill")
router.register(r"brands", BrandViewSet, basename="brand")
router.register(r"employees", EmployeeViewSet, basename="employee")
router.register(r"departments", DepartmentViewSet, basename="department")
router.register(r"page-services", PageServiceViewSet, basename="pageservice")
router.register(r"content-sections", ContentSectionViewSet, basename="contentsection")
router.register(r"contact", ContactMessageViewSet, basename="contact")
router.register(r"faqs", FAQViewSet, basename="faq")
router.register(r"academy-overview", AcademyOverviewViewSet, basename="academy-overview")
router.register(r"our-values/sections", ValueTabSectionViewSet, basename="valuetabsection")
router.register(r"our-values/tabs", ValueTabViewSet, basename="valuetab")
router.register(r"our-values/contents", ValueTabContentViewSet, basename="valuetabcontent")

# ========== Course System - All with 'courses/' prefix ==========
router.register(r"courses/categories", CategoryViewSet, basename="course-category")
router.register(r"courses/batches", CourseBatchViewSet, basename="course-batch")
router.register(r"courses/prices", CoursePriceViewSet, basename="course-price")
router.register(r"courses/coupons", CouponViewSet, basename="course-coupon")
router.register(r"courses/details", CourseDetailViewSet, basename="course-detail")
router.register(
    r"courses/content-sections",
    CourseContentSectionViewSet,
    basename="course-content-section",
)
router.register(r"courses/section-tabs", CourseSectionTabViewSet, basename="course-section-tab")
router.register(
    r"courses/tabbed-content",
    CourseTabbedContentViewSet,
    basename="course-tabbed-content",
)
router.register(r"courses/why-enrol", WhyEnrolViewSet, basename="course-why-enrol")
router.register(r"courses/modules", CourseModuleViewSet, basename="course-module")
router.register(r"courses/benefits", KeyBenefitViewSet, basename="course-benefit")
router.register(r"courses/side-sections", SideImageSectionViewSet, basename="course-side-section")
router.register(r"courses/success-stories", SuccessStoryViewSet, basename="course-success-story")
router.register(r"courses/instructors", CourseInstructorViewSet, basename="course-instructor")

router.register(r"orders", OrderViewSet, basename="order")
router.register(r"order-items", OrderItemViewSet, basename="orderitem")
router.register(r"enrollments", EnrollmentViewSet, basename="enrollment")
router.register(r"custom-payments", CustomPaymentViewSet, basename="custompayment")

# Live Class, Assignment, Quiz System
router.register(r"live-classes", LiveClassViewSet, basename="live-class")
router.register(r"assignments", AssignmentViewSet, basename="assignment")
router.register(
    r"assignment-submissions",
    AssignmentSubmissionViewSet,
    basename="assignment-submission",
)

# Quizzes (student + teacher)
router.register(r"quizzes", QuizViewSet, basename="quiz")

# Quiz questions (teacher/admin only)
router.register(r"quiz-questions", QuizQuestionViewSet, basename="quiz-question")

# Quiz attempts (student only, read-only)
router.register(r"quiz-attempts", QuizAttemptViewSet, basename="quiz-attempt")

# Backwards-compatible alias for frontend: `/api/resources/` -> CourseResourceViewSet
router.register(r"resources", CourseResourceViewSet, basename="resources")

# Accounting endpoints
router.register(r"income-types", IncomeTypeViewSet, basename="income-type")
router.register(r"income-payment-method", PaymentMethodViewSet, basename="income-payment-method")
router.register(r'incomes', IncomeViewSet, basename='income')
router.register(r'income-update-requests', IncomeUpdateRequestViewSet, basename='income-update-request')

router.register(r"income-types", ExpenseViewSet, basename="expense-type")
router.register(r"income-payment-method", ExpensePaymentMethodViewSet, basename="expense-payment-method")
router.register(r"expenses", ExpenseViewSet, basename="expense")
router.register(r"expense-update-requests", ExpenseUpdateRequestViewSet, basename="expense-update-request")

router.register("student/assignments", StudentAssignmentViewSet, basename="student-assignments")
router.register("student/quizzes", StudentQuizViewSet, basename="student-quizzes")
router.register("student/live-classes", StudentLiveClassViewSet, basename="student-live-classes")
router.register("student/resources", StudentResourceViewSet, basename="student-resources")
router.register("student/attendance", StudentAttendanceViewSet, basename="student-attendance")

urlpatterns = router.urls + [
    # =============================================
    # AUTHENTICATION & PROFILE ENDPOINTS
    # =============================================

    # Universal logout
    path("logout/", LogoutView.as_view(), name="logout"),
    # Student specific endpoints
    path("students/register/", StudentRegisterView.as_view(), name="student-register"),
    path("students/login/", StudentLoginView.as_view(), name="student-login"),
    path("verify-student/", VerifyEmailView.as_view(), name="verify-student"),
    path(
        "students/resend-verification/",
        ResendVerificationEmailView.as_view(),
        name="resend-verification",
    ),
    path("students/reset-password/", PasswordResetView.as_view(), name="password-reset"),
    path(
        "students/reset-password-confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path(
        "students/change-password/",
        PasswordChangeView.as_view(),
        name="student-change-password",
    ),
    # Phone change via email-confirmed flow
    path("students/update-phone/", RequestPhoneChangeView.as_view(), name="update-phone"),
    # Teacher specific endpoints
    path("teachers/login/", TeacherLoginView.as_view(), name="teacher-login"),
    path(
        "teachers/change-password/",
        PasswordChangeView.as_view(),
        name="teacher-change-password",
    ),
    # Generic current-user profile endpoint for all authenticated roles
    path("profile/", CurrentUserProfileView.as_view(), name="my-profile"),
    # Admin specific login
    path("admin/login/", AdminLoginView.as_view(), name="admin-login"),
    path("staff/login/", StaffLoginView.as_view(), name="staff-login"),
    path("accountant/login/", AccountantLoginView.as_view(), name="accountant-login"),
    path(
        "admin/change-password/",
        PasswordChangeView.as_view(),
        name="admin-change-password",
    ),
    # Jwt Token endpoints
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # =============================================
    # FOOTER ENDPOINTS
    # =============================================
    path("footer/", FooterPublicView.as_view(), name="footer-public"),
    path("admin/footer/update/", FooterAdminView.as_view(), name="footer-admin"),
    # =============================================
    # BLOG CATEGIORY ENDPOINTS
    # =============================================
    path(
        "blog-categories/",
        BlogCategoryViewSet.as_view({"get": "list", "post": "create"}),
        name="category-list",
    ),
    path(
        "blog-categories/<uuid:pk>/",
        BlogCategoryViewSet.as_view({"put": "update", "patch": "partial_update", "delete": "destroy"}),
        name="category-id-admin",
    ),
    path(
        "blog-categories/<slug:slug>/",
        BlogCategoryViewSet.as_view({"get": "retrieve"}),
        name="category-retrieve-slug",
    ),
    # =============================================
    # BLOG ENDPOINTS
    # =============================================
    path(
        "blogs/",
        BlogViewSet.as_view({"get": "list", "post": "create"}),
        name="blog-list",
    ),
    path("blogs/latest/", BlogViewSet.as_view({"get": "latest"}), name="blog-latest"),
    # ID-based update/delete must come before slug-based retrieve
    path(
        "blogs/<uuid:pk>/",
        BlogViewSet.as_view({"put": "update", "patch": "partial_update", "delete": "destroy"}),
        name="blog-id-admin",
    ),
    # Slug-based retrieve
    path(
        "blogs/<slug:slug>/",
        BlogViewSet.as_view({"get": "retrieve"}),
        name="blog-retrieve-slug",
    ),
    # =============================================
    # COURSE SYSTEM - ALL ENDPOINTS (Priority Order)
    # =============================================
    # Course Main - Custom Actions (must come BEFORE slug-based retrieve)
    path(
        "courses/featured/",
        CourseViewSet.as_view({"get": "featured"}),
        name="course-featured",
    ),
    path(
        "courses/home-categories/",
        CourseViewSet.as_view({"get": "home_categories"}),
        name="course-home-categories",
    ),
    path(
        "courses/megamenu-nav/",
        CourseViewSet.as_view({"get": "megamenu_nav"}),
        name="course-megamenu-nav",
    ),
    path(
        "courses/category/<slug:category_slug>/",
        CourseViewSet.as_view({"get": "by_category"}),
        name="course-by-category",
    ),
    # Course Main - List/Create
    path(
        "courses/",
        CourseViewSet.as_view({"get": "list", "post": "create"}),
        name="course-list",
    ),
    # Course Main - UUID admin routes (MUST come before slug routes)
    # These handle admin updates/deletes with UUID primary keys
    path(
        "courses/<uuid:pk>/",
        CourseViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="course-detail-uuid",
    ),
    # Course Main - Public slug-based routes (MUST come LAST)
    # These are placed after the UUID admin route so UUIDs don't match slug converter
    path(
        "courses/<slug:slug>/study-plan/<slug:module_slug>/",
        CourseModuleStudyPlanView.as_view(),
        name="course-module-study-plan",
    ),
    path(
        "courses/<slug:slug>/modules/",
        CourseViewSet.as_view({"get": "modules"}),
        name="course-modules-by-slug",
    ),
    path(
        "courses/<slug:slug>/",
        CourseViewSet.as_view({"get": "retrieve"}),
        name="course-retrieve-slug",
    ),
    path(
        "courses/<uuid:pk>/",
        CourseViewSet.as_view({"put": "update", "patch": "partial_update", "delete": "destroy"}),
        name="course-id-admin",
    ),
    # =============================================
    # COURSE CART & WISHLIST
    # =============================================
    path("cart/", cart_detail, name="cart-detail"),
    path("cart/add/", add_to_cart, name="cart-add"),
    path("cart/remove/<uuid:item_id>/", remove_from_cart, name="cart-remove"),
    path("cart/clear/", clear_cart, name="cart-clear"),
    path("wishlist/", wishlist_detail, name="wishlist-detail"),
    path("wishlist/add/", add_to_wishlist, name="wishlist-add"),
    path(
        "wishlist/remove/<uuid:course_id>/",
        remove_from_wishlist,
        name="wishlist-remove",
    ),
    path(
        "wishlist/move-to-cart/<uuid:course_id>/",
        move_to_cart,
        name="wishlist-move-to-cart",
    ),
    # =============================================
    # COURSE PAYMENT (SSLCommerz)
    # =============================================
    path("payment/initiate/", PaymentInitiateView.as_view(), name="payment-initiate"),
    path("payment/webhook/", payment_webhook, name="payment-webhook"),
    # POST-to-GET redirect endpoints (receive POST from SSLCommerz, redirect to frontend with GET)
    path("payment/success/", payment_success_redirect, name="payment-success-redirect"),
    path("payment/fail/", payment_fail_redirect, name="payment-fail-redirect"),
    path("payment/cancel/", payment_cancel_redirect, name="payment-cancel-redirect"),
    # Verification endpoint for frontend
    path("payment/verify/", verify_payment, name="payment-verify"),
    # COURSE INSTALLMENT RELATED API
    path(
        "installments/summary/<uuid:order_id>/",
        InstallmentSummaryView.as_view(),
        name="installment-summary",
    ),
    # =============================================
    # CKEditor Image Upload Endpoint
    # =============================================
    path(
        "ckeditor/upload/",
        CKEditorImageUploadView.as_view(),
        name="ckeditor-image-upload",
    ),
    # =============================================
    # DASHBOARD ENDPOINTS (Admin Analytics)
    # =============================================
    path("dashboard/overview/", dashboard_overview, name="dashboard-overview"),
    path(
        "dashboard/students/details/",
        student_details,
        name="dashboard-students-details",
    ),
    path("dashboard/courses/details/", course_details, name="dashboard-courses-details"),
    path(
        "dashboard/earnings/details/",
        earnings_details,
        name="dashboard-earnings-details",
    ),
    # =============================================
    # DATA EXPORT ENDPOINTS
    # =============================================
    # Student exports
    path("export/students/csv/", export_students_csv, name="export-students-csv"),
    path("export/students/pdf/", export_students_pdf, name="export-students-pdf"),
    # Employee exports
    path("export/employees/csv/", export_employees_csv, name="export-employees-csv"),
    path("export/employees/pdf/", export_employees_pdf, name="export-employees-pdf"),
    # Order exports
    path("export/orders/csv/", export_orders_csv, name="export-orders-csv"),
    path(
        "export/orders/<uuid:order_id>/invoice/",
        export_order_invoice_pdf,
        name="export-order-invoice",
    ),
    # Student's own invoice download
    path(
        "export/my-orders/<uuid:order_id>/invoice/",
        export_my_order_invoice_pdf,
        name="export-my-order-invoice",
    ),
    path(
        "export/my-orders/<str:order_number>/invoice/",
        export_my_order_invoice_by_number_pdf,
        name="export-my-order-invoice-by-number",
    ),
    # Course completion reports
    path(
        "export/course-completion/csv/",
        export_course_completion_csv,
        name="export-course-completion-csv",
    ),
    path(
        "export/course-completion/pdf/",
        export_course_completion_pdf,
        name="export-course-completion-pdf",
    ),
    # Revenue & sales analytics
    path(
        "export/revenue-analytics/csv/",
        export_revenue_analytics_csv,
        name="export-revenue-analytics-csv",
    ),
    path(
        "export/revenue-analytics/pdf/",
        export_revenue_analytics_pdf,
        name="export-revenue-analytics-pdf",
    ),

    # Accounting dashboard endpoint
    path("accounting/dashboard/", AccountingDashboardAPIView.as_view(), name="accounting-dashboard"),
    path("accounting/transactions/", TransactionsAPIView.as_view(), name="accounting-transactions"),

    # =============================================
    # POLICY PAGES ENDPOINTS
    # =============================================
    # List and create policy pages
    path(
        "policy-pages/",
        PolicyPageViewSet.as_view({"get": "list", "post": "create"}),
        name="policy-pages-list",
    ),
    # UUID-based operations for admin (update, partial_update, delete)
    path(
        "policy-pages/<uuid:pk>/",
        PolicyPageViewSet.as_view({"put": "update", "patch": "partial_update", "delete": "destroy"}),
        name="policy-pages-admin",
    ),
    # Page name-based retrieval (public access using page_name)
    path(
        "policy-pages/<slug:page_name>/",
        PolicyPageViewSet.as_view({"get": "retrieve"}),
        name="policy-pages-retrieve",
    ),
    # Alternative endpoint for explicit page name access
    path(
        "policy-pages/by-name/<slug:page_name>/",
        PolicyPageViewSet.as_view({"get": "by_page_name"}),
        name="policy-pages-by-name",
    ),
    path("enroll-free/", enroll_free_course, name="enroll_free_course"),
    path("orders/verify/<str:order_number>", verify_invoice, name="verify_invoice"),

]

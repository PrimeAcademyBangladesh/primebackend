# api/filters/blog_filters.py
import django_filters

from api.models.models_auth import CustomUser, Skill
from api.models.models_blog import Blog, BlogCategory


class BlogFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(
        field_name='category__slug',
        lookup_expr='iexact'
    )

    class Meta:
        model = Blog
        fields = ['category']



class UserFilter(django_filters.FilterSet):
    """FilterSet for admin user list endpoints.

    Allows filtering users by role, active/enabled flags, date_joined range,
    email/student_id/phone substring matches, profile.education substring,
    and filtering by associated skills.
    """

    role = django_filters.CharFilter(field_name='role', lookup_expr='iexact')
    is_active = django_filters.BooleanFilter(field_name='is_active')
    is_enabled = django_filters.BooleanFilter(field_name='is_enabled')
    date_joined = django_filters.DateFromToRangeFilter(field_name='date_joined')
    email = django_filters.CharFilter(field_name='email', lookup_expr='icontains')
    student_id = django_filters.CharFilter(field_name='student_id', lookup_expr='icontains')
    phone = django_filters.CharFilter(field_name='phone', lookup_expr='icontains')
    profile_education = django_filters.CharFilter(
        field_name='profile__education', lookup_expr='icontains'
    )
    # Allow filtering by one or more skill ids (profile__skills)
    skills = django_filters.ModelMultipleChoiceFilter(
        field_name='profile__skills', queryset=Skill.objects.all(), to_field_name='id'
    )

    class Meta:
        model = CustomUser
        fields = [
            'role', 'is_active', 'is_enabled', 'date_joined', 'email',
            'student_id', 'phone', 'profile_education', 'skills'
        ]


class ContactMessageFilter(django_filters.FilterSet):
    """FilterSet for contact messages used by admin endpoints.

    Provides a date range filter on `created_at` so callers can query messages
    within a specific period.
    """

    created_at = django_filters.DateFromToRangeFilter(field_name='created_at')

    class Meta:
        model = None  # set by views to avoid import cycles
        fields = ['created_at']


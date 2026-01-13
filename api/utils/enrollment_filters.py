from api.models.models_order import Enrollment


def get_student_enrollment_scope(user):
    """
    Returns (batch_ids, course_ids) for an enrolled student.
    If user is not a student or has no enrollments, returns (None, None).
    """

    if not user or not user.is_authenticated:
        return None, None

    if getattr(user, "role", None) != "student":
        return None, None

    enrollments = Enrollment.objects.filter(
        user=user,
        is_active=True,
    ).select_related("batch", "course")

    if not enrollments.exists():
        return None, None

    batch_ids = enrollments.values_list("batch_id", flat=True)
    course_ids = enrollments.values_list("course_id", flat=True)

    return batch_ids, course_ids


def filter_queryset_for_student(queryset, user, *, batch_field="batch_id", course_field=None):
    """
    Applies enrollment-based filtering to a queryset.

    Parameters:
    - queryset: Django queryset
    - user: request.user
    - batch_field: field name for batch FK (default: batch_id)
    - course_field: optional field name for course FK (e.g. module__course_id)

    Returns:
    - filtered queryset
    """

    batch_ids, course_ids = get_student_enrollment_scope(user)

    # Non-students or no enrollment → no filtering
    if batch_ids is None:
        return queryset

    filters = {f"{batch_field}__in": batch_ids}

    if course_field:
        filters[f"{course_field}__in"] = course_ids

    return queryset.filter(**filters)

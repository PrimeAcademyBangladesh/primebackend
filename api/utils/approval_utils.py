from decimal import Decimal

from rest_framework import status

from api.permissions import IsAccountant
from api.utils.response_utils import api_response


# ============================================================
# Helper: serialize validated data for JSONField
# ============================================================
def serialize_validated_data(validated_data):
    serialized = {}
    for key, value in validated_data.items():
        if value is None:
            serialized[key] = None
        elif isinstance(value, Decimal):
            serialized[key] = str(value)
        elif hasattr(value, "isoformat"):
            serialized[key] = value.isoformat()
        elif hasattr(value, "pk"):
            serialized[key] = value.pk
        else:
            serialized[key] = value
    return serialized

# ============================================================
# Shared Approval Workflow for Updates
# ============================================================

def handle_update_with_approval(
    *,
    request,
    instance,
    serializer,
    update_request_model,
    success_message,
):
    """
    Shared approval workflow for Income & Expense updates.

    Accountant:
        → creates update request
    Admin:
        → updates directly
    """

    # 🔒 Block if pending request exists
    if getattr(instance, "has_pending_request", False):
        return api_response(
            success=False,
            message="An update request is already pending approval",
            status_code=status.HTTP_409_CONFLICT,
        )

    # 👤 Accountant → create update request
    if IsAccountant().has_permission(request, None):
        req = update_request_model.objects.create(
            **{instance._meta.model_name: instance},
            requested_by=request.user,
            requested_data=serialize_validated_data(serializer.validated_data),
        )

        return api_response(
            success=True,
            message="Update request submitted for admin approval",
            data={"request_id": str(req.id)},
            status_code=status.HTTP_202_ACCEPTED,
        )

    # 🛡 Admin → direct update
    serializer.save()

    return api_response(
        success=True,
        message=success_message,
    )

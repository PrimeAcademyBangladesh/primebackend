from rest_framework import serializers

from api.models.models_policy_pages import PolicyPage
from api.serializers.serializers_helpers import HTMLFieldsMixin


class PolicyPageSerializer(HTMLFieldsMixin, serializers.ModelSerializer):
    html_fields = ["content"]

    class Meta:
        model = PolicyPage
        fields = ["id", "page_name", "title", "content", "is_active"]
        read_only_fields = ["id"]

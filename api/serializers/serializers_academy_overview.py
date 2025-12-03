from rest_framework import serializers

from api.models.models_academy_overview import AcademyOverview


class AcademyOverviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademyOverview
        fields = [
            "id",
            "title",
            "description",
            "learners_count",
            "learners_short",
            "partners_count",
            "partners_short",
            "outstanding_title",
            "outstanding_short",
            "partnerships_title",
            "partnerships_short",
            "button_text",
            "button_url",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate_learners_count(self, value):
        if value < 0:
            raise serializers.ValidationError("learners_count must be non-negative")
        return value

    def validate_partners_count(self, value):
        if value < 0:
            raise serializers.ValidationError("partners_count must be non-negative")
        return value

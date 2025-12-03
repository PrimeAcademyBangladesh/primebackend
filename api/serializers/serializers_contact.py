from rest_framework import serializers

from api.models.models_contact import ContactMessage


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = [
            'id',
            'first_name',
            'last_name',
            'email',
            'phone',
            'message',
            'agree_to_policy',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        
    def validate_agree_to_policy(self, value):
        if not value:
            raise serializers.ValidationError("You must agree to the privacy policy.")
        return value

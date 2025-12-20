from rest_framework import serializers

from api.models.models_faq import FAQ, FAQItem


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ["id", "question", "answer", "order", "is_active"]
        read_only_fields = ["id"]


class FAQItemSerializer(serializers.ModelSerializer):
    faqs = FAQSerializer(many=True, required=False)
    faq_nav_order = serializers.IntegerField(source="order", required=False)

    class Meta:
        model = FAQItem
        fields = ["id", "title", "faq_nav", "faq_nav_slug", "faq_nav_order", "is_active", "faqs"]
        read_only_fields = ["faq_nav_slug"]

    def create(self, validated_data):
        faqs_data = validated_data.pop("faqs", [])
        item = FAQItem.objects.create(**validated_data)

        for faq_data in faqs_data:
            FAQ.objects.create(item=item, **faq_data)
        return item

    def update(self, instance, validated_data):
        faqs_data = validated_data.pop("faqs", [])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if faqs_data:
            instance.faqs.all().delete()
            for faq_data in faqs_data:
                FAQ.objects.create(item=instance, **faq_data)

        return instance


# from django.utils.html import strip_tags
# from rest_framework import serializers

# from api.models.models_faq import FAQ, FAQItem


# class FAQItemSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = FAQItem
#         fields = [
#             "id",
#             "title",
#             "faq_nav",
#             "faq_nav_slug",
#             "order",
#             "is_active",
#             "created_at",
#             "updated_at",
#         ]
#         read_only_fields = ["id", "created_at", "updated_at", "faq_nav_slug"]


# class FAQSerializer(serializers.ModelSerializer):
#     item = FAQItemSerializer(read_only=True)
#     item_id = serializers.PrimaryKeyRelatedField(
#         queryset=FAQItem.objects.all(), source="item", write_only=True
#     )

#     class Meta:
#         model = FAQ
#         fields = [
#             "id",
#             "item",
#             "item_id",
#             "question",
#             "answer",
#             "order",
#             "is_active",
#             "created_at",
#             "updated_at",
#         ]
#         read_only_fields = ["id", "created_at", "updated_at"]

#     def validate(self, data):
#         question_text = strip_tags(data.get("question", "")).strip()
#         answer_text = strip_tags(data.get("answer", "")).strip()

#         if not question_text:
#             raise serializers.ValidationError({"question": "Question cannot be empty."})
#         if not answer_text:
#             raise serializers.ValidationError({"answer": "Answer cannot be empty."})

#         return data

#     def to_representation(self, instance):
#         ret = super().to_representation(instance)
#         # Convert HTML-empty strings to None
#         if not strip_tags(ret.get("question", "")).strip():
#             ret["question"] = None
#         if not strip_tags(ret.get("answer", "")).strip():
#             ret["answer"] = None

#         request = self.context.get('request') if hasattr(self, 'context') else None
#         if ret.get('answer'):
#             from api.utils.ckeditor_paths import absolutize_media_urls
#             try:
#                 ret['answer'] = absolutize_media_urls(ret['answer'], request)
#             except Exception:
#                 pass
#         return ret

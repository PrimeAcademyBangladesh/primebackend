import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.html import strip_tags
from django.utils.text import slugify

from django_ckeditor_5.fields import CKEditor5Field

from api.utils.helper_models import TimeStampedModel


class FAQItem(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    faq_nav = models.CharField(max_length=100)
    faq_nav_slug = models.SlugField(max_length=100, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["faq_nav", "order", "created_at"]
        verbose_name_plural = "FAQ Items"

    def __str__(self):
        return f"{self.faq_nav} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.faq_nav_slug and self.faq_nav:
            self.faq_nav_slug = slugify(self.faq_nav)
        super().save(*args, **kwargs)


class FAQ(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(FAQItem, on_delete=models.CASCADE, related_name="faqs")
    question = models.TextField(blank=False, null=False)
    answer = CKEditor5Field(blank=False, null=False)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["item", "order", "created_at"]

    def clean(self):
        super().clean()
        question_text = strip_tags(self.question or "").strip()
        answer_text = strip_tags(self.answer or "").strip()

        errors = {}
        if not question_text:
            errors["question"] = "Question cannot be empty."
        if not answer_text:
            errors["answer"] = "Answer cannot be empty."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return strip_tags(self.question)[:100] if self.question else f"FAQ {self.id}"


# import uuid

# from django.core.exceptions import ValidationError
# from django.db import models
# from django.utils.html import strip_tags
# from django.utils.text import slugify
# from django_ckeditor_5.fields import CKEditor5Field
# from api.utils.helper_models import TimeStampedModel


# class FAQItem(TimeStampedModel):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     title = models.CharField(max_length=200)
#     faq_nav = models.CharField(max_length=100)
#     faq_nav_slug = models.SlugField(max_length=100, blank=True)
#     order = models.PositiveIntegerField(default=0)
#     is_active = models.BooleanField(default=True)

#     class Meta:
#         ordering = ['faq_nav', 'order', 'created_at']
#         verbose_name_plural = "FAQ Items"

#     def __str__(self):
#         return f"{self.faq_nav} - {self.title}"

#     def save(self, *args, **kwargs):
#         if not self.faq_nav_slug and self.faq_nav:
#             self.faq_nav_slug = slugify(self.faq_nav)
#         super().save(*args, **kwargs)


# class FAQ(TimeStampedModel):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     item = models.ForeignKey(FAQItem, on_delete=models.CASCADE, related_name='faqs')
#     question = models.TextField(
#         blank=False,
#         null=False,
#         help_text="Write your FAQ question here.",
#     )
#     answer = CKEditor5Field(
#         blank=False,
#         null=False,
#         help_text="Write your FAQ answer here.",
#     )
#     order = models.PositiveIntegerField(default=0)
#     is_active = models.BooleanField(default=True)

#     class Meta:
#         ordering = ['item', 'order', 'created_at']

#     def clean(self):
#         super().clean()  # call parent clean in case TimeStampedModel adds validation
#         question_text = strip_tags(self.question or "").strip()
#         answer_text = strip_tags(self.answer or "").strip()

#         errors = {}
#         if not question_text:
#             errors["question"] = "Question cannot be empty."
#         if not answer_text:
#             errors["answer"] = "Answer cannot be empty."

#         if errors:
#             raise ValidationError(errors)

#     def save(self, *args, **kwargs):
#         self.full_clean()  # runs clean() before save
#         super().save(*args, **kwargs)

#     def __str__(self):
#         plain_text = strip_tags(self.question).strip()
#         return plain_text[:100] if plain_text else f"FAQ {self.id}"

#     def get_question_preview(self):
#         return strip_tags(self.question)[:100] if self.question else ""

#     def get_answer_preview(self):
#         return strip_tags(self.answer)[:150] if self.answer else ""

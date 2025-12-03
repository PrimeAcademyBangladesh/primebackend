import uuid

from django.db import models

from api.utils.helper_models import TimeStampedModel


class ContactMessage(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, null=True)
    message = models.TextField()
    agree_to_policy = models.BooleanField(default=False)


    class Meta:
        verbose_name = "Contact Message"
        verbose_name_plural = "Contact Messages"
        ordering = ['-created_at'] 
        
    def __str__(self):
        return f"Message from {self.first_name} {self.last_name}"
from django.db import models

from api.utils.helper_models import TimeStampedModel  # optional if you have it


class AcademyOverview(TimeStampedModel):
    title = models.CharField(max_length=100, default="Get to Know Us")
    description = models.TextField()

    learners_count = models.PositiveIntegerField(default=0)
    learners_short = models.CharField(max_length=150, blank=True, null=True)
    
    partners_count = models.PositiveIntegerField(default=0)
    partners_short = models.CharField(max_length=150, blank=True, null=True)

    outstanding_title = models.CharField(max_length=50, blank=True, null=True)
    outstanding_short = models.CharField(max_length=150, blank=True, null=True)

    partnerships_title = models.CharField(max_length=50, blank=True, null=True)
    partnerships_short = models.CharField(max_length=150, blank=True, null=True)
    
    button_text = models.CharField(max_length=100, default="Explore Prime Academy")
    button_url = models.CharField(max_length=150, blank=True, null=True)
    
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Academy Overview"
        verbose_name_plural = "Academy Overview"

    def __str__(self):
        return self.title

"""Signal handlers for user profiles and footer cache management.

Keep cache in sync when footer/link/social models change and ensure
profiles are created for new users.
"""

import logging
import os

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from api.models.models_course import (
    Category,
    Course,
    CourseContentSection,
    CourseDetail,
    CourseModule,
    CourseSectionTab,
    CourseTabbedContent,
    KeyBenefit,
    SideImageSection,
    SuccessStory,
    WhyEnrol,
)
from api.models.models_footer import Footer, LinkGroup, QuickLink, SocialLink
from api.models.models_pricing import CoursePrice
from api.utils.cache_utils import clear_category_caches, clear_course_caches

from .models import Profile

logger = logging.getLogger(__name__)

# -----------------------------
# User Profile related signals
# -----------------------------


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    # Skip if created from admin inline
    if created and not getattr(instance, "_created_from_admin", False):
        Profile.objects.create(user=instance)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_profile(sender, instance, **kwargs):
    # Skip if from admin inline
    if getattr(instance, "_created_from_admin", False):
        return

    try:
        instance.profile.save()
    except Profile.DoesNotExist:
        Profile.objects.create(user=instance)


# -----------------------------
# Footer related signals
# -----------------------------

CACHE_KEY = "footer_api_response"

MEGAMENU_NAV_CACHE_KEY = "megamenu_nav_v1"


def clear_megamenu_cache():
    """Clear cached compact megamenu payload (legacy support)."""
    try:
        # Clear the nav cache key (legacy)
        cache.delete(MEGAMENU_NAV_CACHE_KEY)
    except Exception:
        logger.exception("Failed to clear megamenu cache")


def clear_footer_cache():
    """Clear cached footer response."""
    cache.delete(CACHE_KEY)


def touch_footer(footer: Footer):
    """Update footer timestamp + clear cache."""
    Footer.objects.filter(pk=footer.pk).update()
    clear_footer_cache()


@receiver([post_save, post_delete], sender=LinkGroup)
def update_footer_on_group_change(sender, instance, **kwargs):
    touch_footer(instance.footer)


@receiver([post_save, post_delete], sender=QuickLink)
def update_footer_on_link_change(sender, instance, **kwargs):
    touch_footer(instance.group.footer)


@receiver([post_save, post_delete], sender=SocialLink)
def update_footer_on_social_change(sender, instance, **kwargs):
    touch_footer(instance.footer)


@receiver([post_save, post_delete], sender=Footer)
def update_footer_on_footer_change(sender, instance, **kwargs):
    clear_footer_cache()


# ---------------------------
# Delete old file on update
# ---------------------------
# ---------------------------
# Generic file cleanup
# ---------------------------


def delete_file(path):
    if path and os.path.isfile(path):
        os.remove(path)


@receiver(pre_save)
def auto_delete_file_on_change(sender, instance, **kwargs):
    """
    Deletes old file from filesystem
    when a FileField/ImageField is updated.
    """
    # Only act on models with FileField/ImageField
    file_fields = [f for f in sender._meta.get_fields() if isinstance(f, models.FileField)]
    if not file_fields:
        return

    if not instance.pk:
        return  # new instance, nothing to delete

    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    for field in file_fields:
        old_file = getattr(old_instance, field.name)
        new_file = getattr(instance, field.name)
        if old_file and old_file != new_file:
            delete_file(old_file.path)


@receiver(post_delete)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    """
    Deletes all FileField/ImageField files from filesystem
    when a model instance is deleted.
    """
    file_fields = [f for f in sender._meta.get_fields() if isinstance(f, models.FileField)]
    for field in file_fields:
        file = getattr(instance, field.name)
        if file:
            delete_file(file.path)


# Blacklist outstanding JWT refresh tokens when a user is deleted.
# This ensures that if a user account is removed, any active refresh tokens
# cannot be used to obtain new access tokens.
@receiver(pre_save, sender=settings.AUTH_USER_MODEL)
def _noop_pre_save_user(sender, instance, **kwargs):
    # placeholder to keep signal ordering explicit; real blacklist runs on pre_delete
    return


@receiver(post_delete, sender=settings.AUTH_USER_MODEL)
def _noop_post_delete_user(sender, instance, **kwargs):
    # placeholder; actual blacklisting is performed in pre_delete to ensure
    # OutstandingToken objects are still available.
    return


@receiver(models.signals.pre_delete, sender=settings.AUTH_USER_MODEL)
def blacklist_user_tokens_on_delete(sender, instance, **kwargs):
    try:
        # Import locally to avoid hard dependency if token_blacklist not installed
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
    except Exception:
        # Token blacklist not available in this environment; nothing to do.
        logger.debug("token_blacklist app not available; skipping token blacklist on user delete")
        return

    try:
        # Query outstanding tokens for this user and blacklist each one.
        tokens = OutstandingToken.objects.filter(user_id=instance.pk)
        for t in tokens:
            try:
                BlacklistedToken.objects.get_or_create(token=t)
            except Exception:
                # Log and continue - blacklisting should be best-effort
                logger.exception(f"Failed to blacklist token {getattr(t, 'jti', '<unknown>')} for deleted user {instance}")
    except Exception:
        logger.exception("Error while attempting to blacklist tokens for deleted user")

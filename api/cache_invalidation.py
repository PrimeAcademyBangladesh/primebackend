"""
Django signals for automatic cache invalidation.

Automatically clears relevant caches when models are updated.
"""

from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from api.models.models_academy_overview import AcademyOverview
from api.models.models_blog import Blog, BlogCategory
from api.models.models_course import Category, Course, CourseDetail
from api.models.models_faq import FAQ
from api.models.models_pricing import Coupon, CoursePrice
from api.utils.cache_utils import (
    clear_academy_caches,
    clear_blog_caches,
    clear_category_caches,
    clear_course_caches,
    clear_course_detail_cache,
    clear_faq_caches,
)

# ========== Course Cache Invalidation ==========


@receiver([post_save, post_delete], sender=Course)
def invalidate_course_cache(sender, instance, **kwargs):
    """Clear course caches when course is created, updated, or deleted."""
    clear_course_caches()

    # Clear specific course detail cache
    if hasattr(instance, "slug"):
        clear_course_detail_cache(instance.slug)


@receiver([post_save, post_delete], sender=CourseDetail)
def invalidate_course_detail_cache(sender, instance, **kwargs):
    """Clear course caches when course details are updated."""
    clear_course_caches()

    # Clear specific course cache
    if hasattr(instance, "course") and hasattr(instance.course, "slug"):
        clear_course_detail_cache(instance.course.slug)


@receiver([post_save, post_delete], sender=CoursePrice)
def invalidate_course_price_cache(sender, instance, **kwargs):
    """Clear course caches when pricing is updated."""
    clear_course_caches()

    # Clear specific course cache
    if hasattr(instance, "course") and hasattr(instance.course, "slug"):
        clear_course_detail_cache(instance.course.slug)


# ========== Category Cache Invalidation ==========


@receiver([post_save, post_delete], sender=Category)
def invalidate_category_cache(sender, instance, **kwargs):
    """Clear category and course caches when category is updated."""
    clear_category_caches()
    clear_course_caches()  # Courses include category data


# ========== Coupon Cache Invalidation ==========


@receiver([post_save, post_delete], sender=Coupon)
def invalidate_coupon_cache(sender, instance, **kwargs):
    """Clear course caches when coupons are updated (affects pricing display)."""
    # Only clear if coupon is for all courses or affects multiple courses
    if instance.apply_to_all:
        clear_course_caches()


@receiver(m2m_changed, sender=Coupon.courses.through)
def invalidate_coupon_courses_cache(sender, instance, **kwargs):
    """Clear cache when coupon-course relationship changes."""
    if isinstance(instance, Coupon) and instance.apply_to_all:
        clear_course_caches()


# ========== Blog Cache Invalidation ==========


@receiver([post_save, post_delete], sender=Blog)
def invalidate_blog_cache(sender, instance, **kwargs):
    """Clear blog caches when blog is created, updated, or deleted."""
    clear_blog_caches()


@receiver([post_save, post_delete], sender=BlogCategory)
def invalidate_blog_category_cache(sender, instance, **kwargs):
    """Clear blog caches when blog category is updated."""
    clear_blog_caches()


# ========== FAQ Cache Invalidation ==========


@receiver([post_save, post_delete], sender=FAQ)
def invalidate_faq_cache(sender, instance, **kwargs):
    """Clear FAQ caches when FAQ is created, updated, or deleted."""
    clear_faq_caches()


# ========== Academy Overview Cache Invalidation ==========


@receiver([post_save, post_delete], sender=AcademyOverview)
def invalidate_academy_cache(sender, instance, **kwargs):
    """Clear academy overview caches when content is updated."""
    clear_academy_caches()

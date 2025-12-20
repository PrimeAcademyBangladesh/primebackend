"""
Management command to clear all application caches.

Usage:
    python manage.py clear_cache
    python manage.py clear_cache --cache-type course
    python manage.py clear_cache --cache-type all
"""

from django.core.cache import cache
from django.core.management.base import BaseCommand

from api.utils.cache_utils import (
    clear_academy_caches,
    clear_blog_caches,
    clear_category_caches,
    clear_course_caches,
    clear_faq_caches,
)


class Command(BaseCommand):
    help = "Clear application caches"

    def add_arguments(self, parser):
        parser.add_argument(
            "--cache-type",
            type=str,
            default="all",
            choices=["all", "course", "category", "blog", "faq", "academy"],
            help="Type of cache to clear",
        )

    def handle(self, *args, **options):
        cache_type = options["cache_type"]

        if cache_type == "all":
            self.stdout.write("Clearing all caches...")
            clear_course_caches()
            clear_category_caches()
            clear_blog_caches()
            clear_faq_caches()
            clear_academy_caches()
            cache.clear()  # Clear everything
            self.stdout.write(self.style.SUCCESS("✓ All caches cleared successfully"))

        elif cache_type == "course":
            self.stdout.write("Clearing course caches...")
            clear_course_caches()
            self.stdout.write(self.style.SUCCESS("✓ Course caches cleared"))

        elif cache_type == "category":
            self.stdout.write("Clearing category caches...")
            clear_category_caches()
            self.stdout.write(self.style.SUCCESS("✓ Category caches cleared"))

        elif cache_type == "blog":
            self.stdout.write("Clearing blog caches...")
            clear_blog_caches()
            self.stdout.write(self.style.SUCCESS("✓ Blog caches cleared"))

        elif cache_type == "faq":
            self.stdout.write("Clearing FAQ caches...")
            clear_faq_caches()
            self.stdout.write(self.style.SUCCESS("✓ FAQ caches cleared"))

        elif cache_type == "academy":
            self.stdout.write("Clearing academy caches...")
            clear_academy_caches()
            self.stdout.write(self.style.SUCCESS("✓ Academy caches cleared"))

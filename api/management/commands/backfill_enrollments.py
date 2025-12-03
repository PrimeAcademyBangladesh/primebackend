from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from api.models.models_order import Order, Enrollment


class Command(BaseCommand):
    help = "Backfill missing enrollments for completed orders"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Don't create enrollments; just show what would be done",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of orders to inspect",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Only consider orders completed in the last N days",
        )
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Actually create missing enrollments (requires --commit)",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run")
        limit = options.get("limit")
        days = options.get("days")
        commit = options.get("commit")

        qs = Order.objects.filter(status="completed").annotate(
            items_count=Count("items"), enroll_count=Count("enrollments")
        ).order_by("-completed_at")

        if days:
            since = timezone.now() - timezone.timedelta(days=days)
            qs = qs.filter(completed_at__gte=since)

        total_checked = 0
        total_missing = 0
        total_created = 0

        if limit:
            qs = qs[:limit]

        for order in qs:
            total_checked += 1
            items = list(order.items.all())
            if not items:
                continue

            existing_enrollments = {(e.user_id, e.course_id) for e in order.enrollments.all()}

            missing = []
            for item in items:
                key = (order.user_id, item.course_id)
                if key not in existing_enrollments:
                    missing.append(item)

            if not missing:
                continue

            total_missing += len(missing)
            self.stdout.write(
                self.style.WARNING(
                    f"Order {order.order_number}: {len(missing)} missing enrollment(s)"
                )
            )

            for item in missing:
                self.stdout.write(f"  - Will create enrollment: user={order.user.email}, course={item.course.title}")
                if commit:
                    try:
                        with transaction.atomic():
                            Enrollment.objects.get_or_create(
                                user=order.user, course=item.course, defaults={"order": order}
                            )
                            total_created += 1
                    except Exception as e:
                        self.stderr.write(f"Failed to create enrollment for order {order.order_number}: {e}")

        self.stdout.write("")
        self.stdout.write(f"Checked orders: {total_checked}")
        self.stdout.write(f"Missing enrollments found: {total_missing}")
        if commit:
            self.stdout.write(self.style.SUCCESS(f"Enrollments created: {total_created}"))
        else:
            self.stdout.write(self.style.NOTICE("No changes made (dry-run). Run with --commit to create enrollments."))

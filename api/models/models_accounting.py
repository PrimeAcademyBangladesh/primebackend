import uuid
from django.db import models, transaction
from django.utils import timezone

from api.utils.helper_models import TimeStampedModel

# -------------------------------
# Payment Method
# -------------------------------
class PaymentMethod(TimeStampedModel):
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Income Payment Method"
        verbose_name_plural = "Income Payment Methods"

    def __str__(self):
        return self.name


# -------------------------------
# Income Type
# -------------------------------
class IncomeType(TimeStampedModel):
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100, unique=True)
    prefix = models.CharField(max_length=10)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


# -------------------------------
# Transaction Counter (NEW - for race condition fix)
# -------------------------------
class TransactionCounter(models.Model):
    """Stores counter for each transaction prefix to avoid race conditions"""
    prefix = models.CharField(max_length=50, unique=True, db_index=True)
    counter = models.IntegerField(default=0)

    class Meta:
        db_table = 'transaction_counter'

    def __str__(self):
        return f"{self.prefix}: {self.counter}"


# -------------------------------
# Income
# -------------------------------
class Income(TimeStampedModel):
    STATUS_CHOICES = [
        ("completed", "Completed"),
        ("pending", "Pending"),
        ("cancelled", "Cancelled"),
    ]

    APPROVAL_STATUS = [
        ("approved", "Approved"),
        ("pending", "Pending Approval"),
        ("rejected", "Rejected"),
    ]


    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_id = models.CharField(max_length=50, unique=True, editable=False)

    income_type = models.ForeignKey(IncomeType, on_delete=models.PROTECT)
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT)

    description = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()

    payer_name = models.CharField(max_length=200)
    payer_email = models.EmailField(blank=True, null=True)
    payer_phone = models.CharField(max_length=20, blank=True)

    payment_reference = models.CharField(max_length=100, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="completed")

    approval_status = models.CharField(
        max_length=20, choices=APPROVAL_STATUS, default="pending"
    )
    approved_by = models.ForeignKey(
        "CustomUser", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="approved_incomes"
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    recorded_by = models.ForeignKey(
        "CustomUser", null=True, on_delete=models.SET_NULL,
        related_name="recorded_incomes"
    )

    class Meta:
        indexes = [
            models.Index(fields=['-date'], name='income_date_idx'),
            models.Index(fields=['status', 'approval_status'], name='income_status_idx'),
            models.Index(fields=['income_type', '-date'], name='income_type_date_idx'),
            models.Index(fields=['payment_method'], name='income_payment_idx'),
        ]
        ordering = ['-date', '-created_at']

    def save(self, *args, **kwargs):
        if self._state.adding and not self.transaction_id:
            self.transaction_id = self.generate_transaction_id()
        super().save(*args, **kwargs)

    def generate_transaction_id(self):
        """
        Generate unique transaction ID using counter table to prevent race conditions.
        Format: PRIME-{PREFIX}-{YEAR}-{COUNTER}
        Example: PRIME-DON-2025-0001
        """
        year = self.date.year if self.date else timezone.now().year
        prefix_code = self.income_type.prefix.upper()
        prefix_key = f"PRIME-{prefix_code}-{year}"

        with transaction.atomic():
            # Get or create counter for this prefix, with row lock
            counter_obj, created = TransactionCounter.objects.select_for_update().get_or_create(
                prefix=prefix_key,
                defaults={'counter': 0}
            )

            # Increment counter
            counter_obj.counter += 1
            counter_obj.save(update_fields=['counter'])

            # Generate transaction ID
            return f"{prefix_key}-{str(counter_obj.counter).zfill(4)}"

    def __str__(self):
        return self.transaction_id


# -------------------------------
# Income Update Request (Approval System)
# -------------------------------


class IncomeUpdateRequest(TimeStampedModel):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    # Fields that are allowed to be updated via approval request
    ALLOWED_UPDATE_FIELDS = {
        'income_type', 'payment_method', 'description', 'amount',
        'date', 'payer_name', 'payer_email', 'payer_phone',
        'payment_reference', 'status'
    }

    income = models.ForeignKey(
        Income, on_delete=models.CASCADE, related_name="update_requests"
    )

    requested_by = models.ForeignKey(
        "CustomUser", on_delete=models.CASCADE,
        related_name="income_update_requests"
    )

    requested_data = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    reviewed_by = models.ForeignKey(
        "CustomUser", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reviewed_income_requests"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', '-created_at'], name='income_req_status_idx'),
            models.Index(fields=['income', 'status'], name='income_req_income_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["income"],
                condition=models.Q(status="pending"),
                name="unique_pending_income_update"
            )
        ]
        ordering = ['-created_at']

    def approve(self, admin_user):
        if self.status != "pending":
            raise ValueError("Only pending requests can be approved.")

        with transaction.atomic():
            income = Income.objects.select_for_update().get(pk=self.income_id)

            for field, value in self.requested_data.items():
                if field in self.ALLOWED_UPDATE_FIELDS:
                    setattr(income, field, value)

            income.approval_status = "approved"
            income.approved_by = admin_user
            income.approved_at = timezone.now()

            update_fields = [
                field for field in self.requested_data.keys()
                if field in self.ALLOWED_UPDATE_FIELDS
            ]

            income.save(update_fields=[
                *update_fields,
                "approval_status",
                "approved_by",
                "approved_at",
            ])

            self.status = "approved"
            self.reviewed_by = admin_user
            self.reviewed_at = timezone.now()
            self.save(update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
            ])

    def reject(self, admin_user, reason=""):
        if self.status != "pending":
            raise ValueError("Only pending requests can be rejected.")

        with transaction.atomic():
            self.status = "rejected"
            self.reviewed_by = admin_user
            self.reviewed_at = timezone.now()
            self.rejection_reason = reason
            self.save(update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "rejection_reason",
            ])

    def __str__(self):
        return f"Update Request for {self.income.transaction_id} by {self.requested_by}"



# ============================================================
# Expense Type (MASTER DATA)
# ============================================================
class ExpenseType(TimeStampedModel):
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


# ============================================================
# Expense Payment Method (MASTER DATA)
# ============================================================
class ExpensePaymentMethod(TimeStampedModel):
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


# ============================================================
# Expense (TRANSACTION)
# ============================================================
class Expense(TimeStampedModel):
    STATUS_CHOICES = [
        ("paid", "Paid"),
        ("pending", "Pending"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_id = models.CharField(max_length=50, unique=True, editable=False)

    expense_type = models.ForeignKey(ExpenseType, on_delete=models.PROTECT)
    payment_method = models.ForeignKey(ExpensePaymentMethod, on_delete=models.PROTECT)

    description = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()

    vendor_name = models.CharField(max_length=200)
    vendor_email = models.EmailField(blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="paid")

    recorded_by = models.ForeignKey(
        "CustomUser",
        null=True,
        on_delete=models.SET_NULL,
        related_name="recorded_expenses",
    )

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["-date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["expense_type"]),
            models.Index(fields=["payment_method"]),
        ]

    def save(self, *args, **kwargs):
        if self._state.adding and not self.reference_id:
            self.reference_id = self.generate_reference_id()
        super().save(*args, **kwargs)

    def generate_reference_id(self):
        return f"EXP-{timezone.now().year}-{uuid.uuid4().hex[:6].upper()}"

    def __str__(self):
        return self.reference_id


# ============================================================
# Expense Update Request (APPROVAL WORKFLOW)
# ============================================================
class ExpenseUpdateRequest(TimeStampedModel):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    ALLOWED_UPDATE_FIELDS = {
        "expense_type",
        "payment_method",
        "description",
        "amount",
        "date",
        "vendor_name",
        "vendor_email",
        "status",
    }

    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name="update_requests",
    )

    requested_by = models.ForeignKey(
        "CustomUser",
        on_delete=models.CASCADE,
        related_name="expense_update_requests",
    )

    requested_data = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    reviewed_by = models.ForeignKey(
        "CustomUser",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_expense_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["expense", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["expense"],
                condition=models.Q(status="pending"),
                name="unique_pending_expense_update",
            )
        ]

    # --------------------------------------------------------
    # APPROVE
    # --------------------------------------------------------
    def approve(self, admin_user):
        if self.status != "pending":
            raise ValueError("Only pending requests can be approved.")

        from api.serializers.serializers_accounting import ExpenseCreateSerializer

        with transaction.atomic():
            expense = Expense.objects.select_for_update().get(pk=self.expense_id)

            serializer = ExpenseCreateSerializer(
                expense,
                data=self.requested_data,
                partial=True,
                context={"is_approval": True},
            )
            serializer.is_valid(raise_exception=True)

            update_fields = []

            for field, value in serializer.validated_data.items():
                if field in self.ALLOWED_UPDATE_FIELDS:
                    setattr(expense, field, value)
                    update_fields.append(field)

            expense.save(update_fields=update_fields)

            self.status = "approved"
            self.reviewed_by = admin_user
            self.reviewed_at = timezone.now()
            self.save(update_fields=["status", "reviewed_by", "reviewed_at"])

    # --------------------------------------------------------
    # REJECT
    # --------------------------------------------------------
    def reject(self, admin_user, reason=""):
        if self.status != "pending":
            raise ValueError("Only pending requests can be rejected.")

        with transaction.atomic():
            self.status = "rejected"
            self.reviewed_by = admin_user
            self.reviewed_at = timezone.now()
            self.rejection_reason = reason
            self.save(
                update_fields=[
                    "status",
                    "reviewed_by",
                    "reviewed_at",
                    "rejection_reason",
                ]
            )

    def __str__(self):
        return f"Expense Update Request → {self.expense.reference_id}"

from django.db import models
from django.utils.translation import gettext_lazy as _
from decimal import Decimal

class ProjectStatusChoices(models.TextChoices):
    PLANNING = 'PLANNING', _('Planning & Permits')
    ACTIVE = 'ACTIVE', _('Active Construction')
    ON_HOLD = 'ON_HOLD', _('On Hold')
    COMPLETED = 'COMPLETED', _('Completed')
    ARCHIVED = 'ARCHIVED', _('Archived')


class Project(models.Model):
    name = models.CharField(max_length=200, verbose_name=_("Project Name"))
    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name=_("Unique Project Code"),
        help_text=_("e.g. PRJ-2026-001")
    )
    description = models.TextField(blank=True, verbose_name=_("Description"))
    project_type = models.CharField(
        max_length=100,
        default='Commercial & Residential',
        verbose_name=_("Project Type")
    )
    address = models.TextField(blank=True, verbose_name=_("Site Address"))
    location = models.CharField(
        max_length=150,
        verbose_name=_("City / Location"),
        help_text=_("e.g. Central City Waterfront, Sector 45")
    )
    client_name = models.CharField(max_length=150, verbose_name=_("Client / Owner"))
    client_contact = models.CharField(max_length=100, blank=True, verbose_name=_("Client Contact Info"))
    cover_image = models.ImageField(
        upload_to='project_covers/',
        blank=True,
        null=True,
        verbose_name=_("Cover Image")
    )
    approved_initial_budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_("Approved Initial Budget")
    )
    start_date = models.DateField(verbose_name=_("Start Date"))
    expected_completion_date = models.DateField(verbose_name=_("Expected Completion Date"))
    actual_completion_date = models.DateField(null=True, blank=True, verbose_name=_("Actual Completion Date"))
    status = models.CharField(
        max_length=30,
        choices=ProjectStatusChoices.choices,
        default=ProjectStatusChoices.ACTIVE,
        verbose_name=_("Project Status")
    )
    progress_percentage = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_("Construction Progress (%)")
    )
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_projects',
        verbose_name=_("Created By")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Project")
        verbose_name_plural = _("Projects")
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['status']),
            models.Index(fields=['start_date']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_project_manager(self):
        """Return the active Project Manager assigned to this project."""
        from apps.accounts.models import RoleChoices
        membership = self.memberships.filter(
            role=RoleChoices.PROJECT_MANAGER,
            is_active=True
        ).select_related('user').first()
        return membership.user if membership else self.created_by

    def get_assigned_supervisors(self):
        """Return all active site supervisors assigned to this project."""
        from apps.accounts.models import RoleChoices
        return [
            m.user for m in self.memberships.filter(
                role=RoleChoices.SITE_SUPERVISOR,
                is_active=True
            ).select_related('user')
        ]

    def get_approved_budget(self):
        """Return approved budget including approved revisions if available."""
        # Check if budget revisions exist
        if hasattr(self, 'budget_revisions'):
            total_revisions = self.budget_revisions.filter(is_approved=True).aggregate(
                total=models.Sum('revised_amount')
            )['total']
            if total_revisions:
                return total_revisions
        return self.approved_initial_budget

    def get_recorded_expenditure(self):
        """
        Calculated actual recognized expenditure from all modules:
        Labour net wages + Material recognized invoices + other financial expense transactions.
        """
        total = Decimal('0.00')
        if hasattr(self, 'financial_transactions'):
            # Aggregate all actual expenditure transactions
            expense_total = self.financial_transactions.filter(
                transaction_type='EXPENSE',
                is_reversed=False
            ).aggregate(total=models.Sum('amount'))['total']
            if expense_total:
                total += Decimal(str(expense_total))
        return total

    def get_amount_paid(self):
        """Calculated total cash payments disbursed for this project."""
        total = Decimal('0.00')
        if hasattr(self, 'financial_transactions'):
            paid_total = self.financial_transactions.filter(
                transaction_type__in=['PAYMENT_SUPPLIER', 'PAYMENT_LABOUR', 'EXPENSE'],
                payment_status='PAID',
                is_reversed=False
            ).aggregate(total=models.Sum('amount'))['total']
            if paid_total:
                total += Decimal(str(paid_total))
        return total

    def get_outstanding_liabilities(self):
        """Calculated outstanding liabilities = recorded expenditure minus payments made."""
        expenditure = self.get_recorded_expenditure()
        paid = self.get_amount_paid()
        diff = expenditure - paid
        return max(Decimal('0.00'), diff)

    def get_remaining_budget(self):
        """Remaining approved budget = approved budget - recorded expenditure."""
        approved = self.get_approved_budget()
        expenditure = self.get_recorded_expenditure()
        return approved - expenditure

    def get_budget_burn_rate(self):
        """Percentage of approved budget consumed so far."""
        approved = self.get_approved_budget()
        if not approved or approved == 0:
            return 0
        expenditure = self.get_recorded_expenditure()
        rate = (expenditure / approved) * 100
        return min(100, round(float(rate), 1))

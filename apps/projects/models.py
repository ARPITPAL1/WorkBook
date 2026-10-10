from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal


class ProjectStatusChoices(models.TextChoices):
    PLANNING = 'PLANNING', _('Planning & Permits')
    ACTIVE = 'ACTIVE', _('Active Construction')
    ON_HOLD = 'ON_HOLD', _('On Hold')
    COMPLETED = 'COMPLETED', _('Completed')
    ARCHIVED = 'ARCHIVED', _('Archived')


class POStatusChoices(models.TextChoices):
    DRAFT = 'DRAFT', _('Draft')
    ISSUED = 'ISSUED', _('Issued')
    PARTIAL = 'PARTIAL', _('Partially Delivered')
    DELIVERED = 'DELIVERED', _('Delivered')
    CANCELLED = 'CANCELLED', _('Cancelled')


class InvoiceStatusChoices(models.TextChoices):
    DRAFT = 'DRAFT', _('Draft')
    PENDING_APPROVAL = 'PENDING_APPROVAL', _('Pending Approval')
    UNPAID = 'UNPAID', _('Unpaid')
    PARTIALLY_PAID = 'PARTIALLY_PAID', _('Partially Paid')
    PAID = 'PAID', _('Paid')
    OVERDUE = 'OVERDUE', _('Overdue')
    DISPUTED = 'DISPUTED', _('Disputed')
    CANCELLED = 'CANCELLED', _('Cancelled')


class PaymentMethodChoices(models.TextChoices):
    BANK_TRANSFER = 'BANK_TRANSFER', _('Bank Transfer (NEFT/RTGS)')
    CHEQUE = 'CHEQUE', _('Cheque')
    UPI = 'UPI', _('UPI / Digital')
    CASH = 'CASH', _('Site Cash Disbursement')
    OTHER = 'OTHER', _('Other')


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
    currency = models.CharField(
        max_length=10,
        default='INR',
        verbose_name=_("Project Currency")
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
        """Return approved budget."""
        return self.approved_initial_budget

    def get_recorded_expenditure(self):
        """
        Calculated actual recognized expenditure from all modules:
        Labour gross wages + Material recognized invoices + other financial expense transactions.
        Avoids double counting by checking relationships.
        """
        total = Decimal('0.00')
        # 1. Labour Gross Wages
        labour_sum = self.labour_entries.aggregate(tot=models.Sum('gross_wages'))['tot']
        if labour_sum:
            total += Decimal(str(labour_sum))

        # 2. Material Invoices (non-cancelled)
        invoice_sum = self.material_invoices.exclude(status='CANCELLED').aggregate(tot=models.Sum('total_amount'))['tot']
        if invoice_sum:
            total += Decimal(str(invoice_sum))

        # 3. Direct general expenses in financial transactions not tied to labour or invoice
        if hasattr(self, 'financial_transactions'):
            direct_expense = self.financial_transactions.filter(
                transaction_type='EXPENSE',
                related_invoice__isnull=True,
                related_labour__isnull=True,
                is_reversed=False
            ).aggregate(tot=models.Sum('amount'))['tot']
            if direct_expense:
                total += Decimal(str(direct_expense))
        return total

    def get_amount_paid(self):
        """Calculated total cash payments disbursed for this project."""
        total = Decimal('0.00')
        # 1. Labour wages paid
        labour_paid = self.labour_entries.aggregate(tot=models.Sum('paid_amount'))['tot']
        if labour_paid:
            total += Decimal(str(labour_paid))

        # 2. Material invoice payments made
        invoice_payments = self.invoice_payments.filter(is_reversed=False).aggregate(tot=models.Sum('amount'))['tot']
        if invoice_payments:
            total += Decimal(str(invoice_payments))

        # 3. Direct financial disbursements not tied to invoice or labour
        if hasattr(self, 'financial_transactions'):
            direct_paid = self.financial_transactions.filter(
                transaction_type__in=['PAYMENT_SUPPLIER', 'PAYMENT_LABOUR'],
                related_invoice__isnull=True,
                related_labour__isnull=True,
                is_reversed=False
            ).aggregate(tot=models.Sum('amount'))['tot']
            if direct_paid:
                total += Decimal(str(direct_paid))
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


class LabourEntry(models.Model):
    """Daily site labour attendance and wage record."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='labour_entries')
    date = models.DateField(default=timezone.now, db_index=True)
    category = models.CharField(max_length=120, help_text="e.g. Masonry & Brickwork Gang")
    location_floor = models.CharField(max_length=150, blank=True, help_text="e.g. Floor 14, Tower A")
    workers_count = models.PositiveIntegerField(default=1)
    wage_rate_per_day = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    overtime_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    overtime_rate_per_hour = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    gross_wages = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    outstanding_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    supervisor = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.project.code} - {self.date} - {self.category} ({self.workers_count} workers)"

    def save(self, *args, **kwargs):
        # Auto-compute gross wages = (workers * daily_rate) + (overtime_hours * overtime_rate)
        base = Decimal(str(self.workers_count)) * Decimal(str(self.wage_rate_per_day))
        ot = Decimal(str(self.overtime_hours)) * Decimal(str(self.overtime_rate_per_hour))
        self.gross_wages = base + ot
        self.outstanding_amount = max(Decimal('0.00'), self.gross_wages - self.paid_amount)
        super().save(*args, **kwargs)


class Supplier(models.Model):
    """Construction material vendor or trade subcontractor."""
    name = models.CharField(max_length=200, unique=True)
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    gst_number = models.CharField(max_length=50, blank=True, verbose_name="GSTIN / Tax ID")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class MaterialPurchaseOrder(models.Model):
    """Procurement purchase order issued to supplier."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='purchase_orders')
    po_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='purchase_orders')
    category = models.CharField(max_length=100)
    description = models.TextField()
    quantity = models.CharField(max_length=100)
    estimated_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=30, choices=POStatusChoices.choices, default=POStatusChoices.ISSUED)
    order_date = models.DateField(default=timezone.now)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-order_date', '-created_at']

    def __str__(self):
        return f"{self.po_number} - {self.supplier.name}"


class MaterialInvoice(models.Model):
    """Vendor delivery bill / procurement invoice with live balance tracking."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='material_invoices')
    purchase_order = models.ForeignKey(MaterialPurchaseOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='invoices')
    invoice_number = models.CharField(max_length=100)
    invoice_date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)
    material_description = models.CharField(max_length=250)
    quantity = models.CharField(max_length=100, blank=True)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    outstanding_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=30, choices=InvoiceStatusChoices.choices, default=InvoiceStatusChoices.UNPAID)
    delivery_status = models.CharField(max_length=30, default='Delivered')
    invoice_document = models.FileField(upload_to='invoices/', null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-invoice_date', '-created_at']

    def __str__(self):
        return f"{self.invoice_number} ({self.supplier.name}) - ₹{self.total_amount}"

    def save(self, *args, **kwargs):
        # On first creation, initialise outstanding_balance to total_amount
        if not self.pk:
            self.outstanding_balance = self.total_amount
        super().save(*args, **kwargs)

    def recalculate_status_and_balance(self):
        """
        Authoritative calculation:
        Sum non-reversed payments, update paid_amount, outstanding_balance, and status.
        """
        payments_sum = self.payments.filter(is_reversed=False).aggregate(tot=models.Sum('amount'))['tot'] or Decimal('0.00')
        self.paid_amount = Decimal(str(payments_sum))
        self.outstanding_balance = max(Decimal('0.00'), self.total_amount - self.paid_amount)
        if self.paid_amount == Decimal('0.00'):
            self.status = InvoiceStatusChoices.UNPAID
        elif self.paid_amount >= self.total_amount:
            self.status = InvoiceStatusChoices.PAID
        else:
            self.status = InvoiceStatusChoices.PARTIALLY_PAID
        self.save()


class InvoicePayment(models.Model):
    """Actual cash or bank settlement against an invoice."""
    invoice = models.ForeignKey(MaterialInvoice, on_delete=models.CASCADE, related_name='payments')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='invoice_payments')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_date = models.DateField(default=timezone.now)
    payment_method = models.CharField(max_length=50, choices=PaymentMethodChoices.choices, default=PaymentMethodChoices.BANK_TRANSFER)
    reference_number = models.CharField(max_length=100, blank=True, help_text="UTR / NEFT / Cheque No.")
    receipt_document = models.FileField(upload_to='payment_receipts/', null=True, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    is_reversed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']

    def __str__(self):
        return f"Payment ₹{self.amount} on {self.payment_date} for {self.invoice.invoice_number}"


class FinancialTransaction(models.Model):
    """Consolidated double-entry financial ledger transaction."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='financial_transactions')
    transaction_ref = models.CharField(max_length=50, unique=True, db_index=True)
    transaction_date = models.DateField(default=timezone.now)
    transaction_type = models.CharField(max_length=30)  # EXPENSE, PAYMENT_SUPPLIER, PAYMENT_LABOUR, RECEIPT_CLIENT, ADVANCE
    category = models.CharField(max_length=100)
    description = models.TextField()
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    debit_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    credit_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    payment_status = models.CharField(max_length=30, default='POSTED')
    related_invoice = models.ForeignKey(MaterialInvoice, on_delete=models.SET_NULL, null=True, blank=True)
    related_labour = models.ForeignKey(LabourEntry, on_delete=models.SET_NULL, null=True, blank=True)
    is_reversed = models.BooleanField(default=False)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-transaction_date', '-created_at']

    def __str__(self):
        return f"{self.transaction_ref} ({self.transaction_type}) - ₹{self.amount}"


class BudgetAllocation(models.Model):
    """Budget category allocations for project analytics."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='budget_allocations')
    category = models.CharField(max_length=100)
    allocated_amount = models.DecimalField(max_digits=14, decimal_places=2)
    notes = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('project', 'category')

    def __str__(self):
        return f"{self.project.code} - {self.category}: ₹{self.allocated_amount}"


class LegalDocument(models.Model):
    """Statutory licenses, building sanctions, NOCs, and environmental permits."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='legal_documents')
    title = models.CharField(max_length=200)
    document_type = models.CharField(max_length=100)
    reference_number = models.CharField(max_length=100, blank=True)
    issuing_authority = models.CharField(max_length=200, blank=True)
    issue_date = models.DateField(default=timezone.now)
    expiry_date = models.DateField(null=True, blank=True)
    document_file = models.FileField(upload_to='legal_docs/', null=True, blank=True)
    status = models.CharField(max_length=30, default='Active & Approved')
    uploaded_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-issue_date', '-created_at']

    def __str__(self):
        return f"{self.title} ({self.project.code})"


class ProjectContact(models.Model):
    """Project stakeholder and directory contact."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=150)
    role_assignment = models.CharField(max_length=100)
    organization = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - {self.role_assignment}"


class DailyDiaryEntry(models.Model):
    """Daily site progress report and photographic log."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='diary_entries')
    date = models.DateField(default=timezone.now, db_index=True)
    day_number = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=200)
    weather_condition = models.CharField(max_length=50, default='Clear')
    temperature_celsius = models.IntegerField(default=28)
    work_summary = models.TextField()
    supervisor = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    photo_1 = models.ImageField(upload_to='site_diary/', null=True, blank=True)
    photo_1_caption = models.CharField(max_length=200, blank=True)
    photo_2 = models.ImageField(upload_to='site_diary/', null=True, blank=True)
    photo_2_caption = models.CharField(max_length=200, blank=True)
    photo_3 = models.ImageField(upload_to='site_diary/', null=True, blank=True)
    photo_3_caption = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=30, default='Approved')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-day_number']

    def __str__(self):
        return f"Day {self.day_number} ({self.date}): {self.title}"


class WorkPlanTask(models.Model):
    """Weekly work plan milestone and scheduling item."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='plan_tasks')
    title = models.CharField(max_length=200)
    work_area = models.CharField(max_length=150)
    supervisor = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    start_date = models.DateField(default=timezone.now)
    target_date = models.DateField(default=timezone.now)
    progress_percentage = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=30, default='Planned')
    delay_reason = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start_date', 'target_date']

    def __str__(self):
        return f"{self.title} - {self.progress_percentage}%"

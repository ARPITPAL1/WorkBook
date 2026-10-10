from django import forms
from decimal import Decimal
from django.core.exceptions import ValidationError
from apps.projects.models import (
    Project,
    LabourEntry,
    Supplier,
    MaterialPurchaseOrder,
    MaterialInvoice,
    InvoicePayment,
    FinancialTransaction,
    BudgetAllocation,
    LegalDocument,
    ProjectContact,
    DailyDiaryEntry,
    WorkPlanTask,
    PaymentMethodChoices,
)
from apps.accounts.models import User, RoleChoices


class ProjectForm(forms.ModelForm):
    currency = forms.CharField(
        max_length=10,
        required=False,
        initial='INR',
        widget=forms.TextInput(attrs={'class': 'form-control nova-input', 'readonly': 'readonly'})
    )
    assigned_manager = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True, is_approved=True),
        required=False,
        label="Assigned Project Manager",
        widget=forms.Select(attrs={'class': 'form-select nova-input'})
    )

    class Meta:
        model = Project
        fields = [
            'name',
            'code',
            'project_type',
            'currency',
            'location',
            'address',
            'client_name',
            'client_contact',
            'approved_initial_budget',
            'start_date',
            'expected_completion_date',
            'status',
            'progress_percentage',
            'description',
            'cover_image'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'e.g. Skyline Pinnacle Residences'}),
            'code': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'e.g. PRJ-2026-003'}),
            'project_type': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'e.g. High-Rise Commercial / Residential'}),
            'currency': forms.TextInput(attrs={'class': 'form-control nova-input', 'readonly': 'readonly'}),
            'location': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'e.g. Waterfront Boulevard, Sector 12'}),
            'address': forms.Textarea(attrs={'class': 'form-control nova-input', 'rows': 2, 'placeholder': 'Plot 4A, Marine Way'}),
            'client_name': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'e.g. Apex Living Real Estate Ltd'}),
            'client_contact': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'Phone or primary email'}),
            'approved_initial_budget': forms.NumberInput(attrs={'class': 'form-control nova-input', 'step': '0.01', 'min': '0'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control nova-input', 'type': 'date'}),
            'expected_completion_date': forms.DateInput(attrs={'class': 'form-control nova-input', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select nova-input'}),
            'progress_percentage': forms.NumberInput(attrs={'class': 'form-control nova-input', 'min': '0', 'max': '100'}),
            'description': forms.Textarea(attrs={'class': 'form-control nova-input', 'rows': 3, 'placeholder': 'Scope of construction work, structural specifications...'}),
            'cover_image': forms.FileInput(attrs={'class': 'form-control nova-input'}),
        }

    def clean_currency(self):
        return self.cleaned_data.get('currency') or 'INR'

    def clean_code(self):
        code = self.cleaned_data.get('code', '').strip().upper()
        if not code:
            raise ValidationError("A project code is required.")
        qs = Project.objects.filter(code__iexact=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(f"A project with code '{code}' already exists.")
        return code

    def clean_approved_initial_budget(self):
        budget = self.cleaned_data.get('approved_initial_budget')
        if budget is not None and budget < Decimal('0.00'):
            raise ValidationError("Budget must be a positive number.")
        return budget

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('expected_completion_date')
        if start_date and end_date and end_date < start_date:
            raise ValidationError("Expected completion date cannot be earlier than start date.")
        return cleaned_data


class LabourEntryForm(forms.ModelForm):
    class Meta:
        model = LabourEntry
        fields = [
            'date',
            'category',
            'location_floor',
            'workers_count',
            'wage_rate_per_day',
            'overtime_hours',
            'overtime_rate_per_hour',
            'paid_amount',
            'notes'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control nova-input', 'type': 'date'}),
            'category': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'e.g. Masonry & Brickwork Gang'}),
            'location_floor': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'e.g. Floor 14, Tower A'}),
            'workers_count': forms.NumberInput(attrs={'class': 'form-control nova-input', 'min': '1'}),
            'wage_rate_per_day': forms.NumberInput(attrs={'class': 'form-control nova-input', 'step': '0.01', 'min': '0'}),
            'overtime_hours': forms.NumberInput(attrs={'class': 'form-control nova-input', 'step': '0.5', 'min': '0'}),
            'overtime_rate_per_hour': forms.NumberInput(attrs={'class': 'form-control nova-input', 'step': '0.01', 'min': '0'}),
            'paid_amount': forms.NumberInput(attrs={'class': 'form-control nova-input', 'step': '0.01', 'min': '0'}),
            'notes': forms.Textarea(attrs={'class': 'form-control nova-input', 'rows': 2, 'placeholder': 'Notes or contractor gang lead details...'}),
        }


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'contact_person', 'phone', 'email', 'address', 'gst_number']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'Supplier or Vendor Business Name'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control nova-input'}),
            'phone': forms.TextInput(attrs={'class': 'form-control nova-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-control nova-input'}),
            'address': forms.Textarea(attrs={'class': 'form-control nova-input', 'rows': 2}),
            'gst_number': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'GSTIN Number'}),
        }


class MaterialPurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = MaterialPurchaseOrder
        fields = ['po_number', 'supplier', 'category', 'description', 'quantity', 'estimated_amount', 'order_date']
        widgets = {
            'po_number': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'PO-2026-001'}),
            'supplier': forms.Select(attrs={'class': 'form-select nova-input'}),
            'category': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'Ready-Mix Concrete, TMT Steel...'}),
            'description': forms.Textarea(attrs={'class': 'form-control nova-input', 'rows': 2}),
            'quantity': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'e.g. 450 cu.m / 85 Tonnes'}),
            'estimated_amount': forms.NumberInput(attrs={'class': 'form-control nova-input', 'step': '0.01', 'min': '0'}),
            'order_date': forms.DateInput(attrs={'class': 'form-control nova-input', 'type': 'date'}),
        }


class MaterialInvoiceForm(forms.ModelForm):
    class Meta:
        model = MaterialInvoice
        fields = [
            'supplier',
            'purchase_order',
            'invoice_number',
            'invoice_date',
            'due_date',
            'material_description',
            'quantity',
            'total_amount',
            'tax_amount',
            'delivery_status',
            'notes'
        ]
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select nova-input'}),
            'purchase_order': forms.Select(attrs={'class': 'form-select nova-input'}),
            'invoice_number': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'INV-2026-088'}),
            'invoice_date': forms.DateInput(attrs={'class': 'form-control nova-input', 'type': 'date'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control nova-input', 'type': 'date'}),
            'material_description': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'e.g. Ready-Mix Concrete batch pour M35'}),
            'quantity': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'e.g. 450 cu.m'}),
            'total_amount': forms.NumberInput(attrs={'class': 'form-control nova-input', 'step': '0.01', 'min': '0'}),
            'tax_amount': forms.NumberInput(attrs={'class': 'form-control nova-input', 'step': '0.01', 'min': '0'}),
            'delivery_status': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'Delivered / Partial / Dispatched'}),
            'notes': forms.Textarea(attrs={'class': 'form-control nova-input', 'rows': 2}),
        }


class InvoicePaymentForm(forms.ModelForm):
    """
    Mandatory payment recording form.
    Allows recording partial, full, or multiple settlements against an invoice.
    """
    class Meta:
        model = InvoicePayment
        fields = [
            'amount',
            'payment_date',
            'payment_method',
            'reference_number',
            'receipt_document',
            'notes'
        ]
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control nova-input', 'step': '0.01', 'min': '0.01'}),
            'payment_date': forms.DateInput(attrs={'class': 'form-control nova-input', 'type': 'date'}),
            'payment_method': forms.Select(attrs={'class': 'form-select nova-input'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'Bank UTR / Cheque Ref / Transaction ID'}),
            'receipt_document': forms.FileInput(attrs={'class': 'form-control nova-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control nova-input', 'rows': 2, 'placeholder': 'Payment notes, accounts remarks...'}),
        }


class FinancialTransactionForm(forms.ModelForm):
    class Meta:
        model = FinancialTransaction
        fields = [
            'transaction_date',
            'transaction_type',
            'category',
            'description',
            'amount',
            'payment_status'
        ]
        widgets = {
            'transaction_date': forms.DateInput(attrs={'class': 'form-control nova-input', 'type': 'date'}),
            'transaction_type': forms.Select(
                choices=[
                    ('EXPENSE', 'Expense (Debit)'),
                    ('PAYMENT_SUPPLIER', 'Supplier Payment (Credit)'),
                    ('PAYMENT_LABOUR', 'Labour Wage Payment (Credit)'),
                    ('RECEIPT_CLIENT', 'Client Advance / Milestone Receipt'),
                    ('JOURNAL', 'Journal Adjustment'),
                ],
                attrs={'class': 'form-select nova-input'}
            ),
            'category': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'e.g. Materials, Labour, Equipment, Permits'}),
            'description': forms.Textarea(attrs={'class': 'form-control nova-input', 'rows': 2, 'placeholder': 'Transaction narrative and purpose...'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control nova-input', 'step': '0.01', 'min': '0'}),
            'payment_status': forms.Select(
                choices=[('POSTED', 'Posted'), ('PENDING', 'Pending Settlement')],
                attrs={'class': 'form-select nova-input'}
            ),
        }


class LegalDocumentForm(forms.ModelForm):
    class Meta:
        model = LegalDocument
        fields = [
            'title',
            'document_type',
            'reference_number',
            'issuing_authority',
            'issue_date',
            'expiry_date',
            'document_file',
            'status'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'e.g. Building Sanction Plan V2'}),
            'document_type': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'Municipal Sanction, Fire NOC, EIA...'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'MC-2025-BLD-8812'}),
            'issuing_authority': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'Municipal Development Authority'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control nova-input', 'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control nova-input', 'type': 'date'}),
            'document_file': forms.FileInput(attrs={'class': 'form-control nova-input'}),
            'status': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'Active & Approved'}),
        }


class ProjectContactForm(forms.ModelForm):
    class Meta:
        model = ProjectContact
        fields = ['name', 'role_assignment', 'organization', 'phone', 'email']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'Contact Full Name'}),
            'role_assignment': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'Lead Architect / Structural Engineer / Labour Contractor'}),
            'organization': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'Company or Firm Name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': '+91 98765 43210'}),
            'email': forms.EmailInput(attrs={'class': 'form-control nova-input'}),
        }


class DailyDiaryEntryForm(forms.ModelForm):
    class Meta:
        model = DailyDiaryEntry
        fields = [
            'date',
            'day_number',
            'title',
            'weather_condition',
            'temperature_celsius',
            'work_summary',
            'photo_1',
            'photo_1_caption',
            'photo_2',
            'photo_2_caption',
            'photo_3',
            'photo_3_caption',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control nova-input', 'type': 'date'}),
            'day_number': forms.NumberInput(attrs={'class': 'form-control nova-input', 'min': '1'}),
            'title': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'e.g. Tower A Core Slab Pour'}),
            'weather_condition': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'Clear / Sunny / Rain'}),
            'temperature_celsius': forms.NumberInput(attrs={'class': 'form-control nova-input'}),
            'work_summary': forms.Textarea(attrs={'class': 'form-control nova-input', 'rows': 3, 'placeholder': 'Daily work log, milestones achieved, cubic meters poured, safety status...'}),
            'photo_1': forms.FileInput(attrs={'class': 'form-control nova-input'}),
            'photo_1_caption': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'Photo 1 caption / location'}),
            'photo_2': forms.FileInput(attrs={'class': 'form-control nova-input'}),
            'photo_2_caption': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'Photo 2 caption / location'}),
            'photo_3': forms.FileInput(attrs={'class': 'form-control nova-input'}),
            'photo_3_caption': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'Photo 3 caption / location'}),
        }


class WorkPlanTaskForm(forms.ModelForm):
    class Meta:
        model = WorkPlanTask
        fields = [
            'title',
            'work_area',
            'start_date',
            'target_date',
            'progress_percentage',
            'status',
            'delay_reason'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'Milestone or structural task name'}),
            'work_area': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'e.g. Basement -2, Floor 14 Core'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control nova-input', 'type': 'date'}),
            'target_date': forms.DateInput(attrs={'class': 'form-control nova-input', 'type': 'date'}),
            'progress_percentage': forms.NumberInput(attrs={'class': 'form-control nova-input', 'min': '0', 'max': '100'}),
            'status': forms.Select(
                choices=[
                    ('Planned', 'Planned'),
                    ('In Progress', 'In Progress'),
                    ('Completed', 'Completed'),
                    ('Delayed', 'Delayed'),
                ],
                attrs={'class': 'form-select nova-input'}
            ),
            'delay_reason': forms.TextInput(attrs={'class': 'form-control nova-input', 'placeholder': 'Reason if delayed (optional)'}),
        }


class BudgetAllocationForm(forms.ModelForm):
    class Meta:
        model = BudgetAllocation
        fields = [
            'category',
            'allocated_amount',
            'notes'
        ]
        widgets = {
            'category': forms.Select(
                choices=[
                    ('Labour & Manpower', 'Labour & Manpower'),
                    ('Materials & Procurement', 'Materials & Procurement'),
                    ('Equipment & Machinery', 'Equipment & Machinery'),
                    ('Subcontractors & MEP', 'Subcontractors & MEP'),
                    ('Legal, Permits & Compliance', 'Legal, Permits & Compliance'),
                ],
                attrs={'class': 'form-select nova-input'}
            ),
            'allocated_amount': forms.NumberInput(attrs={'class': 'form-control nova-input', 'step': '0.01', 'min': '0'}),
            'notes': forms.Textarea(attrs={'class': 'form-control nova-input', 'rows': 2, 'placeholder': 'Budget justification / allocation remarks'}),
        }


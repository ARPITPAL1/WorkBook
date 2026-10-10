from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
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
    InvoiceStatusChoices,
)


def generate_txn_ref(prefix="TXN"):
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    import random
    rand = random.randint(100, 999)
    return f"{prefix}-{timestamp}-{rand}"


@transaction.atomic
def record_labour_entry_service(project, data, user=None):
    """
    Saves daily site labour entry and automatically creates matching
    central financial ledger transactions within an atomic database transaction.
    """
    entry = LabourEntry.objects.create(
        project=project,
        date=data.get('date') or timezone.now().date(),
        category=data['category'],
        location_floor=data.get('location_floor', ''),
        workers_count=int(data.get('workers_count', 1)),
        wage_rate_per_day=Decimal(str(data.get('wage_rate_per_day', '0.00'))),
        overtime_hours=Decimal(str(data.get('overtime_hours', '0.00'))),
        overtime_rate_per_hour=Decimal(str(data.get('overtime_rate_per_hour', '0.00'))),
        paid_amount=Decimal(str(data.get('paid_amount', '0.00'))),
        supervisor=user,
        notes=data.get('notes', '')
    )

    # 1. Post recognized labour expense to central financial ledger
    FinancialTransaction.objects.create(
        project=project,
        transaction_ref=generate_txn_ref("LBR-EXP"),
        transaction_date=entry.date,
        transaction_type='EXPENSE',
        category='Labour & Manpower',
        description=f"Site labour muster roll: {entry.category} ({entry.workers_count} workers at {entry.location_floor})",
        amount=entry.gross_wages,
        debit_amount=entry.gross_wages,
        credit_amount=Decimal('0.00'),
        payment_status='POSTED',
        related_labour=entry,
        created_by=user
    )

    # 2. If immediate wage disbursement occurred, record the cash payment transaction
    if entry.paid_amount > Decimal('0.00'):
        FinancialTransaction.objects.create(
            project=project,
            transaction_ref=generate_txn_ref("LBR-PAY"),
            transaction_date=entry.date,
            transaction_type='PAYMENT_LABOUR',
            category='Labour & Manpower',
            description=f"On-site wage settlement: {entry.category}",
            amount=entry.paid_amount,
            debit_amount=Decimal('0.00'),
            credit_amount=entry.paid_amount,
            payment_status='POSTED',
            related_labour=entry,
            created_by=user
        )

    return entry


@transaction.atomic
def create_material_invoice_service(project, data, user=None):
    """
    Saves a material invoice and posts recognized material cost to the central ledger.
    """
    invoice = MaterialInvoice.objects.create(
        project=project,
        purchase_order=data.get('purchase_order'),
        supplier=data['supplier'],
        invoice_number=data['invoice_number'].strip(),
        invoice_date=data.get('invoice_date') or timezone.now().date(),
        due_date=data.get('due_date'),
        material_description=data['material_description'],
        quantity=data.get('quantity', ''),
        total_amount=Decimal(str(data['total_amount'])),
        tax_amount=Decimal(str(data.get('tax_amount', '0.00'))),
        delivery_status=data.get('delivery_status', 'Delivered'),
        notes=data.get('notes', ''),
        created_by=user
    )

    # Post recognized procurement expense in ledger
    FinancialTransaction.objects.create(
        project=project,
        transaction_ref=generate_txn_ref("MAT-INV"),
        transaction_date=invoice.invoice_date,
        transaction_type='EXPENSE',
        category='Materials & Procurement',
        description=f"Material invoice #{invoice.invoice_number} from {invoice.supplier.name}: {invoice.material_description}",
        amount=invoice.total_amount,
        debit_amount=invoice.total_amount,
        credit_amount=Decimal('0.00'),
        payment_status='POSTED',
        related_invoice=invoice,
        created_by=user
    )

    return invoice


@transaction.atomic
def record_invoice_payment_service(invoice, payment_amount, payment_date, payment_method, ref_no='', notes='', user=None):
    """
    Records an invoice payment (partial or full), updates outstanding balances,
    recalculates invoice status, and logs payment transaction in the ledger.
    """
    amt = Decimal(str(payment_amount))
    if amt <= Decimal('0.00'):
        raise ValueError("Payment amount must be greater than zero.")

    if amt > invoice.outstanding_balance:
        raise ValueError(f"Payment amount (₹{amt}) cannot exceed outstanding balance (₹{invoice.outstanding_balance}).")

    payment = InvoicePayment.objects.create(
        invoice=invoice,
        project=invoice.project,
        amount=amt,
        payment_date=payment_date or timezone.now().date(),
        payment_method=payment_method,
        reference_number=ref_no,
        notes=notes,
        recorded_by=user
    )

    # Recalculate invoice status and balance
    invoice.recalculate_status_and_balance()

    # Record supplier settlement transaction in central ledger
    FinancialTransaction.objects.create(
        project=invoice.project,
        transaction_ref=generate_txn_ref("SUP-PAY"),
        transaction_date=payment.payment_date,
        transaction_type='PAYMENT_SUPPLIER',
        category='Materials & Procurement',
        description=f"Disbursed settlement for Inv #{invoice.invoice_number} ({invoice.supplier.name}) Ref: {ref_no}",
        amount=payment.amount,
        debit_amount=Decimal('0.00'),
        credit_amount=payment.amount,
        payment_status='POSTED',
        related_invoice=invoice,
        created_by=user
    )

    return payment


def get_project_budget_analytics(project):
    """
    Returns actual spent and planned amounts by category from the live database.
    """
    categories = [
        'Labour & Manpower',
        'Materials & Procurement',
        'Equipment & Machinery',
        'Subcontractors & MEP',
        'Legal, Permits & Compliance'
    ]

    # Actuals
    actual_labour = project.labour_entries.aggregate(tot=models.Sum('gross_wages'))['tot'] or Decimal('0.00')
    actual_materials = project.material_invoices.exclude(status='CANCELLED').aggregate(tot=models.Sum('total_amount'))['tot'] or Decimal('0.00')

    # Query allocations
    allocations_list = list(project.budget_allocations.all())
    allocations_map = {b.category: b.allocated_amount for b in allocations_list}
    allocations_obj_map = {b.category: b for b in allocations_list}

    # If no allocations defined, distribute approved budget across realistic standard industry ratios
    total_approved = project.get_approved_budget()
    default_ratios = {
        'Labour & Manpower': Decimal('0.28'),
        'Materials & Procurement': Decimal('0.45'),
        'Equipment & Machinery': Decimal('0.12'),
        'Subcontractors & MEP': Decimal('0.10'),
        'Legal, Permits & Compliance': Decimal('0.05'),
    }

    breakdown = []
    labels = []
    planned_data = []
    actual_data = []

    for cat in categories:
        labels.append(cat)
        planned = allocations_map.get(cat)
        alloc_obj = allocations_obj_map.get(cat)
        if planned is None:
            ratio = default_ratios.get(cat, Decimal('0.00'))
            planned = total_approved * ratio
        planned_data.append(float(planned))

        # Determine actual spent
        if cat == 'Labour & Manpower':
            actual = actual_labour
        elif cat == 'Materials & Procurement':
            actual = actual_materials
        else:
            tx_sum = project.financial_transactions.filter(category__icontains=cat.split()[0], transaction_type='EXPENSE', is_reversed=False).aggregate(tot=models.Sum('amount'))['tot'] or Decimal('0.00')
            actual = Decimal(str(tx_sum))
        actual_data.append(float(actual))

        diff = planned - actual
        status_label = "On Budget" if diff >= Decimal('0.00') else "Over Budget"
        breakdown.append({
            'category': cat,
            'planned': planned,
            'actual': actual,
            'remaining': diff,
            'status': status_label,
            'share': round((planned / total_approved * 100), 1) if total_approved > 0 else 0,
            'is_custom': alloc_obj is not None,
            'allocation_id': alloc_obj.id if alloc_obj else None,
            'notes': alloc_obj.notes if alloc_obj else '',
        })

    return {
        'labels': labels,
        'planned_data': planned_data,
        'actual_data': actual_data,
        'breakdown': breakdown
    }


# =============================================================================
# SAFE EDITING, DELETION & FINANCIAL REVERSAL SERVICES
# =============================================================================

@transaction.atomic
def update_labour_entry_service(entry, data, user=None):
    """
    Updates daily labour entry, re-computes gross wages and dues,
    and updates matching central ledger transactions.
    """
    if 'date' in data and data['date']:
        entry.date = data['date']
    if 'category' in data and data['category']:
        entry.category = data['category']
    if 'location_floor' in data:
        entry.location_floor = data['location_floor']
    if 'workers_count' in data and data['workers_count'] is not None:
        entry.workers_count = int(data['workers_count'])
    if 'wage_rate_per_day' in data and data['wage_rate_per_day'] is not None:
        entry.wage_rate_per_day = Decimal(str(data['wage_rate_per_day']))
    if 'overtime_hours' in data and data['overtime_hours'] is not None:
        entry.overtime_hours = Decimal(str(data['overtime_hours']))
    if 'overtime_rate_per_hour' in data and data['overtime_rate_per_hour'] is not None:
        entry.overtime_rate_per_hour = Decimal(str(data['overtime_rate_per_hour']))
    if 'paid_amount' in data and data['paid_amount'] is not None:
        entry.paid_amount = Decimal(str(data['paid_amount']))
    if 'notes' in data:
        entry.notes = data['notes']

    entry.save()

    # Update matching expense transaction in central ledger
    FinancialTransaction.objects.filter(
        related_labour=entry,
        transaction_type='EXPENSE'
    ).update(
        transaction_date=entry.date,
        amount=entry.gross_wages,
        debit_amount=entry.gross_wages,
        description=f"Site labour muster roll: {entry.category} ({entry.workers_count} workers at {entry.location_floor})"
    )

    # Update matching payment transaction
    pay_tx = FinancialTransaction.objects.filter(
        related_labour=entry,
        transaction_type='PAYMENT_LABOUR'
    ).first()
    if entry.paid_amount > Decimal('0.00'):
        if pay_tx:
            pay_tx.transaction_date = entry.date
            pay_tx.amount = entry.paid_amount
            pay_tx.credit_amount = entry.paid_amount
            pay_tx.is_reversed = False
            pay_tx.save()
        else:
            FinancialTransaction.objects.create(
                project=entry.project,
                transaction_ref=generate_txn_ref("LBR-PAY"),
                transaction_date=entry.date,
                transaction_type='PAYMENT_LABOUR',
                category='Labour & Manpower',
                description=f"On-site wage settlement: {entry.category}",
                amount=entry.paid_amount,
                debit_amount=Decimal('0.00'),
                credit_amount=entry.paid_amount,
                payment_status='POSTED',
                related_labour=entry,
                created_by=user
            )
    elif pay_tx:
        pay_tx.delete()

    return entry


@transaction.atomic
def delete_labour_entry_service(entry, user=None):
    """
    Safely removes labour muster entry and reverses associated ledger transactions.
    """
    FinancialTransaction.objects.filter(related_labour=entry).delete()
    entry.delete()
    return True


@transaction.atomic
def update_material_invoice_service(invoice, data, user=None):
    """
    Updates procurement invoice details, validates totals against paid amounts,
    and updates ledger expense postings.
    """
    if 'supplier' in data and data['supplier']:
        invoice.supplier = data['supplier']
    if 'purchase_order' in data:
        invoice.purchase_order = data['purchase_order']
    if 'invoice_number' in data and data['invoice_number']:
        invoice.invoice_number = data['invoice_number'].strip()
    if 'invoice_date' in data and data['invoice_date']:
        invoice.invoice_date = data['invoice_date']
    if 'due_date' in data:
        invoice.due_date = data['due_date']
    if 'material_description' in data and data['material_description']:
        invoice.material_description = data['material_description']
    if 'quantity' in data:
        invoice.quantity = data['quantity']
    if 'tax_amount' in data and data['tax_amount'] is not None:
        invoice.tax_amount = Decimal(str(data['tax_amount']))
    if 'delivery_status' in data and data['delivery_status']:
        invoice.delivery_status = data['delivery_status']
    if 'notes' in data:
        invoice.notes = data['notes']

    if 'total_amount' in data and data['total_amount'] is not None:
        new_total = Decimal(str(data['total_amount']))
        if new_total < invoice.paid_amount:
            raise ValueError(f"Total invoice amount cannot be less than disbursed payments (₹{invoice.paid_amount}).")
        invoice.total_amount = new_total

    invoice.save()
    invoice.recalculate_status_and_balance()

    FinancialTransaction.objects.filter(
        related_invoice=invoice,
        transaction_type='EXPENSE'
    ).update(
        transaction_date=invoice.invoice_date,
        amount=invoice.total_amount,
        debit_amount=invoice.total_amount,
        description=f"Material invoice #{invoice.invoice_number} from {invoice.supplier.name}: {invoice.material_description}"
    )
    return invoice


@transaction.atomic
def cancel_or_delete_material_invoice_service(invoice, user=None):
    """
    If payments exist, preserves audit trail: cancels invoice and reverses transactions.
    If no payments exist, safely deletes invoice and cleans ledger.
    """
    has_active_payments = invoice.payments.filter(is_reversed=False).exists()
    if has_active_payments:
        invoice.status = InvoiceStatusChoices.CANCELLED
        invoice.outstanding_balance = Decimal('0.00')
        invoice.save()
        for p in invoice.payments.filter(is_reversed=False):
            p.is_reversed = True
            p.save()
        FinancialTransaction.objects.filter(related_invoice=invoice).update(
            is_reversed=True,
            payment_status='REVERSED'
        )
    else:
        FinancialTransaction.objects.filter(related_invoice=invoice).delete()
        invoice.delete()
    return True


@transaction.atomic
def reverse_invoice_payment_service(payment, user=None, reason=''):
    """
    Reverses an invoice payment, recalculates invoice balance and status,
    and voids the matching ledger transaction.
    """
    if payment.is_reversed:
        raise ValueError("This payment has already been reversed.")
    payment.is_reversed = True
    if reason:
        payment.notes = f"{payment.notes} [REVERSED: {reason}]".strip()
    payment.save()

    FinancialTransaction.objects.filter(
        related_invoice=payment.invoice,
        amount=payment.amount,
        transaction_type='PAYMENT_SUPPLIER',
        is_reversed=False
    ).update(is_reversed=True, payment_status='REVERSED')

    payment.invoice.recalculate_status_and_balance()
    return payment


@transaction.atomic
def update_purchase_order_service(po, data, user=None):
    """Updates purchase order details."""
    if 'supplier' in data and data['supplier']:
        po.supplier = data['supplier']
    if 'category' in data and data['category']:
        po.category = data['category']
    if 'description' in data:
        po.description = data['description']
    if 'quantity' in data:
        po.quantity = data['quantity']
    if 'estimated_amount' in data and data['estimated_amount'] is not None:
        po.estimated_amount = Decimal(str(data['estimated_amount']))
    if 'status' in data and data['status']:
        po.status = data['status']
    if 'order_date' in data and data['order_date']:
        po.order_date = data['order_date']
    po.save()
    return po


@transaction.atomic
def delete_purchase_order_service(po, user=None):
    """Deletes purchase order if not referenced by active invoices."""
    if po.invoices.exclude(status='CANCELLED').exists():
        raise ValueError(f"Cannot delete Purchase Order {po.po_number}: active supplier invoices reference it.")
    po.delete()
    return True


@transaction.atomic
def update_supplier_service(supplier, data, user=None):
    """Updates supplier information."""
    for field in ['name', 'contact_person', 'phone', 'email', 'address', 'gst_number']:
        if field in data and data[field] is not None:
            setattr(supplier, field, data[field])
    supplier.save()
    return supplier


@transaction.atomic
def delete_supplier_service(supplier, user=None):
    """Deletes supplier only if not referenced by invoices or purchase orders."""
    if supplier.invoices.exists() or supplier.purchase_orders.exists():
        raise ValueError(f"Cannot delete vendor '{supplier.name}': active invoices or purchase orders are linked to this supplier.")
    supplier.delete()
    return True


@transaction.atomic
def reverse_financial_transaction_service(txn, user=None, reason=''):
    """
    Authoritative reversal of a manual ledger transaction.
    Preserves audit history and marks transaction as reversed.
    """
    if txn.is_reversed:
        raise ValueError("Transaction has already been reversed.")
    if txn.related_invoice or txn.related_labour:
        raise ValueError("This transaction was generated automatically by an operational record. Please adjust or cancel the source invoice/muster roll instead.")

    txn.is_reversed = True
    txn.payment_status = 'REVERSED'
    desc_suffix = f" [REVERSED by {user.username if user else 'System'}: {reason}]" if reason else f" [REVERSED by {user.username if user else 'System'}]"
    txn.description = f"{txn.description}{desc_suffix}"
    txn.save()
    return txn


@transaction.atomic
def delete_budget_allocation_service(project, allocation_id_or_cat, user=None):
    """Deletes budget allocation category for project."""
    if allocation_id_or_cat:
        if str(allocation_id_or_cat).isdigit():
            BudgetAllocation.objects.filter(project=project, pk=int(allocation_id_or_cat)).delete()
        else:
            BudgetAllocation.objects.filter(project=project, category=str(allocation_id_or_cat)).delete()
    return True


@transaction.atomic
def delete_legal_document_service(doc, user=None):
    """Deletes legal document."""
    doc.delete()
    return True


@transaction.atomic
def delete_project_contact_service(contact, user=None):
    """Deletes project contact."""
    contact.delete()
    return True


@transaction.atomic
def delete_daily_diary_service(diary, user=None):
    """Deletes daily site report."""
    diary.delete()
    return True


@transaction.atomic
def delete_work_plan_task_service(task, user=None):
    """Deletes work plan milestone/task."""
    task.delete()
    return True


@transaction.atomic
def delete_project_service(project, user=None):
    """Permanently deletes project (restricted to company admins)."""
    if not (user and user.is_company_admin):
        raise PermissionError("Permission denied. Only Company Administrators can delete projects.")
    project.delete()
    return True


import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Avg
from django.utils import timezone
from decimal import Decimal

from apps.projects.models import (
    Project,
    ProjectStatusChoices,
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
)
from apps.projects.forms import (
    ProjectForm,
    LabourEntryForm,
    SupplierForm,
    MaterialPurchaseOrderForm,
    MaterialInvoiceForm,
    InvoicePaymentForm,
    FinancialTransactionForm,
    LegalDocumentForm,
    ProjectContactForm,
    DailyDiaryEntryForm,
    WorkPlanTaskForm,
    BudgetAllocationForm,
)
from apps.accounts.models import ProjectMembership, RoleChoices
from apps.accounts.permissions import project_access_required, project_role_required
from apps.projects.services import (
    record_labour_entry_service,
    update_labour_entry_service,
    delete_labour_entry_service,
    create_material_invoice_service,
    update_material_invoice_service,
    cancel_or_delete_material_invoice_service,
    record_invoice_payment_service,
    reverse_invoice_payment_service,
    update_purchase_order_service,
    delete_purchase_order_service,
    update_supplier_service,
    delete_supplier_service,
    reverse_financial_transaction_service,
    delete_budget_allocation_service,
    delete_legal_document_service,
    delete_project_contact_service,
    delete_daily_diary_service,
    delete_work_plan_task_service,
    delete_project_service,
    get_project_budget_analytics,
    generate_txn_ref,
)


@login_required
def project_list_view(request):
    """
    Project Portfolio Homepage.
    Displays architectural cards, portfolio statistics, search and filters.
    All figures calculated dynamically from database.
    """
    user = request.user
    if user.is_company_admin:
        queryset = Project.objects.all()
    else:
        assigned_project_ids = user.project_memberships.filter(is_active=True).values_list('project_id', flat=True)
        queryset = Project.objects.filter(id__in=assigned_project_ids)

    # Search query
    q = request.GET.get('q', '').strip()
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q) |
            Q(code__icontains=q) |
            Q(location__icontains=q) |
            Q(client_name__icontains=q)
        )

    # Status filter
    status_filter = request.GET.get('status', '').strip()
    if status_filter and status_filter in ProjectStatusChoices.values:
        queryset = queryset.filter(status=status_filter)

    # Sorting
    sort = request.GET.get('sort', '-updated_at')
    valid_sorts = {
        'recent': '-updated_at',
        'progress_desc': '-progress_percentage',
        'progress_asc': 'progress_percentage',
        'budget_desc': '-approved_initial_budget',
        'budget_asc': 'approved_initial_budget',
        'name': 'name',
    }
    order_by_field = valid_sorts.get(sort, '-updated_at')
    projects = queryset.order_by(order_by_field)

    # Portfolio Summary Metrics from live database
    total_projects = queryset.count()
    active_count = queryset.filter(status=ProjectStatusChoices.ACTIVE).count()
    total_budget = queryset.aggregate(total=Sum('approved_initial_budget'))['total'] or Decimal('0.00')
    avg_progress = queryset.aggregate(avg=Avg('progress_percentage'))['avg'] or 0

    context = {
        'projects': projects,
        'total_projects': total_projects,
        'active_count': active_count,
        'total_budget': total_budget,
        'avg_progress': round(avg_progress, 1),
        'search_query': q,
        'selected_status': status_filter,
        'selected_sort': sort,
        'status_choices': ProjectStatusChoices.choices,
    }
    return render(request, 'projects/project_list.html', context)


@login_required
def project_create_view(request):
    """Create a new construction project workspace."""
    if not request.user.can_manage_project():
        messages.error(request, "Permission denied. Only Administrators and Project Managers can create projects.")
        return redirect('projects:project_list')

    if request.method == 'POST':
        form = ProjectForm(request.POST, request.FILES)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            project.save()

            assigned_manager = form.cleaned_data.get('assigned_manager')
            if assigned_manager:
                ProjectMembership.objects.update_or_create(
                    user=assigned_manager,
                    project=project,
                    defaults={'role': RoleChoices.PROJECT_MANAGER, 'is_active': True}
                )

            if request.user.primary_role == RoleChoices.PROJECT_MANAGER:
                ProjectMembership.objects.get_or_create(
                    user=request.user,
                    project=project,
                    defaults={'role': RoleChoices.PROJECT_MANAGER, 'is_active': True}
                )

            messages.success(request, f"Project '{project.name}' ({project.code}) initialized successfully!")
            return redirect('projects:project_detail', pk=project.pk)
    else:
        form = ProjectForm()

    return render(request, 'projects/project_form.html', {'form': form})


@login_required
@project_access_required
def project_detail_view(request, pk):
    """Central Project Dashboard."""
    project = request.current_project
    user_role = request.current_project_role

    context = {
        'project': project,
        'user_role': user_role,
        'approved_budget': project.get_approved_budget(),
        'recorded_expenditure': project.get_recorded_expenditure(),
        'amount_paid': project.get_amount_paid(),
        'outstanding_liabilities': project.get_outstanding_liabilities(),
        'remaining_budget': project.get_remaining_budget(),
        'burn_rate': project.get_budget_burn_rate(),
        'memberships': project.memberships.filter(is_active=True).select_related('user'),
        'project_manager': project.get_project_manager(),
        'active_tab': 'overview',
    }
    return render(request, 'projects/project_detail.html', context)


@login_required
@project_access_required
def project_labour_view(request, pk):
    """Labour Daily Diary with working entry form, edit, delete, and real database records."""
    project = request.current_project
    form = LabourEntryForm()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'edit_labour':
            entry_id = request.POST.get('entry_id')
            entry = get_object_or_404(LabourEntry, pk=entry_id, project=project)
            edit_form = LabourEntryForm(request.POST, instance=entry)
            if edit_form.is_valid():
                update_labour_entry_service(entry, edit_form.cleaned_data, user=request.user)
                messages.success(request, f"Labour entry for {entry.category} updated and financial ledger synchronized.")
                return redirect('projects:project_labour', pk=project.pk)
            else:
                messages.error(request, "Please correct the errors in the edit labour form.")

        elif action == 'delete_labour':
            entry_id = request.POST.get('entry_id')
            entry = get_object_or_404(LabourEntry, pk=entry_id, project=project)
            cat_name = entry.category
            delete_labour_entry_service(entry, user=request.user)
            messages.success(request, f"Labour entry for '{cat_name}' safely deleted and associated ledger entries removed.")
            return redirect('projects:project_labour', pk=project.pk)

        else:
            form = LabourEntryForm(request.POST)
            if form.is_valid():
                record_labour_entry_service(project, form.cleaned_data, user=request.user)
                messages.success(request, "Daily labour entry recorded and posted to project finance ledger.")
                return redirect('projects:project_labour', pk=project.pk)
            else:
                messages.error(request, "Please correct the errors in the labour form.")

    entries = project.labour_entries.all()

    # Aggregate summaries
    today = timezone.now().date()
    today_entries = entries.filter(date=today)
    today_headcount = today_entries.aggregate(tot=Sum('workers_count'))['tot'] or 0
    today_gross = today_entries.aggregate(tot=Sum('gross_wages'))['tot'] or Decimal('0.00')

    total_gross = entries.aggregate(tot=Sum('gross_wages'))['tot'] or Decimal('0.00')
    total_paid = entries.aggregate(tot=Sum('paid_amount'))['tot'] or Decimal('0.00')
    total_outstanding = max(Decimal('0.00'), total_gross - total_paid)

    context = {
        'project': project,
        'active_tab': 'labour',
        'user_role': request.current_project_role,
        'form': form,
        'entries': entries,
        'today_headcount': today_headcount,
        'today_gross': today_gross,
        'total_gross': total_gross,
        'total_paid': total_paid,
        'total_outstanding': total_outstanding,
    }
    return render(request, 'projects/modules/labour_diary.html', context)


@login_required
@project_access_required
def project_materials_view(request, pk):
    """
    Materials & Procurement Register.
    Includes Purchase Orders, Vendor Invoices, and Payment Status updates.
    """
    project = request.current_project
    invoice_form = MaterialInvoiceForm()
    po_form = MaterialPurchaseOrderForm()
    supplier_form = SupplierForm()

    # Handle form submissions
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_invoice':
            invoice_form = MaterialInvoiceForm(request.POST, request.FILES)
            if invoice_form.is_valid():
                create_material_invoice_service(project, invoice_form.cleaned_data, user=request.user)
                messages.success(request, "Procurement invoice saved and recognized in financial ledger.")
                return redirect('projects:project_materials', pk=project.pk)
            else:
                messages.error(request, "Error saving invoice. Please check the fields.")

        elif action == 'add_po':
            po_form = MaterialPurchaseOrderForm(request.POST)
            if po_form.is_valid():
                po = po_form.save(commit=False)
                po.project = project
                po.created_by = request.user
                po.save()
                messages.success(request, f"Purchase Order {po.po_number} created successfully.")
                return redirect('projects:project_materials', pk=project.pk)
            else:
                messages.error(request, "Error creating purchase order.")

        elif action == 'add_supplier':
            supplier_form = SupplierForm(request.POST)
            if supplier_form.is_valid():
                sup = supplier_form.save()
                messages.success(request, f"Supplier '{sup.name}' added to vendor directory.")
                return redirect('projects:project_materials', pk=project.pk)

        elif action == 'edit_invoice':
            inv_id = request.POST.get('invoice_id')
            inv = get_object_or_404(MaterialInvoice, pk=inv_id, project=project)
            inv_form = MaterialInvoiceForm(request.POST, request.FILES, instance=inv)
            if inv_form.is_valid():
                try:
                    update_material_invoice_service(inv, inv_form.cleaned_data, user=request.user)
                    messages.success(request, f"Invoice #{inv.invoice_number} updated successfully.")
                    return redirect('projects:project_materials', pk=project.pk)
                except ValueError as e:
                    messages.error(request, str(e))
            else:
                messages.error(request, "Validation error while updating invoice.")

        elif action == 'delete_invoice':
            inv_id = request.POST.get('invoice_id')
            inv = get_object_or_404(MaterialInvoice, pk=inv_id, project=project)
            inv_num = inv.invoice_number
            cancel_or_delete_material_invoice_service(inv, user=request.user)
            messages.success(request, f"Invoice #{inv_num} safely cancelled/removed and financial totals refreshed.")
            return redirect('projects:project_materials', pk=project.pk)

        elif action == 'edit_po':
            po_id = request.POST.get('po_id')
            po = get_object_or_404(MaterialPurchaseOrder, pk=po_id, project=project)
            po_edit_form = MaterialPurchaseOrderForm(request.POST, instance=po)
            if po_edit_form.is_valid():
                update_purchase_order_service(po, po_edit_form.cleaned_data, user=request.user)
                messages.success(request, f"Purchase Order {po.po_number} updated.")
                return redirect('projects:project_materials', pk=project.pk)
            else:
                messages.error(request, "Validation error while updating purchase order.")

        elif action == 'delete_po':
            po_id = request.POST.get('po_id')
            po = get_object_or_404(MaterialPurchaseOrder, pk=po_id, project=project)
            po_num = po.po_number
            try:
                delete_purchase_order_service(po, user=request.user)
                messages.success(request, f"Purchase Order {po_num} deleted.")
                return redirect('projects:project_materials', pk=project.pk)
            except ValueError as e:
                messages.error(request, str(e))

        elif action == 'edit_supplier':
            sup_id = request.POST.get('supplier_id')
            sup = get_object_or_404(Supplier, pk=sup_id)
            sup_edit_form = SupplierForm(request.POST, instance=sup)
            if sup_edit_form.is_valid():
                update_supplier_service(sup, sup_edit_form.cleaned_data, user=request.user)
                messages.success(request, f"Vendor '{sup.name}' details updated.")
                return redirect('projects:project_materials', pk=project.pk)
            else:
                messages.error(request, "Validation error updating vendor.")

        elif action == 'delete_supplier':
            sup_id = request.POST.get('supplier_id')
            sup = get_object_or_404(Supplier, pk=sup_id)
            sup_name = sup.name
            try:
                delete_supplier_service(sup, user=request.user)
                messages.success(request, f"Vendor '{sup_name}' deleted.")
                return redirect('projects:project_materials', pk=project.pk)
            except ValueError as e:
                messages.error(request, str(e))

        elif action == 'reverse_payment':
            pmt_id = request.POST.get('payment_id')
            pmt = get_object_or_404(InvoicePayment, pk=pmt_id, project=project)
            reason = request.POST.get('reason', '')
            try:
                reverse_invoice_payment_service(pmt, user=request.user, reason=reason)
                messages.success(request, f"Payment of ₹{pmt.amount} reversed and invoice balance updated.")
                return redirect('projects:project_materials', pk=project.pk)
            except ValueError as e:
                messages.error(request, str(e))

    invoices = project.material_invoices.all().select_related('supplier', 'purchase_order')
    pos = project.purchase_orders.all().select_related('supplier')
    suppliers = Supplier.objects.all()

    # Summaries
    committed_po = pos.aggregate(tot=Sum('estimated_amount'))['tot'] or Decimal('0.00')
    invoiced_expenses = invoices.exclude(status='CANCELLED').aggregate(tot=Sum('total_amount'))['tot'] or Decimal('0.00')
    paid_to_suppliers = invoices.aggregate(tot=Sum('paid_amount'))['tot'] or Decimal('0.00')
    supplier_dues = invoices.aggregate(tot=Sum('outstanding_balance'))['tot'] or Decimal('0.00')

    context = {
        'project': project,
        'active_tab': 'materials',
        'user_role': request.current_project_role,
        'invoices': invoices,
        'pos': pos,
        'suppliers': suppliers,
        'invoice_form': invoice_form,
        'po_form': po_form,
        'supplier_form': supplier_form,
        'committed_po': committed_po,
        'invoiced_expenses': invoiced_expenses,
        'paid_to_suppliers': paid_to_suppliers,
        'supplier_dues': supplier_dues,
        'payment_form': InvoicePaymentForm(),
    }
    return render(request, 'projects/modules/materials_register.html', context)


@login_required
@project_access_required
def invoice_payment_create_view(request, pk, invoice_id):
    """
    Mandatory Section 6 Feature:
    Record payment (partial, full, or multiple) against a specific vendor invoice,
    recalculate outstanding balances, derive status, and log in financial ledger.
    """
    project = request.current_project
    invoice = get_object_or_404(MaterialInvoice, pk=invoice_id, project=project)

    if request.method == 'POST':
        form = InvoicePaymentForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                record_invoice_payment_service(
                    invoice=invoice,
                    payment_amount=form.cleaned_data['amount'],
                    payment_date=form.cleaned_data['payment_date'],
                    payment_method=form.cleaned_data['payment_method'],
                    ref_no=form.cleaned_data.get('reference_number', ''),
                    notes=form.cleaned_data.get('notes', ''),
                    user=request.user
                )
                messages.success(
                    request,
                    f"Payment of ₹{form.cleaned_data['amount']} recorded for Invoice #{invoice.invoice_number}. New status: {invoice.get_status_display()}."
                )
            except ValueError as e:
                messages.error(request, str(e))
        else:
            messages.error(request, "Invalid payment submission. Please check the values entered.")

    return redirect('projects:project_materials', pk=project.pk)


@login_required
@project_access_required
def project_finance_view(request, pk):
    """Central Financial Ledger with live postings, reversal workflow, and manual transaction entry."""
    project = request.current_project
    form = FinancialTransactionForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'reverse_transaction':
            txn_id = request.POST.get('txn_id')
            txn = get_object_or_404(FinancialTransaction, pk=txn_id, project=project)
            reason = request.POST.get('reason', '')
            try:
                reverse_financial_transaction_service(txn, user=request.user, reason=reason)
                messages.success(request, f"Transaction {txn.transaction_ref} reversed successfully. Central ledger and totals updated.")
                return redirect('projects:project_finance', pk=project.pk)
            except ValueError as e:
                messages.error(request, str(e))
        else:
            form = FinancialTransactionForm(request.POST)
            if form.is_valid():
                txn = form.save(commit=False)
                txn.project = project
                txn.transaction_ref = generate_txn_ref("MAN-TXN")
                txn.created_by = request.user
                if txn.transaction_type == 'EXPENSE':
                    txn.debit_amount = txn.amount
                elif txn.transaction_type in ['PAYMENT_SUPPLIER', 'PAYMENT_LABOUR']:
                    txn.credit_amount = txn.amount
                elif txn.transaction_type == 'RECEIPT_CLIENT':
                    txn.credit_amount = txn.amount
                txn.save()
                messages.success(request, f"Financial Transaction {txn.transaction_ref} posted to central ledger.")
                return redirect('projects:project_finance', pk=project.pk)
            else:
                messages.error(request, "Please correct the form fields before posting.")

    transactions = project.financial_transactions.all().order_by('-transaction_date', '-created_at')

    context = {
        'project': project,
        'active_tab': 'finance',
        'user_role': request.current_project_role,
        'form': form,
        'transactions': transactions,
        'approved_budget': project.get_approved_budget(),
        'recorded_expenditure': project.get_recorded_expenditure(),
        'amount_paid': project.get_amount_paid(),
        'outstanding_liabilities': project.get_outstanding_liabilities(),
        'remaining_budget': project.get_remaining_budget(),
    }
    return render(request, 'projects/modules/finance_ledger.html', context)


@login_required
@project_access_required
def project_budget_view(request, pk):
    """Budget Allocation & Interactive Chart.js breakdown based on real database records."""
    project = request.current_project
    form = BudgetAllocationForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete_allocation':
            alloc_id = request.POST.get('allocation_id')
            delete_budget_allocation_service(project, alloc_id, user=request.user)
            messages.success(request, "Budget allocation category removed and breakdown updated.")
            return redirect('projects:project_budget', pk=project.pk)
        else:
            form = BudgetAllocationForm(request.POST)
            if form.is_valid():
                cat = form.cleaned_data['category']
                amt = form.cleaned_data['allocated_amount']
                notes = form.cleaned_data.get('notes', '')
                BudgetAllocation.objects.update_or_create(
                    project=project,
                    category=cat,
                    defaults={'allocated_amount': amt, 'notes': notes}
                )
                messages.success(request, f"Budget allocation for '{cat}' updated to ₹{amt}.")
                return redirect('projects:project_budget', pk=project.pk)
            else:
                messages.error(request, "Failed to update budget allocation. Please verify the amount.")

    analytics = get_project_budget_analytics(project)

    import json
    context = {
        'project': project,
        'active_tab': 'budget',
        'user_role': request.current_project_role,
        'form': form,
        'approved_budget': project.get_approved_budget(),
        'recorded_expenditure': project.get_recorded_expenditure(),
        'remaining_budget': project.get_remaining_budget(),
        'analytics': analytics,
        'categories_json': json.dumps(analytics['labels']),
        'planned_json': json.dumps(analytics['planned_data']),
        'actual_json': json.dumps(analytics['actual_data']),
    }
    return render(request, 'projects/modules/budget_chart.html', context)



@login_required
@project_access_required
def project_budget_api(request, pk):
    """API endpoint providing real database budget statistics for Chart.js."""
    project = request.current_project
    analytics = get_project_budget_analytics(project)
    return JsonResponse(analytics)


@login_required
@project_access_required
def project_legal_view(request, pk):
    """Legal & Statutory Documents Management."""
    project = request.current_project
    form = LegalDocumentForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'edit_document':
            doc_id = request.POST.get('doc_id')
            doc = get_object_or_404(LegalDocument, pk=doc_id, project=project)
            doc_form = LegalDocumentForm(request.POST, request.FILES, instance=doc)
            if doc_form.is_valid():
                doc_form.save()
                messages.success(request, f"Legal document '{doc.title}' updated successfully.")
                return redirect('projects:project_legal', pk=project.pk)
            else:
                messages.error(request, "Error updating legal document. Please check form inputs.")
        elif action == 'delete_document':
            doc_id = request.POST.get('doc_id')
            doc = get_object_or_404(LegalDocument, pk=doc_id, project=project)
            title = doc.title
            delete_legal_document_service(doc, user=request.user)
            messages.success(request, f"Legal document '{title}' removed from repository.")
            return redirect('projects:project_legal', pk=project.pk)
        else:
            form = LegalDocumentForm(request.POST, request.FILES)
            if form.is_valid():
                doc = form.save(commit=False)
                doc.project = project
                doc.uploaded_by = request.user
                doc.save()
                messages.success(request, f"Legal Document '{doc.title}' uploaded successfully.")
                return redirect('projects:project_legal', pk=project.pk)
            else:
                messages.error(request, "Failed to upload document. Please check form inputs.")

    documents = project.legal_documents.all()
    context = {
        'project': project,
        'active_tab': 'legal',
        'user_role': request.current_project_role,
        'form': form,
        'documents': documents,
    }
    return render(request, 'projects/modules/legal_documents.html', context)


@login_required
@project_access_required
def project_people_view(request, pk):
    """Related People & Stakeholder Directory."""
    project = request.current_project
    form = ProjectContactForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'edit_contact':
            contact_id = request.POST.get('contact_id')
            contact = get_object_or_404(ProjectContact, pk=contact_id, project=project)
            c_form = ProjectContactForm(request.POST, instance=contact)
            if c_form.is_valid():
                c_form.save()
                messages.success(request, f"Contact '{contact.name}' updated successfully.")
                return redirect('projects:project_people', pk=project.pk)
            else:
                messages.error(request, "Error updating contact.")
        elif action == 'delete_contact':
            contact_id = request.POST.get('contact_id')
            contact = get_object_or_404(ProjectContact, pk=contact_id, project=project)
            name = contact.name
            delete_project_contact_service(contact, user=request.user)
            messages.success(request, f"Contact '{name}' removed from project directory.")
            return redirect('projects:project_people', pk=project.pk)
        else:
            form = ProjectContactForm(request.POST)
            if form.is_valid():
                contact = form.save(commit=False)
                contact.project = project
                contact.save()
                messages.success(request, f"Contact '{contact.name}' added to project directory.")
                return redirect('projects:project_people', pk=project.pk)
            else:
                messages.error(request, "Error adding contact.")

    contacts = project.contacts.all()
    memberships = project.memberships.filter(is_active=True).select_related('user')

    context = {
        'project': project,
        'active_tab': 'people',
        'user_role': request.current_project_role,
        'form': form,
        'contacts': contacts,
        'memberships': memberships,
    }
    return render(request, 'projects/modules/related_people.html', context)


@login_required
@project_access_required
def project_diary_view(request, pk):
    """Daily Site Images and Photographic Work Diary."""
    project = request.current_project
    form = DailyDiaryEntryForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'edit_diary':
            entry_id = request.POST.get('entry_id')
            diary = get_object_or_404(DailyDiaryEntry, pk=entry_id, project=project)
            d_form = DailyDiaryEntryForm(request.POST, request.FILES, instance=diary)
            if d_form.is_valid():
                d_form.save()
                messages.success(request, f"Daily progress report for Day {diary.day_number} updated.")
                return redirect('projects:project_diary', pk=project.pk)
            else:
                messages.error(request, "Error updating daily progress report.")
        elif action == 'delete_diary':
            entry_id = request.POST.get('entry_id')
            diary = get_object_or_404(DailyDiaryEntry, pk=entry_id, project=project)
            day_num = diary.day_number
            delete_daily_diary_service(diary, user=request.user)
            messages.success(request, f"Daily report for Day {day_num} removed.")
            return redirect('projects:project_diary', pk=project.pk)
        else:
            form = DailyDiaryEntryForm(request.POST, request.FILES)
            if form.is_valid():
                diary = form.save(commit=False)
                diary.project = project
                diary.supervisor = request.user
                diary.save()
                messages.success(request, f"Site progress report for Day {diary.day_number} ({diary.title}) submitted successfully.")
                return redirect('projects:project_diary', pk=project.pk)
            else:
                messages.error(request, "Error submitting daily site report.")

    entries = project.diary_entries.all()

    context = {
        'project': project,
        'active_tab': 'diary',
        'user_role': request.current_project_role,
        'form': form,
        'entries': entries,
    }
    return render(request, 'projects/modules/daily_diary.html', context)


@login_required
@project_access_required
def project_schedule_view(request, pk):
    """Weekly Work Plan & Scheduling."""
    project = request.current_project
    form = WorkPlanTaskForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'edit_task':
            task_id = request.POST.get('task_id')
            task = get_object_or_404(WorkPlanTask, pk=task_id, project=project)
            t_form = WorkPlanTaskForm(request.POST, instance=task)
            if t_form.is_valid():
                t_form.save()
                messages.success(request, f"Work Task '{task.title}' updated successfully.")
                return redirect('projects:project_schedule', pk=project.pk)
            else:
                messages.error(request, "Error updating work task.")
        elif action == 'delete_task':
            task_id = request.POST.get('task_id')
            task = get_object_or_404(WorkPlanTask, pk=task_id, project=project)
            title = task.title
            delete_work_plan_task_service(task, user=request.user)
            messages.success(request, f"Work task '{title}' removed from schedule.")
            return redirect('projects:project_schedule', pk=project.pk)
        else:
            form = WorkPlanTaskForm(request.POST)
            if form.is_valid():
                task = form.save(commit=False)
                task.project = project
                task.supervisor = request.user
                task.save()
                messages.success(request, f"Work Task '{task.title}' added to schedule.")
                return redirect('projects:project_schedule', pk=project.pk)
            else:
                messages.error(request, "Error adding work plan task.")

    tasks = project.plan_tasks.all()

    context = {
        'project': project,
        'active_tab': 'schedule',
        'user_role': request.current_project_role,
        'form': form,
        'tasks': tasks,
    }
    return render(request, 'projects/modules/work_schedule.html', context)


@login_required
@project_access_required
def project_reports_view(request, pk):
    """Project Executive Reports & Exports."""
    project = request.current_project
    context = {
        'project': project,
        'active_tab': 'reports',
        'user_role': request.current_project_role,
    }
    return render(request, 'projects/modules/project_reports.html', context)


@login_required
@project_access_required
def export_ledger_csv(request, pk):
    """Export project financial ledger as CSV."""
    project = request.current_project
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{project.code}_financial_ledger.csv"'

    writer = csv.writer(response)
    writer.writerow(['Transaction Ref', 'Date', 'Type', 'Category', 'Description', 'Debit (INR)', 'Credit (INR)', 'Status'])

    for tx in project.financial_transactions.all():
        writer.writerow([
            tx.transaction_ref,
            tx.transaction_date,
            tx.transaction_type,
            tx.category,
            tx.description,
            tx.debit_amount,
            tx.credit_amount,
            tx.payment_status
        ])
    return response


@login_required
@project_access_required
def export_labour_csv(request, pk):
    """Export daily site labour muster roll as CSV."""
    project = request.current_project
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{project.code}_labour_muster.csv"'

    writer = csv.writer(response)
    writer.writerow(['Date', 'Trade Category', 'Location / Floor', 'Workers', 'Daily Wage Rate (INR)', 'Gross Wages (INR)', 'Paid (INR)', 'Outstanding (INR)'])

    for lbr in project.labour_entries.all():
        writer.writerow([
            lbr.date,
            lbr.category,
            lbr.location_floor,
            lbr.workers_count,
            lbr.wage_rate_per_day,
            lbr.gross_wages,
            lbr.paid_amount,
            lbr.outstanding_amount
        ])
    return response


@login_required
@project_access_required
def export_materials_csv(request, pk):
    """Export materials & procurement invoices as CSV."""
    project = request.current_project
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{project.code}_materials_invoices.csv"'

    writer = csv.writer(response)
    writer.writerow(['Invoice Ref', 'Date', 'Supplier', 'Description', 'Quantity', 'Total Amount (INR)', 'Paid Amount (INR)', 'Outstanding (INR)', 'Status'])

    for inv in project.material_invoices.all():
        writer.writerow([
            inv.invoice_number,
            inv.invoice_date,
            inv.supplier.name,
            inv.material_description,
            inv.quantity,
            inv.total_amount,
            inv.paid_amount,
            inv.outstanding_balance,
            inv.status
        ])
    return response


@login_required
@project_access_required
def project_settings_view(request, pk):
    """Project Parameters & Configuration."""
    project = request.current_project

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_status':
            status = request.POST.get('status')
            progress = request.POST.get('progress')
            if status in ProjectStatusChoices.values:
                project.status = status
            if progress is not None:
                try:
                    project.progress_percentage = max(0, min(100, int(progress)))
                except ValueError:
                    pass
            project.save()
            messages.success(request, "Project parameters updated successfully.")
            return redirect('projects:project_settings', pk=project.pk)

        elif action == 'archive_project':
            project.status = ProjectStatusChoices.ARCHIVED
            project.save()
            messages.warning(request, f"Project {project.code} has been archived.")
            return redirect('projects:project_list')

        elif action == 'delete_project':
            if not request.user.is_company_admin:
                messages.error(request, "Permission denied. Only Company Administrators can permanently delete a project.")
                return redirect('projects:project_settings', pk=project.pk)
            code = project.code
            delete_project_service(project, user=request.user)
            messages.warning(request, f"Project {code} has been permanently deleted.")
            return redirect('projects:project_list')

        elif action == 'edit_project':
            if not request.user.can_manage_project(project):
                messages.error(request, "Permission denied. Only Administrators and Project Managers can update project details.")
                return redirect('projects:project_settings', pk=project.pk)
            project_form = ProjectForm(request.POST, request.FILES, instance=project)
            if project_form.is_valid():
                project_form.save()
                messages.success(request, f"Project '{project.name}' details updated successfully.")
                return redirect('projects:project_settings', pk=project.pk)
            else:
                messages.error(request, "Validation error while updating project parameters.")

    project_edit_form = ProjectForm(instance=project)
    context = {
        'project': project,
        'active_tab': 'settings',
        'user_role': request.current_project_role,
        'status_choices': ProjectStatusChoices.choices,
        'project_edit_form': project_edit_form,
    }
    return render(request, 'projects/modules/project_settings.html', context)

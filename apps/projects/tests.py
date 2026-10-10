from django.test import TestCase, Client
from django.urls import reverse
from decimal import Decimal
from datetime import date, timedelta
from apps.accounts.models import User, ProjectMembership, RoleChoices
from apps.projects.models import (
    Project, ProjectStatusChoices,
    LabourEntry, Supplier, MaterialInvoice, InvoicePayment,
    FinancialTransaction, BudgetAllocation,
    MaterialPurchaseOrder, LegalDocument, ProjectContact,
    DailyDiaryEntry, WorkPlanTask, InvoiceStatusChoices,
)
from apps.projects.utils import format_inr
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
)


class ProjectStage2TestCase(TestCase):
    def setUp(self):
        self.client = Client()

        self.super_admin = User.objects.create_superuser(
            username='admin_stage2',
            email='admin2@example.com',
            password='Password123!',
            primary_role=RoleChoices.SUPER_ADMIN,
            is_approved=True
        )

        self.pm_user = User.objects.create_user(
            username='pm_stage2',
            email='pm2@example.com',
            password='Password123!',
            primary_role=RoleChoices.PROJECT_MANAGER,
            is_approved=True
        )

        self.supervisor = User.objects.create_user(
            username='supervisor_stage2',
            email='sup2@example.com',
            password='Password123!',
            primary_role=RoleChoices.SITE_SUPERVISOR,
            is_approved=True
        )

        self.project_1 = Project.objects.create(
            name='Skyline Heights',
            code='PRJ-TEST-001',
            location='Downtown Metropolitan',
            client_name='Vanguard Real Estate',
            approved_initial_budget=Decimal('10000000.00'),
            start_date=date(2026, 1, 1),
            expected_completion_date=date(2027, 12, 31),
            status=ProjectStatusChoices.ACTIVE,
            progress_percentage=25,
            created_by=self.super_admin
        )

        self.project_2 = Project.objects.create(
            name='Lakeside Villas',
            code='PRJ-TEST-002',
            location='Lakeview District',
            client_name='Sunset Holdings',
            approved_initial_budget=Decimal('4500000.00'),
            start_date=date(2026, 2, 1),
            expected_completion_date=date(2027, 6, 30),
            status=ProjectStatusChoices.PLANNING,
            progress_percentage=5,
            created_by=self.super_admin
        )

        # Supervisor is only assigned to Project 1
        ProjectMembership.objects.create(
            user=self.supervisor,
            project=self.project_1,
            role=RoleChoices.SITE_SUPERVISOR,
            is_active=True
        )

    def test_project_list_shows_all_for_superadmin(self):
        """Superadmin can see all projects."""
        self.client.login(username='admin_stage2', password='Password123!')
        response = self.client.get(reverse('projects:project_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Skyline Heights')
        self.assertContains(response, 'Lakeside Villas')

    def test_project_list_restricted_for_supervisor(self):
        """Supervisor only sees assigned projects."""
        self.client.login(username='supervisor_stage2', password='Password123!')
        response = self.client.get(reverse('projects:project_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Skyline Heights')
        self.assertNotContains(response, 'Lakeside Villas')

    def test_project_list_search_and_filter(self):
        """Search query filters results appropriately."""
        self.client.login(username='admin_stage2', password='Password123!')
        response = self.client.get(reverse('projects:project_list'), {'q': 'Skyline'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Skyline Heights')
        self.assertNotContains(response, 'Lakeside Villas')

        # Status filter
        response = self.client.get(reverse('projects:project_list'), {'status': 'PLANNING'})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Skyline Heights')
        self.assertContains(response, 'Lakeside Villas')

    def test_project_detail_access_control(self):
        """Supervisor cannot access project they are not assigned to."""
        self.client.login(username='supervisor_stage2', password='Password123!')
        # Access allowed to project 1
        response = self.client.get(reverse('projects:project_detail', kwargs={'pk': self.project_1.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Skyline Heights')

        # Access denied to project 2
        response = self.client.get(reverse('projects:project_detail', kwargs={'pk': self.project_2.pk}))
        self.assertEqual(response.status_code, 403)

    def test_project_creation_validations(self):
        """Test ProjectForm validations: duplicate code, date sanity, budget."""
        self.client.login(username='admin_stage2', password='Password123!')

        # Duplicate project code
        response = self.client.post(reverse('projects:project_create'), {
            'name': 'Duplicate Project',
            'code': 'PRJ-TEST-001', # Already exists
            'location': 'City Center',
            'client_name': 'Client A',
            'approved_initial_budget': '1000000.00',
            'start_date': '2026-01-01',
            'expected_completion_date': '2027-01-01',
            'status': 'ACTIVE',
            'progress_percentage': '0',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")

        # Invalid dates: end before start
        response = self.client.post(reverse('projects:project_create'), {
            'name': 'Time Machine Project',
            'code': 'PRJ-TEST-999',
            'location': 'City Center',
            'client_name': 'Client A',
            'approved_initial_budget': '1000000.00',
            'start_date': '2027-01-01',
            'expected_completion_date': '2026-01-01',
            'status': 'ACTIVE',
            'progress_percentage': '0',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Expected completion date cannot be earlier than start date")

        # Valid project creation
        response = self.client.post(reverse('projects:project_create'), {
            'name': 'Pinnacle Tower',
            'code': 'PRJ-TEST-003',
            'project_type': 'Commercial High-Rise',
            'location': 'Financial District',
            'client_name': 'Apex Investments',
            'approved_initial_budget': '25000000.00',
            'start_date': '2026-05-01',
            'expected_completion_date': '2028-12-31',
            'status': 'ACTIVE',
            'progress_percentage': '10',
            'description': '30-story commercial tower.',
        })
        self.assertEqual(response.status_code, 302)
        created_p = Project.objects.get(code='PRJ-TEST-003')
        self.assertEqual(created_p.name, 'Pinnacle Tower')


# ───────────────────────────────────────────────────────────────────
# Test Suite: INR Currency Formatter
# ───────────────────────────────────────────────────────────────────
class INRFormatterTestCase(TestCase):
    """Verifies the Indian Rupee digit-grouping logic in format_inr()."""

    def test_crore_formatting(self):
        result = format_inr(Decimal('45000000.00'))
        self.assertEqual(result, '₹4,50,00,000.00')

    def test_lakh_formatting(self):
        result = format_inr(Decimal('125000.00'))
        self.assertEqual(result, '₹1,25,000.00')

    def test_sub_lakh_formatting(self):
        result = format_inr(Decimal('99999.99'))
        self.assertEqual(result, '₹99,999.99')

    def test_thousand_formatting(self):
        result = format_inr(Decimal('5000.00'))
        self.assertEqual(result, '₹5,000.00')

    def test_zero(self):
        result = format_inr(Decimal('0.00'))
        self.assertEqual(result, '₹0.00')

    def test_large_budget(self):
        result = format_inr(Decimal('450000000.00'))
        self.assertEqual(result, '₹45,00,00,000.00')

    def test_symbol_excluded(self):
        from apps.projects.utils import format_inr
        result = format_inr(Decimal('1000.00'), symbol='')
        self.assertNotIn('₹', result)
        self.assertIn(',', result)

    def test_no_agency_content_on_homepage(self):
        """Verify construction terminology replaces agency language on project list page."""
        user = User.objects.create_superuser(
            username='content_check',
            email='content@example.com',
            password='Test@12345',
            is_approved=True
        )
        self.client.login(username='content_check', password='Test@12345')
        response = self.client.get(reverse('projects:project_list'))
        content = response.content.decode('utf-8')

        # Should NOT contain agency text
        self.assertNotIn('We create modern websites', content)
        self.assertNotIn('Selected work', content)
        self.assertNotIn('web development agency', content)

        # Should contain construction management text
        self.assertIn('Construction', content)
        self.assertIn('Every Project', content)


# ───────────────────────────────────────────────────────────────────
# Test Suite: Labour Entry Service
# ───────────────────────────────────────────────────────────────────
class LabourEntryServiceTestCase(TestCase):
    """Verifies labour entry creation, gross wage calculation, and ledger posting."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='labour_test_admin',
            email='labour@test.com',
            password='Test@12345',
            is_approved=True
        )
        self.project = Project.objects.create(
            name='Labour Test Project',
            code='PRJ-LBR-001',
            location='Test City',
            client_name='Test Client',
            approved_initial_budget=Decimal('5000000.00'),
            start_date=date(2026, 1, 1),
            expected_completion_date=date(2027, 1, 1),
            status=ProjectStatusChoices.ACTIVE,
            created_by=self.user
        )

    def test_labour_entry_creates_record(self):
        entry = record_labour_entry_service(self.project, {
            'date': date(2026, 6, 1),
            'category': 'Masonry Gang',
            'location_floor': 'Floor 5',
            'workers_count': 10,
            'wage_rate_per_day': Decimal('700.00'),
            'overtime_hours': Decimal('0.00'),
            'overtime_rate_per_hour': Decimal('0.00'),
            'paid_amount': Decimal('0.00'),
        }, user=self.user)

        self.assertIsNotNone(entry.pk)
        self.assertEqual(entry.category, 'Masonry Gang')
        self.assertEqual(entry.gross_wages, Decimal('7000.00'))

    def test_labour_entry_posts_to_ledger(self):
        """A labour entry must auto-create a PAYMENT_LABOUR transaction in the central ledger."""
        record_labour_entry_service(self.project, {
            'date': date(2026, 6, 1),
            'category': 'Carpentry',
            'location_floor': 'Basement -1',
            'workers_count': 5,
            'wage_rate_per_day': Decimal('800.00'),
            'overtime_hours': Decimal('2.00'),
            'overtime_rate_per_hour': Decimal('100.00'),
            'paid_amount': Decimal('4000.00'),
        }, user=self.user)

        txns = FinancialTransaction.objects.filter(
            project=self.project,
            transaction_type='PAYMENT_LABOUR'
        )
        self.assertTrue(txns.exists())

    def test_outstanding_wages_calculation(self):
        entry = record_labour_entry_service(self.project, {
            'date': date(2026, 6, 1),
            'category': 'Steel Fixers',
            'location_floor': 'Floor 7',
            'workers_count': 8,
            'wage_rate_per_day': Decimal('900.00'),
            'overtime_hours': Decimal('0.00'),
            'overtime_rate_per_hour': Decimal('0.00'),
            'paid_amount': Decimal('3000.00'),
        }, user=self.user)

        self.assertEqual(entry.outstanding_amount, Decimal('4200.00'))  # 8*900 = 7200 - 3000 = 4200


# ───────────────────────────────────────────────────────────────────
# Test Suite: Invoice Payment Workflow
# ───────────────────────────────────────────────────────────────────
class InvoicePaymentWorkflowTestCase(TestCase):
    """Verifies invoice status transitions: UNPAID → PARTIALLY_PAID → PAID."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='inv_test_admin',
            email='inv@test.com',
            password='Test@12345',
            is_approved=True
        )
        self.project = Project.objects.create(
            name='Invoice Test Project',
            code='PRJ-INV-001',
            location='Test City',
            client_name='Test Client',
            approved_initial_budget=Decimal('10000000.00'),
            start_date=date(2026, 1, 1),
            expected_completion_date=date(2027, 1, 1),
            status=ProjectStatusChoices.ACTIVE,
            created_by=self.user
        )
        self.supplier = Supplier.objects.create(
            name='UltraTech Cement',
            phone='9876543210'
        )

    def test_new_invoice_is_unpaid(self):
        invoice = create_material_invoice_service(self.project, {
            'supplier': self.supplier,
            'invoice_number': 'INV-TEST-001',
            'invoice_date': date(2026, 6, 1),
            'material_description': 'OPC 53 Cement 500 bags',
            'quantity': '500 Bags',
            'total_amount': Decimal('100000.00'),
            'tax_amount': Decimal('18000.00'),
        }, user=self.user)

        self.assertEqual(invoice.status, 'UNPAID')
        self.assertEqual(invoice.paid_amount, Decimal('0.00'))
        self.assertEqual(invoice.outstanding_balance, Decimal('100000.00'))

    def test_partial_payment_changes_status(self):
        invoice = create_material_invoice_service(self.project, {
            'supplier': self.supplier,
            'invoice_number': 'INV-TEST-002',
            'invoice_date': date(2026, 6, 1),
            'material_description': 'TMT Steel 20mm',
            'quantity': '10 MT',
            'total_amount': Decimal('200000.00'),
            'tax_amount': Decimal('0.00'),
        }, user=self.user)

        record_invoice_payment_service(
            invoice=invoice,
            payment_amount=Decimal('80000.00'),
            payment_date=date(2026, 6, 15),
            payment_method='BANK_TRANSFER',
            ref_no='UTR001',
            user=self.user
        )
        invoice.refresh_from_db()

        self.assertEqual(invoice.status, 'PARTIALLY_PAID')
        self.assertEqual(invoice.paid_amount, Decimal('80000.00'))
        self.assertEqual(invoice.outstanding_balance, Decimal('120000.00'))

    def test_full_payment_marks_paid(self):
        invoice = create_material_invoice_service(self.project, {
            'supplier': self.supplier,
            'invoice_number': 'INV-TEST-003',
            'invoice_date': date(2026, 6, 1),
            'material_description': 'River Sand',
            'quantity': '200 Cu.m',
            'total_amount': Decimal('50000.00'),
            'tax_amount': Decimal('0.00'),
        }, user=self.user)

        record_invoice_payment_service(
            invoice=invoice,
            payment_amount=Decimal('50000.00'),
            payment_date=date(2026, 6, 20),
            payment_method='CHEQUE',
            user=self.user
        )
        invoice.refresh_from_db()

        self.assertEqual(invoice.status, 'PAID')
        self.assertEqual(invoice.outstanding_balance, Decimal('0.00'))

    def test_overpayment_raises_error(self):
        invoice = create_material_invoice_service(self.project, {
            'supplier': self.supplier,
            'invoice_number': 'INV-TEST-004',
            'invoice_date': date(2026, 6, 1),
            'material_description': 'Test Material',
            'quantity': '1 Unit',
            'total_amount': Decimal('10000.00'),
            'tax_amount': Decimal('0.00'),
        }, user=self.user)

        with self.assertRaises(ValueError):
            record_invoice_payment_service(
                invoice=invoice,
                payment_amount=Decimal('15000.00'),  # More than total
                payment_date=date(2026, 6, 20),
                payment_method='BANK_TRANSFER',
                user=self.user
            )

    def test_multiple_partial_payments(self):
        """Multiple partial payments should sum correctly and reach PAID."""
        invoice = create_material_invoice_service(self.project, {
            'supplier': self.supplier,
            'invoice_number': 'INV-TEST-005',
            'invoice_date': date(2026, 6, 1),
            'material_description': 'Aggregate',
            'quantity': '100 MT',
            'total_amount': Decimal('30000.00'),
            'tax_amount': Decimal('0.00'),
        }, user=self.user)

        record_invoice_payment_service(
            invoice=invoice, payment_amount=Decimal('10000.00'),
            payment_date=date(2026, 6, 5), payment_method='BANK_TRANSFER', user=self.user
        )
        record_invoice_payment_service(
            invoice=invoice, payment_amount=Decimal('10000.00'),
            payment_date=date(2026, 6, 10), payment_method='BANK_TRANSFER', user=self.user
        )
        record_invoice_payment_service(
            invoice=invoice, payment_amount=Decimal('10000.00'),
            payment_date=date(2026, 6, 15), payment_method='CHEQUE', user=self.user
        )
        invoice.refresh_from_db()

        self.assertEqual(invoice.status, 'PAID')
        self.assertEqual(invoice.paid_amount, Decimal('30000.00'))
        payments_count = InvoicePayment.objects.filter(invoice=invoice).count()
        self.assertEqual(payments_count, 3)


# ───────────────────────────────────────────────────────────────────
# Test Suite: Budget Analytics
# ───────────────────────────────────────────────────────────────────
class BudgetAnalyticsTestCase(TestCase):
    """Verifies get_project_budget_analytics() returns correct data structure."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='budget_test_admin',
            email='budget@test.com',
            password='Test@12345',
            is_approved=True
        )
        self.project = Project.objects.create(
            name='Budget Analytics Project',
            code='PRJ-BGT-001',
            location='Test City',
            client_name='Test Client',
            approved_initial_budget=Decimal('10000000.00'),
            start_date=date(2026, 1, 1),
            expected_completion_date=date(2027, 1, 1),
            status=ProjectStatusChoices.ACTIVE,
            created_by=self.user
        )

    def test_analytics_returns_correct_keys(self):
        analytics = get_project_budget_analytics(self.project)
        self.assertIn('labels', analytics)
        self.assertIn('planned_data', analytics)
        self.assertIn('actual_data', analytics)
        self.assertIn('breakdown', analytics)

    def test_analytics_five_categories(self):
        analytics = get_project_budget_analytics(self.project)
        self.assertEqual(len(analytics['labels']), 5)
        self.assertEqual(len(analytics['planned_data']), 5)
        self.assertEqual(len(analytics['actual_data']), 5)

    def test_planned_sums_to_budget_with_default_ratios(self):
        """Without explicit BudgetAllocations, default ratios must sum to approved budget."""
        analytics = get_project_budget_analytics(self.project)
        total_planned = sum(analytics['planned_data'])
        self.assertAlmostEqual(total_planned, float(self.project.get_approved_budget()), places=0)

    def test_custom_allocation_overrides_default(self):
        BudgetAllocation.objects.create(
            project=self.project,
            category='Labour & Manpower',
            allocated_amount=Decimal('3000000.00')
        )
        analytics = get_project_budget_analytics(self.project)
        labour_idx = analytics['labels'].index('Labour & Manpower')
        self.assertAlmostEqual(analytics['planned_data'][labour_idx], 3000000.00, places=0)


# ───────────────────────────────────────────────────────────────────
# Test Suite: Safe Deletion, Edits, Reversals & Recalculation
# ───────────────────────────────────────────────────────────────────
class SafeDeletionAndReversalTestCase(TestCase):
    """
    Comprehensive tests for safe deletion, audit reversals, and automatic financial recalculations
    across Labour, Materials, Ledger, Budget, Statutory, and Project governance.
    """

    def setUp(self):
        self.client = Client()

        self.admin = User.objects.create_superuser(
            username='admin_safe',
            email='admin_safe@example.com',
            password='Password123!',
            primary_role=RoleChoices.SUPER_ADMIN,
            is_approved=True
        )

        self.pm_user = User.objects.create_user(
            username='pm_safe',
            email='pm_safe@example.com',
            password='Password123!',
            primary_role=RoleChoices.PROJECT_MANAGER,
            is_approved=True
        )

        self.supervisor = User.objects.create_user(
            username='supervisor_safe',
            email='sup_safe@example.com',
            password='Password123!',
            primary_role=RoleChoices.SITE_SUPERVISOR,
            is_approved=True
        )

        self.project_1 = Project.objects.create(
            name='Oceanic Heights',
            code='PRJ-SAFE-001',
            location='Coastal Road, Mumbai',
            client_name='Oceanic Developers Ltd',
            approved_initial_budget=Decimal('50000000.00'),
            start_date=date(2026, 1, 1),
            expected_completion_date=date(2028, 12, 31),
            status=ProjectStatusChoices.ACTIVE,
            progress_percentage=20,
            created_by=self.admin
        )

        self.project_2 = Project.objects.create(
            name='Pinecrest Commercial',
            code='PRJ-SAFE-002',
            location='Bandra Kurla Complex, Mumbai',
            client_name='Pinecrest Infra',
            approved_initial_budget=Decimal('80000000.00'),
            start_date=date(2026, 2, 1),
            expected_completion_date=date(2028, 6, 30),
            status=ProjectStatusChoices.ACTIVE,
            progress_percentage=10,
            created_by=self.admin
        )

        # Memberships
        ProjectMembership.objects.create(
            user=self.pm_user,
            project=self.project_1,
            role=RoleChoices.PROJECT_MANAGER,
            is_active=True
        )
        ProjectMembership.objects.create(
            user=self.supervisor,
            project=self.project_1,
            role=RoleChoices.SITE_SUPERVISOR,
            is_active=True
        )

        # Vendor
        self.supplier = Supplier.objects.create(
            name='Tata Steel Supplies',
            contact_person='Rajesh Kumar',
            phone='+91 98200 12345',
            email='sales@tatasteel.mock',
            gst_number='27AAACT2727Q1ZB'
        )

    def test_labour_entry_edit_recalculates_financials(self):
        """Editing labour attendance updates gross wages, dues, and linked financial ledger entry."""
        self.client.login(username='admin_safe', password='Password123!')

        # Create entry: 10 workers @ 500 = 5000 gross, 2000 paid => 3000 dues
        entry = record_labour_entry_service(self.project_1, {
            'date': date(2026, 3, 1),
            'category': 'Masonry & Concreting',
            'location_floor': 'Basement B1',
            'workers_count': 10,
            'wage_rate_per_day': Decimal('500.00'),
            'paid_amount': Decimal('2000.00'),
            'notes': 'Initial muster'
        }, user=self.admin)

        self.assertEqual(entry.gross_wages, Decimal('5000.00'))
        self.assertEqual(entry.outstanding_amount, Decimal('3000.00'))
        self.assertEqual(self.project_1.get_recorded_expenditure(), Decimal('5000.00'))

        # Edit entry: 15 workers @ 600 = 9000 gross, 4000 paid => 5000 dues
        response = self.client.post(reverse('projects:project_labour', kwargs={'pk': self.project_1.pk}), {
            'action': 'edit_labour',
            'entry_id': entry.pk,
            'date': '2026-03-01',
            'category': 'Masonry & Concreting',
            'location_floor': 'Basement B1 - Podia',
            'workers_count': 15,
            'wage_rate_per_day': '600.00',
            'paid_amount': '4000.00',
            'notes': 'Updated muster after overtime check'
        })
        self.assertEqual(response.status_code, 302)

        entry.refresh_from_db()
        self.assertEqual(entry.workers_count, 15)
        self.assertEqual(entry.wage_rate_per_day, Decimal('600.00'))
        self.assertEqual(entry.gross_wages, Decimal('9000.00'))
        self.assertEqual(entry.paid_amount, Decimal('4000.00'))
        self.assertEqual(entry.outstanding_amount, Decimal('5000.00'))

        # Verify linked ledger transaction was updated and project expenditure reflects change
        tx = FinancialTransaction.objects.get(related_labour=entry)
        self.assertEqual(tx.amount, Decimal('9000.00'))
        self.assertEqual(tx.debit_amount, Decimal('9000.00'))
        self.assertEqual(self.project_1.get_recorded_expenditure(), Decimal('9000.00'))
        self.assertEqual(self.project_1.get_amount_paid(), Decimal('4000.00'))
        self.assertEqual(self.project_1.get_outstanding_liabilities(), Decimal('5000.00'))

    def test_labour_entry_delete_cleans_linked_ledger_and_recalculates(self):
        """Deleting draft/erroneous labour entry removes entry & ledger, refreshing all totals."""
        self.client.login(username='admin_safe', password='Password123!')

        entry = record_labour_entry_service(self.project_1, {
            'date': date(2026, 3, 2),
            'category': 'Carpentry & Shuttering',
            'location_floor': 'Floor 3 Slab',
            'workers_count': 8,
            'wage_rate_per_day': Decimal('700.00'),
            'paid_amount': Decimal('0.00'),
            'notes': 'Draft entered in error'
        }, user=self.admin)

        self.assertEqual(self.project_1.get_recorded_expenditure(), Decimal('5600.00'))
        self.assertTrue(FinancialTransaction.objects.filter(related_labour=entry).exists())

        # Delete entry via POST with CSRF
        response = self.client.post(reverse('projects:project_labour', kwargs={'pk': self.project_1.pk}), {
            'action': 'delete_labour',
            'entry_id': entry.pk
        })
        self.assertEqual(response.status_code, 302)

        self.assertFalse(LabourEntry.objects.filter(pk=entry.pk).exists())
        self.assertFalse(FinancialTransaction.objects.filter(related_labour_id=entry.pk).exists())
        self.assertEqual(self.project_1.get_recorded_expenditure(), Decimal('0.00'))
        self.assertEqual(self.project_1.get_outstanding_liabilities(), Decimal('0.00'))

    def test_unpaid_invoice_hard_delete(self):
        """Unpaid invoice can be safely deleted, removing pending liability and ledger posting."""
        self.client.login(username='admin_safe', password='Password123!')

        invoice = create_material_invoice_service(self.project_1, {
            'supplier': self.supplier,
            'invoice_number': 'INV-TEST-UNPAID',
            'invoice_date': date(2026, 3, 5),
            'material_description': 'TMT 550D Rebar 12mm (20 MT)',
            'quantity': '20 MT',
            'total_amount': Decimal('1200000.00'),
            'tax_amount': Decimal('216000.00'),
            'notes': 'Unpaid pending delivery inspection'
        }, user=self.admin)

        self.assertEqual(self.project_1.get_recorded_expenditure(), Decimal('1200000.00'))
        self.assertEqual(self.project_1.get_outstanding_liabilities(), Decimal('1200000.00'))

        # Delete unpaid invoice
        response = self.client.post(reverse('projects:project_materials', kwargs={'pk': self.project_1.pk}), {
            'action': 'delete_invoice',
            'invoice_id': invoice.pk
        })
        self.assertEqual(response.status_code, 302)

        self.assertFalse(MaterialInvoice.objects.filter(pk=invoice.pk).exists())
        self.assertFalse(FinancialTransaction.objects.filter(related_invoice_id=invoice.pk).exists())
        self.assertEqual(self.project_1.get_recorded_expenditure(), Decimal('0.00'))
        self.assertEqual(self.project_1.get_outstanding_liabilities(), Decimal('0.00'))

    def test_paid_invoice_cancellation_and_audit_trail_preservation(self):
        """
        Posted invoice with recorded payments cannot be silently dropped.
        Cancelling marks it CANCELLED, reverses payments & ledger txns with full audit history.
        """
        self.client.login(username='admin_safe', password='Password123!')

        invoice = create_material_invoice_service(self.project_1, {
            'supplier': self.supplier,
            'invoice_number': 'INV-TEST-PAID-01',
            'invoice_date': date(2026, 3, 5),
            'material_description': 'Ready Mix Concrete Grade M35',
            'quantity': '100 Cu.M',
            'total_amount': Decimal('500000.00'),
            'notes': 'Delivered and partially settled'
        }, user=self.admin)

        # Record payment of 200,000
        payment = record_invoice_payment_service(invoice, {
            'amount': Decimal('200000.00'),
            'payment_date': date(2026, 3, 6),
            'payment_method': 'NEFT',
            'reference_number': 'UTR-NEFT-998811',
            'notes': 'Part payment on delivery'
        }, user=self.admin)

        self.assertEqual(invoice.status, InvoiceStatusChoices.PARTIALLY_PAID)
        self.assertEqual(self.project_1.get_recorded_expenditure(), Decimal('500000.00'))
        self.assertEqual(self.project_1.get_amount_paid(), Decimal('200000.00'))

        # Cancel/Delete invoice via POST
        response = self.client.post(reverse('projects:project_materials', kwargs={'pk': self.project_1.pk}), {
            'action': 'delete_invoice',
            'invoice_id': invoice.pk
        })
        self.assertEqual(response.status_code, 302)

        # Invoice still exists in database for statutory audit, but status is CANCELLED
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatusChoices.CANCELLED)

        # Payment is reversed
        payment.refresh_from_db()
        self.assertTrue(payment.is_reversed)

        # Ledger transactions are marked reversed
        txns = FinancialTransaction.objects.filter(related_invoice=invoice)
        for tx in txns:
            self.assertTrue(tx.is_reversed)
            self.assertEqual(tx.payment_status, 'REVERSED')

        # Recalculations exclude cancelled invoice and reversed payments
        self.assertEqual(self.project_1.get_recorded_expenditure(), Decimal('0.00'))
        self.assertEqual(self.project_1.get_amount_paid(), Decimal('0.00'))
        self.assertEqual(self.project_1.get_outstanding_liabilities(), Decimal('0.00'))

    def test_reverse_invoice_payment_restores_balance(self):
        """Reversing a specific payment restores invoice dues and voids ledger payment transaction."""
        self.client.login(username='admin_safe', password='Password123!')

        invoice = create_material_invoice_service(self.project_1, {
            'supplier': self.supplier,
            'invoice_number': 'INV-REV-PAY-01',
            'invoice_date': date(2026, 3, 8),
            'material_description': 'Structural Steel Angle & Channels',
            'quantity': '15 MT',
            'total_amount': Decimal('900000.00'),
        }, user=self.admin)

        payment = record_invoice_payment_service(invoice, {
            'amount': Decimal('300000.00'),
            'payment_date': date(2026, 3, 9),
            'payment_method': 'CHEQUE',
            'reference_number': 'CHQ-778899',
            'notes': 'Account payee cheque'
        }, user=self.admin)

        invoice.refresh_from_db()
        self.assertEqual(invoice.outstanding_balance, Decimal('600000.00'))
        self.assertEqual(self.project_1.get_amount_paid(), Decimal('300000.00'))

        # Reverse payment via POST
        response = self.client.post(reverse('projects:project_materials', kwargs={'pk': self.project_1.pk}), {
            'action': 'reverse_payment',
            'payment_id': payment.pk,
            'reason': 'Cheque returned dishonoured by bank'
        })
        self.assertEqual(response.status_code, 302)

        payment.refresh_from_db()
        self.assertTrue(payment.is_reversed)
        self.assertIn('Cheque returned dishonoured by bank', payment.notes)

        # Invoice balance restored to 900,000 and status back to PENDING
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatusChoices.PENDING)
        self.assertEqual(invoice.paid_amount, Decimal('0.00'))
        self.assertEqual(invoice.outstanding_balance, Decimal('900000.00'))

        # Project amount paid decreases back to 0
        self.assertEqual(self.project_1.get_amount_paid(), Decimal('0.00'))
        self.assertEqual(self.project_1.get_outstanding_liabilities(), Decimal('900000.00'))

    def test_purchase_order_deletion_protected_against_active_invoices(self):
        """Purchase order cannot be deleted if active material invoices reference it."""
        self.client.login(username='admin_safe', password='Password123!')

        po = MaterialPurchaseOrder.objects.create(
            project=self.project_1,
            supplier=self.supplier,
            po_number='PO-MUM-2026-001',
            category='Structural Steel',
            description='TMT 16mm fe500D bars',
            quantity='50 MT',
            estimated_amount=Decimal('3000000.00'),
            status='Approved',
            order_date=date(2026, 3, 10),
            created_by=self.admin
        )

        # Create active invoice referencing this PO
        invoice = create_material_invoice_service(self.project_1, {
            'purchase_order': po,
            'supplier': self.supplier,
            'invoice_number': 'INV-PO-REF-01',
            'invoice_date': date(2026, 3, 12),
            'material_description': 'Batch 1 of TMT bars',
            'quantity': '20 MT',
            'total_amount': Decimal('1200000.00'),
        }, user=self.admin)

        # Attempt to delete PO -> should fail with error message
        response = self.client.post(reverse('projects:project_materials', kwargs={'pk': self.project_1.pk}), {
            'action': 'delete_po',
            'po_id': po.pk
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(MaterialPurchaseOrder.objects.filter(pk=po.pk).exists())

        # Delete/Cancel invoice first
        cancel_or_delete_material_invoice_service(invoice, user=self.admin)

        # Now PO can be deleted
        response = self.client.post(reverse('projects:project_materials', kwargs={'pk': self.project_1.pk}), {
            'action': 'delete_po',
            'po_id': po.pk
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(MaterialPurchaseOrder.objects.filter(pk=po.pk).exists())

    def test_supplier_deletion_protected_when_records_exist(self):
        """Supplier cannot be deleted when purchase orders or invoices link to it."""
        self.client.login(username='admin_safe', password='Password123!')

        po = MaterialPurchaseOrder.objects.create(
            project=self.project_1,
            supplier=self.supplier,
            po_number='PO-SUP-CHECK-01',
            category='Cement',
            description='PPC 53 Grade',
            quantity='500 Bags',
            estimated_amount=Decimal('200000.00'),
            order_date=date(2026, 3, 10),
            created_by=self.admin
        )

        response = self.client.post(reverse('projects:project_materials', kwargs={'pk': self.project_1.pk}), {
            'action': 'delete_supplier',
            'supplier_id': self.supplier.pk
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Supplier.objects.filter(pk=self.supplier.pk).exists())

        # An unlinked supplier can be deleted
        orphan_supplier = Supplier.objects.create(name='Temporary Hardware Shop')
        response = self.client.post(reverse('projects:project_materials', kwargs={'pk': self.project_1.pk}), {
            'action': 'delete_supplier',
            'supplier_id': orphan_supplier.pk
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Supplier.objects.filter(pk=orphan_supplier.pk).exists())

    def test_manual_financial_transaction_reversal(self):
        """Direct manual ledger transactions can be reversed with mandatory audit justification."""
        self.client.login(username='admin_safe', password='Password123!')

        txn = FinancialTransaction.objects.create(
            project=self.project_1,
            transaction_ref='TXN-TEST-MANUAL-01',
            transaction_date=date(2026, 3, 15),
            transaction_type='EXPENSE',
            category='Equipment & Machinery',
            description='Mobile crane rental for tower assembly',
            amount=Decimal('75000.00'),
            debit_amount=Decimal('75000.00'),
            payment_status='POSTED',
            created_by=self.admin
        )

        self.assertEqual(self.project_1.get_recorded_expenditure(), Decimal('75000.00'))

        # Reverse transaction via POST
        response = self.client.post(reverse('projects:project_finance', kwargs={'pk': self.project_1.pk}), {
            'action': 'reverse_transaction',
            'txn_id': txn.pk,
            'reason': 'Invoice charged twice by crane vendor'
        })
        self.assertEqual(response.status_code, 302)

        txn.refresh_from_db()
        self.assertTrue(txn.is_reversed)
        self.assertEqual(txn.payment_status, 'REVERSED')
        self.assertIn('Invoice charged twice by crane vendor', txn.description)

        # Recalculated expenditure drops to 0
        self.assertEqual(self.project_1.get_recorded_expenditure(), Decimal('0.00'))

    def test_budget_allocation_deletion_and_recalculation(self):
        """Deleting custom allocation removes database record and restores default benchmark formula."""
        self.client.login(username='admin_safe', password='Password123!')

        alloc = BudgetAllocation.objects.create(
            project=self.project_1,
            category='Labour & Manpower',
            allocated_amount=Decimal('15000000.00'),
            notes='Custom allocation for labour intensive foundation phase'
        )

        analytics = get_project_budget_analytics(self.project_1)
        item = next(x for x in analytics['breakdown'] if x['category'] == 'Labour & Manpower')
        self.assertTrue(item['is_custom'])
        self.assertEqual(item['planned'], Decimal('15000000.00'))

        # Delete allocation via POST
        response = self.client.post(reverse('projects:project_budget', kwargs={'pk': self.project_1.pk}), {
            'action': 'delete_allocation',
            'allocation_id': alloc.pk
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(BudgetAllocation.objects.filter(pk=alloc.pk).exists())

        # Verify default ratio restored (28% of 50 Cr = 1.4 Cr)
        analytics_after = get_project_budget_analytics(self.project_1)
        item_after = next(x for x in analytics_after['breakdown'] if x['category'] == 'Labour & Manpower')
        self.assertFalse(item_after['is_custom'])
        self.assertEqual(item_after['planned'], Decimal('14000000.00'))

    def test_legal_document_edit_and_delete(self):
        """Legal documents can be edited and deleted with CSRF POST protection."""
        self.client.login(username='admin_safe', password='Password123!')

        doc = LegalDocument.objects.create(
            project=self.project_1,
            title='Environmental Impact Clearance',
            document_type='EIA',
            reference_number='EIA-MH-2026-99',
            issuing_authority='Ministry of Environment',
            status='Active & Approved',
            uploaded_by=self.admin
        )

        # Edit
        response = self.client.post(reverse('projects:project_legal', kwargs={'pk': self.project_1.pk}), {
            'action': 'edit_document',
            'doc_id': doc.pk,
            'title': 'Environmental Clearance - Stage 2 Amendment',
            'document_type': 'EIA Amendment',
            'reference_number': 'EIA-MH-2026-99-A',
            'issuing_authority': 'State Environment Impact Assessment Authority',
            'status': 'Approved with stipulations'
        })
        self.assertEqual(response.status_code, 302)
        doc.refresh_from_db()
        self.assertEqual(doc.title, 'Environmental Clearance - Stage 2 Amendment')

        # Delete
        response = self.client.post(reverse('projects:project_legal', kwargs={'pk': self.project_1.pk}), {
            'action': 'delete_document',
            'doc_id': doc.pk
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(LegalDocument.objects.filter(pk=doc.pk).exists())

    def test_project_contact_edit_and_delete(self):
        """External project contacts can be edited and deleted."""
        self.client.login(username='admin_safe', password='Password123!')

        contact = ProjectContact.objects.create(
            project=self.project_1,
            name='Arun Soman',
            role_assignment='Structural Consultant',
            organization='Soman Engineering Associates',
            phone='+91 98201 11223',
            email='arun@soman.mock'
        )

        # Edit
        response = self.client.post(reverse('projects:project_people', kwargs={'pk': self.project_1.pk}), {
            'action': 'edit_contact',
            'contact_id': contact.pk,
            'name': 'Arun Soman (Senior Fellow)',
            'role_assignment': 'Principal Structural Engineer',
            'organization': 'Soman Engineering Associates LLP',
            'phone': '+91 98201 11223',
            'email': 'arun.soman@sea.mock'
        })
        self.assertEqual(response.status_code, 302)
        contact.refresh_from_db()
        self.assertEqual(contact.name, 'Arun Soman (Senior Fellow)')

        # Delete
        response = self.client.post(reverse('projects:project_people', kwargs={'pk': self.project_1.pk}), {
            'action': 'delete_contact',
            'contact_id': contact.pk
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ProjectContact.objects.filter(pk=contact.pk).exists())

    def test_daily_diary_edit_and_delete(self):
        """Daily site diary entries can be edited and deleted."""
        self.client.login(username='admin_safe', password='Password123!')

        diary = DailyDiaryEntry.objects.create(
            project=self.project_1,
            supervisor=self.supervisor,
            date=date(2026, 3, 10),
            day_number=45,
            title='Pouring Basement B2 Retaining Wall',
            weather_condition='Sunny, 31C',
            work_summary='Retaining wall section 4 completed without honeycomb defects.'
        )

        # Edit
        response = self.client.post(reverse('projects:project_diary', kwargs={'pk': self.project_1.pk}), {
            'action': 'edit_diary',
            'entry_id': diary.pk,
            'date': '2026-03-10',
            'day_number': 45,
            'title': 'Pouring Basement B2 Retaining Wall (Completed)',
            'weather_condition': 'Sunny, 33C',
            'work_summary': 'Retaining wall section 4 completed with cube test samples taken.'
        })
        self.assertEqual(response.status_code, 302)
        diary.refresh_from_db()
        self.assertIn('cube test samples taken', diary.work_summary)

        # Delete
        response = self.client.post(reverse('projects:project_diary', kwargs={'pk': self.project_1.pk}), {
            'action': 'delete_diary',
            'entry_id': diary.pk
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(DailyDiaryEntry.objects.filter(pk=diary.pk).exists())

    def test_work_plan_task_edit_and_delete(self):
        """Work plan scheduled tasks can be edited and deleted."""
        self.client.login(username='admin_safe', password='Password123!')

        task = WorkPlanTask.objects.create(
            project=self.project_1,
            supervisor=self.supervisor,
            title='Excavation Pit Dewatering',
            work_area='Zone North',
            start_date=date(2026, 3, 1),
            target_date=date(2026, 3, 15),
            progress_percentage=60,
            status='In Progress'
        )

        # Edit
        response = self.client.post(reverse('projects:project_schedule', kwargs={'pk': self.project_1.pk}), {
            'action': 'edit_task',
            'task_id': task.pk,
            'title': 'Excavation Pit Dewatering & Submersible Pump Overhaul',
            'work_area': 'Zone North & West',
            'start_date': '2026-03-01',
            'target_date': '2026-03-18',
            'progress_percentage': 85,
            'status': 'In Progress',
            'delay_reason': ''
        })
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.progress_percentage, 85)

        # Delete
        response = self.client.post(reverse('projects:project_schedule', kwargs={'pk': self.project_1.pk}), {
            'action': 'delete_task',
            'task_id': task.pk
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(WorkPlanTask.objects.filter(pk=task.pk).exists())

    def test_unauthorized_and_cross_project_delete_rejected(self):
        """
        Non-admin users cannot delete projects, and cross-project deletion attempts are blocked.
        """
        # Site supervisor attempts to delete project 1
        self.client.login(username='supervisor_safe', password='Password123!')
        response = self.client.post(reverse('projects:project_settings', kwargs={'pk': self.project_1.pk}), {
            'action': 'delete_project'
        })
        self.assertEqual(response.status_code, 302)
        # Project must still exist
        self.assertTrue(Project.objects.filter(pk=self.project_1.pk).exists())

        # Cross project attempt: Supervisor (only assigned to Project 1) attempts to modify Project 2
        response = self.client.post(reverse('projects:project_labour', kwargs={'pk': self.project_2.pk}), {
            'action': 'delete_labour',
            'entry_id': 9999
        })
        self.assertEqual(response.status_code, 403)

    def test_project_permanent_deletion_by_company_admin(self):
        """Company administrator can permanently delete a project and all cascading records."""
        self.client.login(username='admin_safe', password='Password123!')

        p2_id = self.project_2.pk
        response = self.client.post(reverse('projects:project_settings', kwargs={'pk': p2_id}), {
            'action': 'delete_project'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('projects:project_list'))
        self.assertFalse(Project.objects.filter(pk=p2_id).exists())



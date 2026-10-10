from django.core.management.base import BaseCommand
from apps.accounts.models import User, ProjectMembership, RoleChoices
from apps.projects.models import (
    Project,
    ProjectStatusChoices,
    Supplier,
    MaterialPurchaseOrder,
    MaterialInvoice,
    InvoicePayment,
    LabourEntry,
    FinancialTransaction,
    BudgetAllocation,
    LegalDocument,
    ProjectContact,
    DailyDiaryEntry,
    WorkPlanTask,
)
from decimal import Decimal
from datetime import date


class Command(BaseCommand):
    help = 'Seeds initial demonstration accounts and sample construction projects with INR records.'

    def handle(self, *args, **options):
        self.stdout.write("Seeding demonstration accounts...")

        users_data = [
            ('superadmin', 'superadmin@novabuild.com', 'Super', 'Administrator', RoleChoices.SUPER_ADMIN, True, True),
            ('companyadmin', 'exec@novabuild.com', 'Elena', 'Vance', RoleChoices.COMPANY_ADMIN, True, False),
            ('pm_lead', 'pm@novabuild.com', 'Marcus', 'Brody', RoleChoices.PROJECT_MANAGER, True, False),
            ('accountant', 'accounts@novabuild.com', 'Sarah', 'Jenkins', RoleChoices.ACCOUNTANT, True, False),
            ('legal_officer', 'legal@novabuild.com', 'Diana', 'Prince', RoleChoices.LEGAL_OFFICER, True, False),
            ('supervisor', 'site@novabuild.com', 'Alex', 'Reyes', RoleChoices.SITE_SUPERVISOR, True, False),
            ('auditor', 'audit@novabuild.com', 'Thomas', 'Crown', RoleChoices.AUDITOR, True, False),
        ]

        created_users = {}
        for username, email, first, last, role, approved, is_super in users_data:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first,
                    'last_name': last,
                    'primary_role': role,
                    'is_approved': approved,
                    'is_staff': is_super or role in [RoleChoices.SUPER_ADMIN, RoleChoices.COMPANY_ADMIN],
                    'is_superuser': is_super,
                    'organization': 'Nova Construction Holdings India'
                }
            )
            user.set_password('Admin@12345')
            user.save()
            created_users[username] = user

        # 1. Create sample construction projects with explicit INR budgets
        p1, _ = Project.objects.update_or_create(
            code='PRJ-2026-001',
            defaults={
                'name': 'The Aurora Waterfront Residences',
                'description': 'High-rise luxury residential condominium featuring 32 floors and sustainable pre-cast architecture.',
                'project_type': 'High-Rise Residential',
                'currency': 'INR',
                'location': 'Harbor Bay Sector 4, Mumbai Waterfront',
                'address': 'Plot 4A, Marine Promenade, Mumbai 400001',
                'client_name': 'Aura Luxury Developments Ltd',
                'client_contact': '+91 (022) 2834-0199 / client@auraluxury.com',
                'approved_initial_budget': Decimal('45000000.00'),  # ₹4,50,00,000.00
                'start_date': date(2026, 1, 15),
                'expected_completion_date': date(2028, 6, 30),
                'status': ProjectStatusChoices.ACTIVE,
                'progress_percentage': 38,
                'created_by': created_users['superadmin']
            }
        )

        p2, _ = Project.objects.update_or_create(
            code='PRJ-2026-002',
            defaults={
                'name': 'Nexus Horizon Tech Campus',
                'description': 'State-of-the-art corporate office campus comprising four interconnected 8-story commercial towers.',
                'project_type': 'Commercial Corporate Office',
                'currency': 'INR',
                'location': 'Whitefield Tech Corridor, Bengaluru',
                'address': 'Survey 102/3, Outer Ring Road, Bengaluru 560066',
                'client_name': 'Horizon Global Tech Parks India',
                'client_contact': '+91 (080) 4123-9100 / facilities@horizonglobal.com',
                'approved_initial_budget': Decimal('78500000.00'),  # ₹7,85,00,000.00
                'start_date': date(2025, 9, 1),
                'expected_completion_date': date(2027, 11, 30),
                'status': ProjectStatusChoices.ACTIVE,
                'progress_percentage': 62,
                'created_by': created_users['superadmin']
            }
        )

        # Assign Memberships
        ProjectMembership.objects.get_or_create(
            user=created_users['pm_lead'],
            project=p1,
            defaults={'role': RoleChoices.PROJECT_MANAGER, 'is_active': True}
        )
        ProjectMembership.objects.get_or_create(
            user=created_users['supervisor'],
            project=p1,
            defaults={'role': RoleChoices.SITE_SUPERVISOR, 'is_active': True}
        )
        ProjectMembership.objects.get_or_create(
            user=created_users['accountant'],
            project=p1,
            defaults={'role': RoleChoices.ACCOUNTANT, 'is_active': True}
        )
        ProjectMembership.objects.get_or_create(
            user=created_users['pm_lead'],
            project=p2,
            defaults={'role': RoleChoices.PROJECT_MANAGER, 'is_active': True}
        )

        # 2. Seed Construction Suppliers
        s1, _ = Supplier.objects.get_or_create(
            name='UltraTech Cement Ltd',
            defaults={
                'contact_person': 'Ramesh Sharma',
                'phone': '+91 98201 12345',
                'email': 'rmx.orders@ultratech.com',
                'address': 'Ahura Centre, Mahakali Caves Road, Andheri (E), Mumbai',
                'gst_number': '27AAACU1234L1Z5'
            }
        )
        s2, _ = Supplier.objects.get_or_create(
            name='Tata Steel Infrastructure Ltd',
            defaults={
                'contact_person': 'Vikramaditya Roy',
                'phone': '+91 98302 67890',
                'email': 'infra.sales@tatasteel.com',
                'address': 'Bombay House, 24 Homi Mody Street, Fort, Mumbai',
                'gst_number': '27AAACT9876M2Z8'
            }
        )
        s3, _ = Supplier.objects.get_or_create(
            name='Godrej Construction & Shuttering',
            defaults={
                'contact_person': 'Anil Kulkarni',
                'phone': '+91 98205 55443',
                'email': 'construction@godrej.com',
                'address': 'Pirojshanagar, Vikhroli, Mumbai',
                'gst_number': '27AAACG4321P1Z2'
            }
        )

        # 3. Seed Labour Entries for PRJ-2026-001
        LabourEntry.objects.get_or_create(
            project=p1,
            date=date.today(),
            category='Masonry & Brickwork Gang',
            defaults={
                'location_floor': 'Floor 14, Tower A',
                'workers_count': 14,
                'wage_rate_per_day': Decimal('750.00'),
                'gross_wages': Decimal('10500.00'),
                'paid_amount': Decimal('10500.00'),
                'outstanding_amount': Decimal('0.00'),
                'supervisor': created_users['supervisor'],
                'notes': 'Brickwork shear wall elevation completed on schedule.'
            }
        )
        LabourEntry.objects.get_or_create(
            project=p1,
            date=date.today(),
            category='Steel Benders & Barbenders',
            defaults={
                'location_floor': 'Podium Level Slab',
                'workers_count': 16,
                'wage_rate_per_day': Decimal('800.00'),
                'gross_wages': Decimal('12800.00'),
                'paid_amount': Decimal('5000.00'),
                'outstanding_amount': Decimal('7800.00'),
                'supervisor': created_users['supervisor'],
                'notes': 'Heavy rebar tying for transfer beam.'
            }
        )
        LabourEntry.objects.get_or_create(
            project=p1,
            date=date.today(),
            category='Carpentry & Shuttering',
            defaults={
                'location_floor': 'Core Shear Walls',
                'workers_count': 12,
                'wage_rate_per_day': Decimal('700.00'),
                'gross_wages': Decimal('8400.00'),
                'paid_amount': Decimal('2500.00'),
                'outstanding_amount': Decimal('5900.00'),
                'supervisor': created_users['supervisor'],
                'notes': 'Aluminium formwork setup for lift shaft.'
            }
        )

        # 4. Seed Purchase Orders & Invoices with Partial Payments for PRJ-2026-001
        po1, _ = MaterialPurchaseOrder.objects.get_or_create(
            project=p1,
            po_number='PO-2026-081',
            defaults={
                'supplier': s1,
                'category': 'Ready-Mix Concrete M35',
                'description': '450 cu.m M35 Grade RMC with slump retention ad-mix for structural column pour',
                'quantity': '450 cu.m',
                'estimated_amount': Decimal('1800000.00'),
                'status': 'DELIVERED',
                'created_by': created_users['pm_lead']
            }
        )
        po2, _ = MaterialPurchaseOrder.objects.get_or_create(
            project=p1,
            po_number='PO-2026-088',
            defaults={
                'supplier': s2,
                'category': 'TMT Steel Fe500D',
                'description': '85 Metric Tonnes 16mm & 25mm high-ductility thermo-mechanically treated rebar',
                'quantity': '85 Tonnes',
                'estimated_amount': Decimal('4250000.00'),
                'status': 'PARTIAL',
                'created_by': created_users['pm_lead']
            }
        )

        inv1, _ = MaterialInvoice.objects.get_or_create(
            project=p1,
            invoice_number='INV-2026-081',
            defaults={
                'purchase_order': po1,
                'supplier': s1,
                'material_description': 'RMC M35 Batch Pour Delivery (450 cu.m)',
                'quantity': '450 cu.m',
                'total_amount': Decimal('1800000.00'),
                'paid_amount': Decimal('1800000.00'),
                'outstanding_balance': Decimal('0.00'),
                'status': 'PAID',
                'created_by': created_users['pm_lead']
            }
        )
        inv2, _ = MaterialInvoice.objects.get_or_create(
            project=p1,
            invoice_number='INV-2026-088',
            defaults={
                'purchase_order': po2,
                'supplier': s2,
                'material_description': 'TMT Steel Fe500D 50MT Lot-1 Delivery',
                'quantity': '50 Tonnes',
                'total_amount': Decimal('2500000.00'),
                'paid_amount': Decimal('1000000.00'),
                'outstanding_balance': Decimal('1500000.00'),
                'status': 'PARTIALLY_PAID',
                'created_by': created_users['pm_lead']
            }
        )

        # Seed Invoice Payment history
        InvoicePayment.objects.get_or_create(
            invoice=inv1,
            reference_number='UTR-HDFC-99128301',
            defaults={
                'project': p1,
                'amount': Decimal('1800000.00'),
                'payment_date': date(2026, 2, 20),
                'payment_method': 'BANK_TRANSFER',
                'notes': 'Full settlement for RMC batch delivery #81',
                'recorded_by': created_users['accountant']
            }
        )
        InvoicePayment.objects.get_or_create(
            invoice=inv2,
            reference_number='UTR-SBI-44019283',
            defaults={
                'project': p1,
                'amount': Decimal('1000000.00'),
                'payment_date': date(2026, 3, 5),
                'payment_method': 'BANK_TRANSFER',
                'notes': 'Advance milestone payment 40% against rebar dispatch',
                'recorded_by': created_users['accountant']
            }
        )

        # 5. Seed Consolidated Ledger Transactions
        FinancialTransaction.objects.get_or_create(
            project=p1,
            transaction_ref='TXN-2026-001',
            defaults={
                'transaction_type': 'EXPENSE',
                'category': 'Materials & Procurement',
                'description': 'Ready-Mix Concrete batch pour invoice #INV-2026-081',
                'amount': Decimal('1800000.00'),
                'debit_amount': Decimal('1800000.00'),
                'credit_amount': Decimal('0.00'),
                'payment_status': 'POSTED',
                'related_invoice': inv1,
                'created_by': created_users['accountant']
            }
        )
        FinancialTransaction.objects.get_or_create(
            project=p1,
            transaction_ref='TXN-2026-002',
            defaults={
                'transaction_type': 'PAYMENT_SUPPLIER',
                'category': 'Materials & Procurement',
                'description': 'Settlement to UltraTech Cement Ltd Ref: UTR-HDFC-99128301',
                'amount': Decimal('1800000.00'),
                'debit_amount': Decimal('0.00'),
                'credit_amount': Decimal('1800000.00'),
                'payment_status': 'POSTED',
                'related_invoice': inv1,
                'created_by': created_users['accountant']
            }
        )
        FinancialTransaction.objects.get_or_create(
            project=p1,
            transaction_ref='TXN-2026-003',
            defaults={
                'transaction_type': 'EXPENSE',
                'category': 'Materials & Procurement',
                'description': 'Tata Steel 50MT rebar invoice #INV-2026-088',
                'amount': Decimal('2500000.00'),
                'debit_amount': Decimal('2500000.00'),
                'credit_amount': Decimal('0.00'),
                'payment_status': 'POSTED',
                'related_invoice': inv2,
                'created_by': created_users['accountant']
            }
        )
        FinancialTransaction.objects.get_or_create(
            project=p1,
            transaction_ref='TXN-2026-004',
            defaults={
                'transaction_type': 'PAYMENT_SUPPLIER',
                'category': 'Materials & Procurement',
                'description': 'Partial settlement to Tata Steel Ref: UTR-SBI-44019283',
                'amount': Decimal('1000000.00'),
                'debit_amount': Decimal('0.00'),
                'credit_amount': Decimal('1000000.00'),
                'payment_status': 'POSTED',
                'related_invoice': inv2,
                'created_by': created_users['accountant']
            }
        )

        # 6. Seed Budget Allocations for Analytics Pie Chart
        BudgetAllocation.objects.update_or_create(
            project=p1,
            category='Labour & Manpower',
            defaults={'allocated_amount': Decimal('12500000.00'), 'notes': 'Site muster roll & gang contractors'}
        )
        BudgetAllocation.objects.update_or_create(
            project=p1,
            category='Materials & Procurement',
            defaults={'allocated_amount': Decimal('20000000.00'), 'notes': 'Concrete, Steel, Masonry & Finishing'}
        )
        BudgetAllocation.objects.update_or_create(
            project=p1,
            category='Equipment & Machinery',
            defaults={'allocated_amount': Decimal('5500000.00'), 'notes': 'Tower cranes, boom placers & earthmovers'}
        )
        BudgetAllocation.objects.update_or_create(
            project=p1,
            category='Subcontractors & MEP',
            defaults={'allocated_amount': Decimal('4500000.00'), 'notes': 'Electrical, HVAC, Plumbing & Fire'}
        )
        BudgetAllocation.objects.update_or_create(
            project=p1,
            category='Legal, Permits & Compliance',
            defaults={'allocated_amount': Decimal('2500000.00'), 'notes': 'Municipal sanctions, RERA, EIA & Fire NOC'}
        )

        # 7. Seed Legal Documents
        LegalDocument.objects.get_or_create(
            project=p1,
            title='Building Sanction Plan Approval',
            defaults={
                'document_type': 'Municipal Sanction',
                'reference_number': 'MCGM/BP/2025/8812',
                'issuing_authority': 'Municipal Corporation of Greater Mumbai (MCGM)',
                'issue_date': date(2026, 1, 10),
                'expiry_date': date(2029, 1, 9),
                'status': 'Active & Approved',
                'uploaded_by': created_users['legal_officer']
            }
        )
        LegalDocument.objects.get_or_create(
            project=p1,
            title='Fire Safety Provisional NOC',
            defaults={
                'document_type': 'Fire Clearance',
                'reference_number': 'FS/MUM/NOC/2025/104',
                'issuing_authority': 'Chief Fire Officer, Mumbai Fire Brigade',
                'issue_date': date(2025, 11, 15),
                'expiry_date': date(2026, 11, 14),
                'status': 'Renewal in 34 Days',
                'uploaded_by': created_users['legal_officer']
            }
        )
        LegalDocument.objects.get_or_create(
            project=p1,
            title='State Environmental Impact Assessment Clearance',
            defaults={
                'document_type': 'Environmental Clearance',
                'reference_number': 'SEIAA-MH-2025-44',
                'issuing_authority': 'State Environmental Authority (SEIAA)',
                'issue_date': date(2025, 8, 20),
                'expiry_date': date(2030, 8, 19),
                'status': 'Active & Approved',
                'uploaded_by': created_users['legal_officer']
            }
        )

        # 8. Seed Contacts
        ProjectContact.objects.get_or_create(
            project=p1,
            name='Ar. Julian Montgomery',
            defaults={
                'role_assignment': 'Principal Architect',
                'organization': 'Montgomery & Partners Architects',
                'phone': '+91 98200 44112',
                'email': 'julian@montgomeryarch.com'
            }
        )
        ProjectContact.objects.get_or_create(
            project=p1,
            name='Er. Rajesh Nair, PE',
            defaults={
                'role_assignment': 'Lead Structural Consultant',
                'organization': 'Apex Structural Engineers',
                'phone': '+91 98209 88771',
                'email': 'rajesh@apexstructures.in'
            }
        )
        ProjectContact.objects.get_or_create(
            project=p1,
            name='Balwinder Singh',
            defaults={
                'role_assignment': 'Labour Contractor (Concrete)',
                'organization': 'BS Shuttering & Civil Gangs',
                'phone': '+91 98199 77665',
                'email': 'bsgangs@construction.net'
            }
        )

        # 9. Seed Daily Diary Progress Log
        DailyDiaryEntry.objects.get_or_create(
            project=p1,
            date=date.today(),
            day_number=78,
            defaults={
                'title': 'Tower A Core Slab Casting & Rebar Inspection',
                'weather_condition': 'Clear & Sunny',
                'temperature_celsius': 31,
                'work_summary': 'Completed casting of 14th floor shear wall core and transfer girder. 450 cu.m of M35 grade concrete poured successfully with zero pump blockages. Cube testing samples taken at truck arrivals (sets of 6 cubes for 7-day and 28-day compression testing). No safety incidents recorded.',
                'supervisor': created_users['supervisor'],
                'photo_1_caption': 'Rebar tying inspection for 14th floor transfer beam',
                'photo_2_caption': 'Concrete boom placer pouring M35 mix at core wall',
                'photo_3_caption': 'Finished slab top surface and curing ponding setup',
                'status': 'Approved'
            }
        )

        # 10. Seed Work Plan Tasks
        WorkPlanTask.objects.get_or_create(
            project=p1,
            title='Basement -2 Raft Foundation & Piling',
            defaults={
                'work_area': 'Sub-Structure Core',
                'supervisor': created_users['supervisor'],
                'start_date': date(2026, 1, 15),
                'target_date': date(2026, 3, 30),
                'progress_percentage': 100,
                'status': 'Completed'
            }
        )
        WorkPlanTask.objects.get_or_create(
            project=p1,
            title='Tower A Superstructure Casting (Floors 1-15)',
            defaults={
                'work_area': 'Tower A Core Shear Walls',
                'supervisor': created_users['supervisor'],
                'start_date': date(2026, 4, 1),
                'target_date': date(2026, 11, 15),
                'progress_percentage': 78,
                'status': 'In Progress'
            }
        )
        WorkPlanTask.objects.get_or_create(
            project=p1,
            title='External Brickwork & Facade Glazing',
            defaults={
                'work_area': 'Floors 1 to 8',
                'supervisor': created_users['supervisor'],
                'start_date': date(2026, 10, 1),
                'target_date': date(2027, 1, 30),
                'progress_percentage': 15,
                'status': 'In Progress',
                'delay_reason': 'Monsoon rain delay (+4 days)'
            }
        )

        self.stdout.write(self.style.SUCCESS("All demo data, INR construction records, and financial ledger items seeded successfully!"))

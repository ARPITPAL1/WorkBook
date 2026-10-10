from django.core.management.base import BaseCommand
from apps.accounts.models import User, ProjectMembership, RoleChoices
from apps.projects.models import Project, ProjectStatusChoices
from decimal import Decimal
from datetime import date


class Command(BaseCommand):
    help = 'Seeds initial demonstration accounts and sample construction projects.'

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
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first,
                    'last_name': last,
                    'primary_role': role,
                    'is_approved': approved,
                    'is_staff': is_super or role in [RoleChoices.SUPER_ADMIN, RoleChoices.COMPANY_ADMIN],
                    'is_superuser': is_super,
                    'organization': 'Nova Construction Holdings'
                }
            )
            user.set_password('Admin@12345')
            user.save()
            created_users[username] = user
            status_str = "Created" if created else "Updated password for"
            self.stdout.write(f"  - {status_str}: {username} ({role})")

        # Create sample construction projects
        p1, _ = Project.objects.get_or_create(
            code='PRJ-2026-001',
            defaults={
                'name': 'The Aurora Waterfront Residences',
                'description': 'High-rise luxury residential condominium featuring 32 floors and sustainable pre-cast architecture.',
                'project_type': 'High-Rise Residential',
                'location': 'Harbor Bay Sector 4, Waterfront District',
                'client_name': 'Aura Luxury Developments Ltd',
                'client_contact': '+1 (555) 019-2834 / client@auraluxury.com',
                'approved_initial_budget': Decimal('45000000.00'),
                'start_date': date(2026, 1, 15),
                'expected_completion_date': date(2028, 6, 30),
                'status': ProjectStatusChoices.ACTIVE,
                'progress_percentage': 38,
                'created_by': created_users['superadmin']
            }
        )

        p2, _ = Project.objects.get_or_create(
            code='PRJ-2026-002',
            defaults={
                'name': 'Nexus Horizon Tech Campus',
                'description': 'State-of-the-art corporate office campus comprising four interconnected 8-story commercial towers.',
                'project_type': 'Commercial Corporate Office',
                'location': 'Innovation Boulevard, Silicon Corridor',
                'client_name': 'Horizon Global Tech Parks',
                'client_contact': '+1 (555) 048-9123 / facilities@horizonglobal.com',
                'approved_initial_budget': Decimal('78500000.00'),
                'start_date': date(2025, 9, 1),
                'expected_completion_date': date(2027, 11, 30),
                'status': ProjectStatusChoices.ACTIVE,
                'progress_percentage': 62,
                'created_by': created_users['superadmin']
            }
        )

        # Assign Project Memberships
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

        self.stdout.write(self.style.SUCCESS("Demo accounts and projects seeded successfully!"))

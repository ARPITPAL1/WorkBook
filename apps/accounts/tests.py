from django.test import TestCase, Client
from django.urls import reverse
from decimal import Decimal
from datetime import date
from apps.accounts.models import User, ProjectMembership, RoleChoices
from apps.projects.models import Project, ProjectStatusChoices

class AccountsAndRolesTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Super Admin
        self.super_admin = User.objects.create_superuser(
            username='superadmin',
            email='superadmin@example.com',
            password='Password123!',
            primary_role=RoleChoices.SUPER_ADMIN,
            is_approved=True
        )

        # Company Admin
        self.company_admin = User.objects.create_user(
            username='companyadmin',
            email='companyadmin@example.com',
            password='Password123!',
            primary_role=RoleChoices.COMPANY_ADMIN,
            is_approved=True
        )

        # Project Manager
        self.pm_user = User.objects.create_user(
            username='pm_user',
            email='pm@example.com',
            password='Password123!',
            primary_role=RoleChoices.PROJECT_MANAGER,
            is_approved=True
        )

        # Accountant
        self.accountant = User.objects.create_user(
            username='accountant',
            email='accountant@example.com',
            password='Password123!',
            primary_role=RoleChoices.ACCOUNTANT,
            is_approved=True
        )

        # Site Supervisor
        self.supervisor = User.objects.create_user(
            username='supervisor1',
            email='supervisor@example.com',
            password='Password123!',
            primary_role=RoleChoices.SITE_SUPERVISOR,
            is_approved=True
        )

        # Unapproved user
        self.unapproved_user = User.objects.create_user(
            username='pending_user',
            email='pending@example.com',
            password='Password123!',
            primary_role=RoleChoices.SITE_SUPERVISOR,
            is_approved=False
        )

        # Sample Project
        self.project_a = Project.objects.create(
            name='Oceanview Luxury Towers',
            code='PRJ-2026-001',
            location='Bay Area Waterfront',
            client_name='Prestige Developers Ltd',
            approved_initial_budget=Decimal('5000000.00'),
            start_date=date(2026, 1, 1),
            expected_completion_date=date(2027, 6, 30),
            status=ProjectStatusChoices.ACTIVE,
            created_by=self.super_admin
        )

        self.project_b = Project.objects.create(
            name='Silicon Heights Commercial Plaza',
            code='PRJ-2026-002',
            location='Tech District Sector 9',
            client_name='Nexus Group',
            approved_initial_budget=Decimal('12000000.00'),
            start_date=date(2026, 3, 1),
            expected_completion_date=date(2028, 12, 31),
            status=ProjectStatusChoices.ACTIVE,
            created_by=self.super_admin
        )

        # Memberships: PM on Project A, Supervisor on Project A
        ProjectMembership.objects.create(
            user=self.pm_user,
            project=self.project_a,
            role=RoleChoices.PROJECT_MANAGER,
            is_active=True
        )

        ProjectMembership.objects.create(
            user=self.supervisor,
            project=self.project_a,
            role=RoleChoices.SITE_SUPERVISOR,
            is_active=True
        )

    def test_user_creation_and_role_properties(self):
        """Test default roles and boolean properties."""
        self.assertTrue(self.super_admin.is_super_admin)
        self.assertTrue(self.super_admin.is_company_admin)
        self.assertTrue(self.company_admin.is_company_admin)
        self.assertFalse(self.supervisor.is_company_admin)
        self.assertFalse(self.supervisor.is_super_admin)

    def test_project_membership_access(self):
        """Test that project membership grants project-level access."""
        # Supervisor has access to Project A, but NOT Project B
        self.assertTrue(self.supervisor.has_project_access(self.project_a))
        self.assertFalse(self.supervisor.has_project_access(self.project_b))

        # Company Admin has global access to all projects
        self.assertTrue(self.company_admin.has_project_access(self.project_a))
        self.assertTrue(self.company_admin.has_project_access(self.project_b))

    def test_financial_permissions_matrix(self):
        """Test financial permissions logic."""
        # Super admin and Company admin can manage finance
        self.assertTrue(self.super_admin.can_manage_finance(self.project_a))
        self.assertTrue(self.company_admin.can_manage_finance(self.project_a))

        # PM assigned to Project A can manage finance on Project A
        self.assertTrue(self.pm_user.can_manage_finance(self.project_a))
        # PM NOT assigned to Project B cannot manage finance on Project B
        self.assertFalse(self.pm_user.can_manage_finance(self.project_b))

        # Supervisor cannot manage finance
        self.assertFalse(self.supervisor.can_manage_finance(self.project_a))

    def test_login_success_and_redirect(self):
        """Test successful authentication."""
        response = self.client.post(reverse('accounts:login'), {
            'username': 'supervisor1',
            'password': 'Password123!'
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('projects:project_list'), response.url)

    def test_unapproved_user_cannot_login(self):
        """Test that unapproved users are blocked from logging in."""
        response = self.client.post(reverse('accounts:login'), {
            'username': 'pending_user',
            'password': 'Password123!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pending administrator approval")

    def test_invalid_credentials(self):
        """Test rejection of invalid credentials."""
        response = self.client.post(reverse('accounts:login'), {
            'username': 'supervisor1',
            'password': 'WrongPassword!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password")

    def test_logout(self):
        """Test secure logout."""
        self.client.login(username='supervisor1', password='Password123!')
        response = self.client.get(reverse('accounts:logout'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)

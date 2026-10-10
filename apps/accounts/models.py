from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

class RoleChoices(models.TextChoices):
    SUPER_ADMIN = 'SUPER_ADMIN', _('Super Administrator')
    COMPANY_ADMIN = 'COMPANY_ADMIN', _('Company Administrator')
    PROJECT_MANAGER = 'PROJECT_MANAGER', _('Project Manager')
    ACCOUNTANT = 'ACCOUNTANT', _('Accountant')
    LEGAL_OFFICER = 'LEGAL_OFFICER', _('Legal Officer')
    SITE_SUPERVISOR = 'SITE_SUPERVISOR', _('Site Supervisor')
    AUDITOR = 'AUDITOR', _('Read-only Auditor')


class User(AbstractUser):
    phone_number = models.CharField(max_length=20, blank=True, verbose_name=_("Phone Number"))
    primary_role = models.CharField(
        max_length=30,
        choices=RoleChoices.choices,
        default=RoleChoices.SITE_SUPERVISOR,
        verbose_name=_("System Role"),
        help_text=_("Default organizational role for the user.")
    )
    is_approved = models.BooleanField(
        default=True,
        verbose_name=_("Account Approved"),
        help_text=_("Designates whether this user account is approved by an administrator.")
    )
    organization = models.CharField(
        max_length=150,
        blank=True,
        verbose_name=_("Company / Organization")
    )

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ['username']

    def __str__(self):
        full_name = self.get_full_name()
        display_name = f"{full_name} ({self.username})" if full_name else self.username
        return f"{display_name} - {self.get_primary_role_display()}"

    @property
    def is_super_admin(self):
        return self.is_superuser or self.primary_role == RoleChoices.SUPER_ADMIN

    @property
    def is_company_admin(self):
        return self.is_super_admin or self.primary_role == RoleChoices.COMPANY_ADMIN

    def get_role_on_project(self, project):
        """
        Return the user's role on the specific project.
        Global administrators always inherit executive role access.
        """
        if self.is_super_admin:
            return RoleChoices.SUPER_ADMIN
        if self.is_company_admin:
            return RoleChoices.COMPANY_ADMIN
        membership = self.project_memberships.filter(project=project, is_active=True).first()
        return membership.role if membership else None

    def has_project_access(self, project):
        """Check if user has any active access to the given project."""
        if not self.is_active or not self.is_approved:
            return False
        if self.is_company_admin:
            return True
        return self.project_memberships.filter(project=project, is_active=True).exists()

    def can_manage_project(self, project=None):
        """Determine if user can create or configure project parameters."""
        if not self.is_active or not self.is_approved:
            return False
        if self.is_company_admin:
            return True
        if project:
            role = self.get_role_on_project(project)
            return role in (RoleChoices.SUPER_ADMIN, RoleChoices.COMPANY_ADMIN, RoleChoices.PROJECT_MANAGER)
        return self.primary_role == RoleChoices.PROJECT_MANAGER

    def can_manage_finance(self, project):
        """Determine if user can record or approve financial transactions."""
        if not self.is_active or not self.is_approved:
            return False
        if self.is_super_admin:
            return True
        role = self.get_role_on_project(project)
        return role in (RoleChoices.SUPER_ADMIN, RoleChoices.COMPANY_ADMIN, RoleChoices.PROJECT_MANAGER, RoleChoices.ACCOUNTANT)

    def can_access_legal(self, project):
        """Determine if user can access legal documents."""
        if not self.is_active or not self.is_approved:
            return False
        if self.is_company_admin:
            return True
        role = self.get_role_on_project(project)
        return role in (RoleChoices.SUPER_ADMIN, RoleChoices.COMPANY_ADMIN, RoleChoices.PROJECT_MANAGER, RoleChoices.LEGAL_OFFICER, RoleChoices.AUDITOR)


class ProjectMembership(models.Model):
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='project_memberships',
        verbose_name=_("User")
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='memberships',
        verbose_name=_("Project")
    )
    role = models.CharField(
        max_length=30,
        choices=RoleChoices.choices,
        default=RoleChoices.SITE_SUPERVISOR,
        verbose_name=_("Project Role")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active Assignment")
    )
    assigned_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_memberships',
        verbose_name=_("Assigned By")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Project Membership")
        verbose_name_plural = _("Project Memberships")
        unique_together = ('user', 'project')
        indexes = [
            models.Index(fields=['user', 'project', 'is_active']),
            models.Index(fields=['project', 'role']),
        ]

    def __str__(self):
        return f"{self.user.username} -> {self.project.name} ({self.get_role_display()})"

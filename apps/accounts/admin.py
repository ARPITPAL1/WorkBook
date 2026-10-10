from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from apps.accounts.models import User, ProjectMembership


class ProjectMembershipInline(admin.TabularInline):
    model = ProjectMembership
    extra = 1
    fk_name = 'user'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'get_full_name', 'primary_role', 'is_approved', 'is_active', 'is_staff')
    list_filter = ('primary_role', 'is_approved', 'is_active', 'is_staff')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'organization')
    inlines = [ProjectMembershipInline]

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Construction Role & Organization', {
            'fields': ('primary_role', 'is_approved', 'organization', 'phone_number'),
        }),
    )


@admin.register(ProjectMembership)
class ProjectMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'project', 'role', 'is_active', 'created_at')
    list_filter = ('role', 'is_active')
    search_fields = ('user__username', 'project__name', 'project__code')

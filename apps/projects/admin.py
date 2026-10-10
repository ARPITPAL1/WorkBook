from django.contrib import admin
from apps.projects.models import Project
from apps.accounts.models import ProjectMembership


class ProjectMembershipInline(admin.TabularInline):
    model = ProjectMembership
    extra = 1
    fk_name = 'project'


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'location', 'client_name', 'status', 'approved_initial_budget', 'progress_percentage', 'start_date')
    list_filter = ('status', 'project_type', 'start_date')
    search_fields = ('code', 'name', 'location', 'client_name')
    inlines = [ProjectMembershipInline]

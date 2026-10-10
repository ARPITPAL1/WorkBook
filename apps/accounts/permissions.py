from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from apps.accounts.models import RoleChoices


def get_user_role_for_project(user, project):
    """Convenience function to get active project role."""
    if not user.is_authenticated:
        return None
    return user.get_role_on_project(project)


def project_access_required(view_func):
    """
    Decorator for views taking project_id or pk.
    Ensures user is logged in, approved, and has access to the project.
    Injects `project` object and `user_role` into request kwargs or attributes.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')

        if not request.user.is_approved:
            messages.error(request, "Your account is pending administrator approval.")
            return redirect('accounts:login')

        project_id = kwargs.get('project_id') or kwargs.get('pk')
        from apps.projects.models import Project
        project = get_object_or_404(Project, pk=project_id)

        if not request.user.has_project_access(project):
            messages.error(request, "Access denied. You are not assigned to this project.")
            raise PermissionDenied("You do not have access to this project.")

        request.current_project = project
        request.current_project_role = request.user.get_role_on_project(project)
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def project_role_required(allowed_roles):
    """
    Decorator ensuring user has one of the allowed roles on the project.
    Always allows Super Admin and Company Admin.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')

            if not request.user.is_approved:
                messages.error(request, "Your account is pending administrator approval.")
                return redirect('accounts:login')

            project_id = kwargs.get('project_id') or kwargs.get('pk')
            from apps.projects.models import Project
            project = get_object_or_404(Project, pk=project_id)

            if request.user.is_company_admin:
                request.current_project = project
                request.current_project_role = request.user.get_role_on_project(project)
                return view_func(request, *args, **kwargs)

            user_role = request.user.get_role_on_project(project)
            if not user_role or user_role not in allowed_roles:
                messages.error(request, "Permission denied for this project action.")
                raise PermissionDenied("Insufficient permissions for this operation.")

            request.current_project = project
            request.current_project_role = user_role
            return view_func(request, *args, **kwargs)

        return _wrapped_view
    return decorator


def admin_or_manager_required(view_func):
    """Decorator ensuring user is a Super Admin, Company Admin, or Project Manager."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_approved:
            messages.error(request, "Account pending approval.")
            return redirect('accounts:login')
        if request.user.is_company_admin or request.user.primary_role == RoleChoices.PROJECT_MANAGER:
            return view_func(request, *args, **kwargs)
        messages.error(request, "Administrative privileges required.")
        raise PermissionDenied("Administrative privileges required.")
    return _wrapped_view

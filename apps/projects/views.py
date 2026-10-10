from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from apps.projects.models import Project

@login_required
def project_list_view(request):
    """Placeholder view for projects portfolio homepage (detailed in Stage 2)."""
    projects = Project.objects.all()
    return render(request, 'projects/project_list.html', {'projects': projects})

@login_required
def project_create_view(request):
    """Placeholder view for creating a project."""
    return render(request, 'projects/project_form.html', {})

@login_required
def project_detail_view(request, pk):
    """Placeholder view for project workspace."""
    project = get_object_or_404(Project, pk=pk)
    return render(request, 'projects/project_detail.html', {'project': project})

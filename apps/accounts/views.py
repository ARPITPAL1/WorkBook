from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.accounts.forms import LoginForm, UserProfileForm, ProjectMembershipForm
from apps.accounts.models import User, ProjectMembership, RoleChoices
from apps.accounts.permissions import admin_or_manager_required


def login_view(request):
    if request.user.is_authenticated:
        return redirect('projects:project_list')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if not user.is_approved:
                messages.error(request, "Your account is pending administrator approval.")
                return render(request, 'accounts/login.html', {'form': form})
            login(request, user)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('projects:project_list')
        else:
            messages.error(request, "Invalid username or password. Please try again.")
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    if request.user.is_authenticated:
        logout(request)
        messages.info(request, "You have been logged out securely.")
    return redirect('accounts:login')


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect('accounts:profile')
    else:
        form = UserProfileForm(instance=request.user)

    memberships = request.user.project_memberships.filter(is_active=True).select_related('project')
    return render(request, 'accounts/profile.html', {
        'form': form,
        'memberships': memberships
    })


@login_required
@admin_or_manager_required
def user_list_view(request):
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'accounts/user_list.html', {'users': users})

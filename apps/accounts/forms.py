from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, UserChangeForm
from apps.accounts.models import User, ProjectMembership, RoleChoices


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg nova-input',
            'placeholder': 'Enter your username or email',
            'autofocus': True
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg nova-input',
            'placeholder': 'Enter your password'
        })
    )


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'organization']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control nova-input'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control nova-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-control nova-input'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control nova-input'}),
            'organization': forms.TextInput(attrs={'class': 'form-control nova-input'}),
        }


class ProjectMembershipForm(forms.ModelForm):
    class Meta:
        model = ProjectMembership
        fields = ['user', 'role', 'is_active']
        widgets = {
            'user': forms.Select(attrs={'class': 'form-select nova-input'}),
            'role': forms.Select(attrs={'class': 'form-select nova-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

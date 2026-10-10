from django.urls import path
from apps.projects import views

app_name = 'projects'

urlpatterns = [
    path('', views.project_list_view, name='project_list'),
    path('new/', views.project_create_view, name='project_create'),
    path('<int:pk>/', views.project_detail_view, name='project_detail'),
]

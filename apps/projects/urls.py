from django.urls import path
from apps.projects import views

app_name = 'projects'

urlpatterns = [
    path('', views.project_list_view, name='project_list'),
    path('new/', views.project_create_view, name='project_create'),
    path('<int:pk>/', views.project_detail_view, name='project_detail'),
    path('<int:pk>/labour/', views.project_labour_view, name='project_labour'),
    path('<int:pk>/materials/', views.project_materials_view, name='project_materials'),
    path('<int:pk>/materials/invoice/<int:invoice_id>/pay/', views.invoice_payment_create_view, name='invoice_payment_create'),
    path('<int:pk>/finance/', views.project_finance_view, name='project_finance'),
    path('<int:pk>/budget/', views.project_budget_view, name='project_budget'),
    path('<int:pk>/budget/api/', views.project_budget_api, name='project_budget_api'),
    path('<int:pk>/legal/', views.project_legal_view, name='project_legal'),
    path('<int:pk>/people/', views.project_people_view, name='project_people'),
    path('<int:pk>/diary/', views.project_diary_view, name='project_diary'),
    path('<int:pk>/schedule/', views.project_schedule_view, name='project_schedule'),
    path('<int:pk>/reports/', views.project_reports_view, name='project_reports'),
    path('<int:pk>/reports/export-ledger/', views.export_ledger_csv, name='export_ledger_csv'),
    path('<int:pk>/reports/export-labour/', views.export_labour_csv, name='export_labour_csv'),
    path('<int:pk>/reports/export-materials/', views.export_materials_csv, name='export_materials_csv'),
    path('<int:pk>/settings/', views.project_settings_view, name='project_settings'),
]

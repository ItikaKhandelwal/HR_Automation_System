# hr_app/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Home page should be the first path
    path('', views.home, name='home'),
    
    # Authentication
    path('accounts/login/', views.login_view, name='login'),
    path('accounts/logout/', views.logout_view, name='logout'),
    
    # Main pages
    path('dashboard/', views.dashboard, name='dashboard'),
    path('analytics/', views.analytics_dashboard, name='analytics'),
    
    # CV Processing
    path('upload/', views.upload_cv, name='upload_cv'),
    path('process/<int:candidate_id>/', views.process_cv, name='process_cv'),
    
    # Candidate Management
    path('candidate/<int:candidate_id>/', views.candidate_detail, name='candidate_detail'),
    path('candidate/<int:candidate_id>/delete/', views.delete_candidate, name='delete_candidate'),
    path('categorize/', views.categorize_candidates, name='categorize'),
    path('skill-filter/', views.skill_filter, name='skill_filter'),
    
    # Bulk Actions
    path('bulk-actions/', views.bulk_actions, name='bulk_actions'),
]
from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('quizzes/', views.quiz_list, name='quiz_list'),
    path('quiz/<int:id>/', views.attempt_quiz, name='attempt_quiz'),
    path('create-quiz/', views.create_quiz, name='create_quiz'),
    path('quiz/<int:quiz_id>/edit/', views.edit_quiz, name='edit_quiz'),
    path('quiz/<int:quiz_id>/delete/', views.delete_quiz, name='delete_quiz'),
    path('result/<int:id>/', views.result_view, name='result'),
]

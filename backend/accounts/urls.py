from accounts import views as acc_views
from django.urls import path
urlpatterns = [
    path('register', acc_views.register_view, name='register'),
    path('login', acc_views.login_view, name='login'),
    path('logout', acc_views.logout_view, name='logout'),
]
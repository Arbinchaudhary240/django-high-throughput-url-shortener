from django.urls import path
from . import views

urlpatterns = [
    path('api/shorten/', views.create_short_url, name='create_short_url'),
    path('r/<str:short_code>/', views.redirect_url, name='redirect_url'),
]
from django.urls import path
from .views import create_short_url, redirect_url

urlpatterns = [
    path('api/shorten/', create_short_url, name='create_short_url'),
    path('r/<str:short_code>/', redirect_url, name='redirect_url'),
]
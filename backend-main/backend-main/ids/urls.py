from django.urls import path
from . import views

urlpatterns = [
    path('read_csv', views.read_csv)
]
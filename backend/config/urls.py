"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path
from apps.trends.views_admin import delete_logs_view, source_status_view

urlpatterns = [
    path("", lambda request: redirect("http://127.0.0.1:5173/", permanent=False)),
    path("admin/source-status/", source_status_view, name="admin-source-status"),
    path("admin/delete-logs/", delete_logs_view, name="admin-delete-logs"),
    path("admin/", admin.site.urls),
    path("api/", include("apps.trends.api.urls")),
]

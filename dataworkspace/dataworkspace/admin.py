from django.contrib import admin
from django.contrib.admin.apps import AdminConfig
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from dataworkspace.apps.core.errors import DjangoAdminPermissionDeniedError


class DataWorkspaceAdminSite(admin.AdminSite):
    index_template = "admin/admin_home.html"

    @method_decorator(never_cache)
    def login(self, request, extra_context=None):
        """
        If user is an admin redirect to admin homepage.
        Displays a 404 page to non-admin users
        """
        if request.method == "GET" and self.has_permission(request):
            index_path = reverse("admin:index", current_app=self.name)
            return HttpResponseRedirect(index_path)
        raise DjangoAdminPermissionDeniedError()


class DataWorkspaceAdminConfig(AdminConfig):
    default_site = "dataworkspace.admin.DataWorkspaceAdminSite"

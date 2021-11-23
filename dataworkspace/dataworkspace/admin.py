from django.contrib import admin
from django.contrib.admin.apps import AdminConfig
from django.http import HttpResponseRedirect, Http404
from django.urls import reverse
from django.views.decorators.cache import never_cache


class DataWorkspaceAdminSite(admin.AdminSite):
    @never_cache
    def login(self, request, extra_context=None):
        """
        If user is an admin redirect to admin homepage.
        Displays a 404 page to non-admin users
        """
        if request.method == "GET" and self.has_permission(request):
            index_path = reverse("admin:index", current_app=self.name)
            return HttpResponseRedirect(index_path)
        raise Http404


class DataWorkspaceAdminConfig(AdminConfig):
    default_site = "dataworkspace.admin.DataWorkspaceAdminSite"

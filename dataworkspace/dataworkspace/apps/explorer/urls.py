from django.urls import path

from dataworkspace.apps.explorer.views import ExplorerIndex

urlpatterns = [
    path('', ExplorerIndex.as_view(), name='index'),
]

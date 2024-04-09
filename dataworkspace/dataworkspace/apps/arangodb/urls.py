from django.urls import path
from dataworkspace.apps.arangodb import views 

urlpatterns = [
    path("", views.TEMPORARY_print_credentials_to_url, name="temporary-arangodb-credentials"),
    path("remove", views.TEMPORARY_remove_temp_credentials_to_url, name="temporary-remove-arangodb-credentials"),
]

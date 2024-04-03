from django.urls import path
from . import views 

urlpatterns = [
    path("", views.TEMPORARY_print_credentials_to_url, name="temporary-arangodb-credentials")
]

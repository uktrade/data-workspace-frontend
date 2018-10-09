from django import forms
from django.contrib import admin
from app.models import (
	Database,
	Privilage,
)

admin.site.register(Database)
admin.site.register(Privilage)
